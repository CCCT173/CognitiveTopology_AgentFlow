"""Phase 0 smoke tests"""
import pytest


def test_safe_eval_blocks_escape():
    from app.core.safe_eval import safe_eval_bool
    assert safe_eval_bool("1 < 2") is True
    assert safe_eval_bool("score > 0.8", {"score": 0.9}) is True
    assert safe_eval_bool("x and y", {"x": True, "y": False}) is False
    # 逃逸应返回 False（异常被 strict fallback 处理）
    assert safe_eval_bool('__import__("os")') is False
    assert safe_eval_bool('().__class__') is False
    assert safe_eval_bool('open("/etc/passwd")') is False


def test_utc_now():
    from app.core.time import utc_now, utc_now_naive
    now = utc_now()
    assert now.tzinfo is not None
    assert now.tzname() == "UTC"
    naive = utc_now_naive()
    assert naive.tzinfo is None


def test_rate_limiter():
    from app.core.security_utils import RateLimiter
    rl = RateLimiter(max_attempts=3, window_sec=60)
    rl.hit("a")
    rl.hit("a")
    rl.hit("a")
    with pytest.raises(Exception):
        rl.check("a")
    rl.reset("a")
    rl.check("a")  # no raise


def test_jwt_utils():
    from app.core.security import create_token, decode_token
    token = create_token(user_id=42)
    uid = decode_token(token)
    assert uid == 42
