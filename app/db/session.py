"""
SQLAlchemy 引擎与会话
- 支持运行时切换 DATABASE_URL（测试用 sqlite）
- 支持同步和异步会话
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings


def _create_engine(url: str | None = None):
    """创建同步 engine。SQLite 用专属参数"""
    db_url = url or settings.DATABASE_URL
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    kwargs: dict = dict(echo=False, pool_pre_ping=True)
    if not db_url.startswith("sqlite"):
        kwargs.update(pool_recycle=3600, pool_size=5, max_overflow=10)
    return create_engine(db_url, connect_args=connect_args, **kwargs)


def _create_async_engine(url: str | None = None):
    """创建异步 engine。根据数据库类型选择合适的异步驱动"""
    db_url = url or settings.DATABASE_URL
    
    if db_url.startswith("sqlite://"):
        # SQLite 异步 URL 需要使用 sqlite+aiosqlite://
        db_url = "sqlite+aiosqlite://" + db_url[len("sqlite://"):]
        connect_args = {"check_same_thread": False}
    elif db_url.startswith("mysql+pymysql://"):
        # MySQL 异步 URL 需要使用 mysql+aiomysql://
        db_url = "mysql+aiomysql://" + db_url[len("mysql+pymysql://"):]
        connect_args = {}
    else:
        connect_args = {}
    
    kwargs: dict = dict(echo=False)
    if not db_url.startswith("sqlite"):
        kwargs.update(pool_recycle=3600, pool_size=5, max_overflow=10)
    
    try:
        return create_async_engine(db_url, connect_args=connect_args, **kwargs)
    except Exception as e:
        # 如果异步驱动不可用，记录警告但不阻塞启动
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"无法创建异步数据库引擎: {e}")
        logger.warning("异步功能可能受限，请安装 aiosqlite（SQLite）或 aiomysql（MySQL）")
        return None


engine = _create_engine()
_SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

# 异步 engine 和 session（如果异步驱动不可用则为 None）
async_engine = _create_async_engine()
_AsyncSessionLocal = async_sessionmaker(bind=async_engine, autoflush=False, autocommit=False, expire_on_commit=False) if async_engine else None


def _make_session_local(bind=None):
    return sessionmaker(bind=bind or engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _make_async_session_local(bind=None):
    return async_sessionmaker(bind=bind or async_engine, autoflush=False, autocommit=False, expire_on_commit=False)


# 默认 SessionLocal（生产用）
SessionLocal = _SessionLocal
AsyncSessionLocal = _AsyncSessionLocal


def _reload_engine(url: str | None = None):
    """测试用：切换 engine 和 SessionLocal 到指定 URL"""
    global engine, SessionLocal, async_engine, AsyncSessionLocal
    engine = _create_engine(url)
    SessionLocal = _make_session_local(engine)
    async_engine = _create_async_engine(url)
    AsyncSessionLocal = _make_async_session_local(async_engine) if async_engine else None
    return engine


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""
    pass


def get_db():
    """FastAPI 依赖: 每个请求一个同步会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """FastAPI 依赖: 每个请求一个异步会话"""
    async with AsyncSessionLocal() as db:
        yield db


def init_db():
    """启动时校验数据库状态。
    - SQLite 新库：直接 create_all（简单、跨 schema 兼容）
    - 非 SQLite 且无 alembic_version：警告提示手动 migrate
    - 其他：交由 Alembic 管理（不 create_all）
    """
    import logging
    import os
    logger = logging.getLogger(__name__)
    from sqlalchemy import inspect

    insp = inspect(engine)
    tables = insp.get_table_names()
    has_alembic = "alembic_version" in tables

    if not tables:
        # 空库（任意 DB 类型）：Base.metadata.create_all + alembic stamp head。
        # SQLAlchemy 按 FK 依赖拓扑排序建表，MySQL/PG/SQLite 均可工作。
        # alembic 的 init_schema 迁移是增量 diff、不含核心表（users/agents/work_groups 等），
        # 无法独立建库，故统一走 create_all 路径。
        is_sqlite = settings.DATABASE_URL.startswith("sqlite")
        logger.info(
            "Empty %s DB detected, creating tables via metadata.create_all "
            "(FK-topological order, safe for all engines)",
            "SQLite" if is_sqlite else "non-SQLite",
        )
        # 导入所有模型以注册 metadata
        from app.models import user, agent, rag, group, workflow, skill, audit  # noqa: F401
        Base.metadata.create_all(bind=engine)
        # 标记 alembic_version 为 head（让后续迁移能正常接力）
        from alembic.config import Config
        from alembic import command
        cfg = Config(os.path.join(os.path.dirname(__file__), "../../alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.stamp(cfg, "head")
        logger.info("Schema created and stamped at alembic head.")
    elif not has_alembic:
        logger.warning(
            "DB has tables but no alembic_version. Auto-stamping at head "
            "so future migrations can proceed."
        )
        from alembic.config import Config
        from alembic import command
        cfg = Config(os.path.join(os.path.dirname(__file__), "../../alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
        command.stamp(cfg, "head")
