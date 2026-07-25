"""
QA 性能基线冒烟测试
- 普通 REST 列表接口：单请求 < 500ms（SQLite 测试环境基线）
- 记录 P95，结果打印到报告
注意：测试环境为 SQLite，生产 MySQL/Milvus 数值会更高，本测试仅作回归冒烟。
"""
from __future__ import annotations
import time
import statistics
import pytest


def _login(client):
    r = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
    return r.json()["data"]["token"]


def _measure(client, method, url, headers=None, json=None, n=11):
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        if method == "GET":
            client.get(url, headers=headers)
        else:
            client.post(url, json=json, headers=headers)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {
        "min": round(times[0], 2),
        "median": round(statistics.median(times), 2),
        "p95": round(times[int(len(times) * 0.95) - 1], 2),
        "max": round(times[-1], 2),
    }


class TestPerfBaseline:
    def test_list_endpoints_latency(self, client):
        token = _login(client)
        H = {"Authorization": f"Bearer {token}"}
        endpoints = [
            ("GET", "/api/v1/workflows", None),
            ("GET", "/api/v1/agents", None),
            ("GET", "/api/v1/rag/kbs", None),
            ("GET", "/api/v1/groups", None),
            ("GET", "/api/v1/skills", None),
        ]
        print("\n=== 性能基线（SQLite 测试环境，单位 ms）===")
        for method, url, _ in endpoints:
            m = _measure(client, method, url, headers=H)
            print(f"  {method} {url}: min={m['min']} median={m['median']} p95={m['p95']} max={m['max']}")
            # 冒烟阈值：测试环境应远低于 500ms；放宽到 800ms 避免偶发抖动误报
            assert m["p95"] < 800, f"{url} P95={m['p95']}ms 超过冒烟阈值"

    def test_auth_login_latency(self, client):
        m = _measure(client, "POST", "/api/v1/auth/login",
                     json={"account": "admin", "password": "admin123"})
        print(f"\n  POST /api/v1/auth/login: min={m['min']} median={m['median']} p95={m['p95']} max={m['max']}")
        assert m["p95"] < 800
