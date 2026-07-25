"""
应用性能监控 (Application Performance Monitoring)
- 在内存中保留最近 N 条请求的耗时
- 按 path+method 聚合 p50/p95/avg/count/error_rate
- 提供最近时间窗口内的 QPS、错误数
- 线程安全, O(1) 写入, O(P) 读取 (P 为不同 path 的数量)
"""
import time
import threading
from collections import deque, defaultdict
from typing import Any

# 保留最近 5000 条请求记录
MAX_RECORDS = 5000

# 归一化 path: 把数字 id 替换成 {id}, 避免 path 爆炸
import re
_ID_PATTERNS = [
    (re.compile(r"/\d{4,}"), "/{id}"),  # 长数字 -> {id}
    (re.compile(r"/[0-9a-f]{8}-[0-9a-f-]{20,}"), "/{uuid}"),  # uuid
]


def normalize_path(path: str) -> str:
    p = path
    for pat, rep in _ID_PATTERNS:
        p = pat.sub(rep, p)
    # /api/v1 前缀去掉方便聚合
    if p.startswith("/api/v1"):
        p = p[len("/api/v1"):]
    if not p:
        p = "/"
    return p


class _Record:
    __slots__ = ("ts", "method", "path", "norm_path", "status", "dur_ms")

    def __init__(self, method: str, path: str, status: int, dur_ms: float):
        self.ts = time.time()
        self.method = method
        self.path = path
        self.norm_path = normalize_path(path)
        self.status = status
        self.dur_ms = dur_ms


class APMMetrics:
    def __init__(self, capacity: int = MAX_RECORDS):
        self._buf: deque[_Record] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def record(self, method: str, path: str, status: int, dur_ms: float) -> None:
        # 跳过静态/健康检查
        if path.startswith(("/files", "/health")):
            return
        rec = _Record(method, path, status, dur_ms)
        with self._lock:
            self._buf.append(rec)

    def _percentile(self, sorted_vals: list[float], pct: float) -> float:
        if not sorted_vals:
            return 0.0
        k = (len(sorted_vals) - 1) * pct
        f = int(k)
        c = min(f + 1, len(sorted_vals) - 1)
        if f == c:
            return sorted_vals[f]
        return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

    def snapshot(self, window_seconds: int = 300) -> dict[str, Any]:
        """返回最近 window_seconds 秒内的聚合指标"""
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            # 过滤时间窗口
            recs = [r for r in self._buf if r.ts >= cutoff]

        total = len(recs)
        errors = sum(1 for r in recs if r.status >= 400)
        durations = [r.dur_ms for r in recs]
        durations.sort()

        avg_ms = sum(durations) / len(durations) if durations else 0.0
        p50 = self._percentile(durations, 0.50)
        p95 = self._percentile(durations, 0.95)
        p99 = self._percentile(durations, 0.99)
        max_ms = max(durations) if durations else 0.0

        # 按端点聚合
        by_endpoint: dict[str, dict[str, Any]] = {}
        groups: dict[str, list[_Record]] = defaultdict(list)
        for r in recs:
            groups[f"{r.method} {r.norm_path}"].append(r)
        for key, items in groups.items():
            durs = sorted(x.dur_ms for x in items)
            err = sum(1 for x in items if x.status >= 400)
            by_endpoint[key] = {
                "key": key,
                "method": items[0].method,
                "path": items[0].norm_path,
                "count": len(items),
                "errors": err,
                "error_rate": err / len(items) if items else 0,
                "avg_ms": sum(durs) / len(durs),
                "p50_ms": self._percentile(durs, 0.50),
                "p95_ms": self._percentile(durs, 0.95),
                "max_ms": durs[-1] if durs else 0,
            }

        # 慢请求 Top 10 (全量 buf 里)
        with self._lock:
            slowest = sorted(self._buf, key=lambda r: -r.dur_ms)[:10]
        top_slow = [{
            "method": r.method, "path": r.norm_path, "status": r.status,
            "dur_ms": round(r.dur_ms, 1),
            "ago": round(now - r.ts, 1),
        } for r in slowest if r.dur_ms > 100]

        # 最近错误
        with self._lock:
            recent_errs = [r for r in self._buf if r.status >= 400][-10:]
        errors_list = [{
            "method": r.method, "path": r.path, "status": r.status,
            "dur_ms": round(r.dur_ms, 1), "ago": round(now - r.ts, 1),
        } for r in reversed(recent_errs)]

        qps = total / window_seconds if window_seconds > 0 else 0

        return {
            "window_seconds": window_seconds,
            "total_requests": total,
            "qps": round(qps, 2),
            "errors": errors,
            "error_rate": round(errors / total, 4) if total else 0,
            "avg_ms": round(avg_ms, 1),
            "p50_ms": round(p50, 1),
            "p95_ms": round(p95, 1),
            "p99_ms": round(p99, 1),
            "max_ms": round(max_ms, 1),
            "endpoints": sorted(by_endpoint.values(), key=lambda x: -x["count"]),
            "top_slow": top_slow,
            "recent_errors": errors_list,
            "buf_size": len(self._buf),
        }


# 全局单例
apm = APMMetrics()
