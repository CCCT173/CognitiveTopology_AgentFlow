"""
SQLAlchemy 列类型：跨数据库兼容
- BigInteger 主键在 SQLite 上需要用 Integer 才能自增
- 提供 pk_column() helper
"""
from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import mapped_column


def pk_column():
    """64 位主键：MySQL/PG 用 BigInteger，SQLite 用 Integer（否则 SQLite 不自增）"""
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


def fk_column(ref: str, **kw):
    """BigInteger 外键（SQLite 自动用 Integer）"""
    return mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        ForeignKey(ref),
        **kw,
    )


# 需要 ForeignKey import
from sqlalchemy import ForeignKey  # noqa: E402
