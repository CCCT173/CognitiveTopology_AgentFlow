"""
时间工具: 统一使用 UTC aware datetime。
- 禁止 utc_now() (Python 3.12 已弃用,返回 naive datetime)
- 禁止 utc_now() 不带 timezone (会被本地时区污染)
- 用 utc_now() 获取当前 UTC 时间
- 用 to_utc() 把 naive datetime 转为 UTC aware
"""
from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """返回当前 UTC 时间 (timezone-aware)。所有数据库默认时间/日志时间都用这个。"""
    return datetime.now(timezone.utc)


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """把 naive datetime 当作 UTC 标记; aware datetime 直接返回; None 透传。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def utc_now_naive() -> datetime:
    """返回当前 UTC 时间但去掉 tzinfo,用于 SQLAlchemy default (部分 DB/dialect 不兼容 aware)。"""
    return utc_now().replace(tzinfo=None)
