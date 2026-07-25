"""安全工具: 登录限流(内存版) + 密码强度校验 + 全局 API 限流"""
import time
from collections import defaultdict, deque
from threading import Lock

from app.core.config import settings
from app.core.exceptions import AppException, ErrorCode


class RateLimiter:
    """简单滑动窗口限流,按 key(IP/账号)计数。"""

    def __init__(self, max_attempts: int, window_sec: int):
        self.max_attempts = max_attempts
        self.window = window_sec
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str) -> int:
        """记录一次请求, 返回当前窗口内请求数"""
        now = time.time()
        with self._lock:
            q = self._hits[key]
            q.append(now)
            while q and now - q[0] > self.window:
                q.popleft()
            return len(q)

    def reset(self, key: str):
        with self._lock:
            self._hits.pop(key, None)

    def check(self, key: str):
        """超限抛异常; 不 hit (只检查)"""
        with self._lock:
            q = self._hits.get(key)
            if not q:
                return
            now = time.time()
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_attempts:
                raise AppException(
                    ErrorCode.RATE_LIMIT,
                    f"请求过于频繁,请 {self.window // 60} 分钟后再试",
                    http_status=429,
                )

    def check_and_hit(self, key: str):
        """检查+记录一次; 超限抛异常"""
        self.check(key)
        count = self.hit(key)
        return count


login_limiter = RateLimiter(settings.LOGIN_RATE_LIMIT_MAX, settings.LOGIN_RATE_LIMIT_WINDOW_SEC)

# 全局 API 限流: 默认 100 req/min/IP
api_limiter = RateLimiter(100, 60)



def validate_password_strength(password: str):
    if not password or len(password) < settings.PASSWORD_MIN_LEN:
        raise AppException(
            ErrorCode.WEAK_PASSWORD,
            f"密码长度至少 {settings.PASSWORD_MIN_LEN} 位",
        )
    # 简单强度: 不全是数字/不全是字母
    if password.isdigit() or password.isalpha():
        raise AppException(ErrorCode.WEAK_PASSWORD, "密码需同时包含字母和数字")
