"""
FastAPI 应用工厂
"""
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestContextMiddleware
from app.core.audit_middleware import AuditLogMiddleware
from app.core.rate_limit_middleware import RateLimitMiddleware
from app.core.config_check import validate_config
from app.api.v1.router import api_router
from app.db.session import init_db, SessionLocal, AsyncSessionLocal
from app.core.security import hash_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")
    validate_config()
    init_db()
    await _seed_super_admin()
    await _load_system_config()
    # APScheduler（dev/prod 启动；test 环境跳过）
    if settings.APP_ENV != "test":
        from app.core.scheduler import start_scheduler, shutdown_scheduler
        try:
            start_scheduler()
        except Exception as e:
            logger.warning(f"scheduler start failed: {e}")
    yield
    if settings.APP_ENV != "test":
        from app.core.scheduler import shutdown_scheduler
        shutdown_scheduler()
    logger.info("Shutdown")


async def _seed_super_admin():
    """启动时若无 super_admin 则创建默认超级管理员 admin/admin123"""
    from app.models.user import User
    from sqlalchemy import select, func
    
    # 如果异步引擎不可用，回退到同步模式
    if AsyncSessionLocal is None:
        db = SessionLocal()
        try:
            exists = db.scalar(select(User).where(User.role == "super_admin"))
            if not exists:
                next_id = db.scalar(select(func.coalesce(func.max(User.user_id), 0))) + 1
                admin = User(
                    user_id=next_id,
                    username="超级管理员",
                    account="admin",
                    email="admin@local",
                    password_hash=hash_password("admin123"),
                    role="super_admin",
                )
                db.add(admin)
                db.commit()
                logger.warning("已创建默认超级管理员: admin / admin123 (请尽快修改密码)")
        except Exception as e:
            logger.warning(f"创建默认管理员失败（可能数据库已有数据）: {e}")
            db.rollback()
        finally:
            db.close()
        return
    
    # 异步模式
    async with AsyncSessionLocal() as db:
        try:
            exists = await db.scalar(select(User).where(User.role == "super_admin"))
            if not exists:
                next_id = (await db.scalar(select(func.coalesce(func.max(User.user_id), 0)))) + 1
                admin = User(
                    user_id=next_id,
                    username="超级管理员",
                    account="admin",
                    email="admin@local",
                    password_hash=hash_password("admin123"),
                    role="super_admin",
                )
                db.add(admin)
                await db.commit()
                logger.warning("已创建默认超级管理员: admin / admin123 (请尽快修改密码)")
        except Exception as e:
            logger.warning(f"创建默认管理员失败（可能数据库已有数据）: {e}")
            await db.rollback()


async def _load_system_config():
    """启动时从 DB 加载 system_config 到内存缓存，供 LLM 服务层读取"""
    # 如果异步引擎不可用，回退到同步模式
    if AsyncSessionLocal is None:
        db = SessionLocal()
        try:
            from app.services import system_config_service as cfg_svc
            cfg_svc.load_config(db)
        except Exception as e:
            logger.warning(f"加载 system_config 失败（可能表尚未创建）: {e}")
        finally:
            db.close()
        return
    
    # 异步模式
    async with AsyncSessionLocal() as db:
        try:
            from app.services import system_config_service as cfg_svc
            cfg_svc.load_config(db)
        except Exception as e:
            logger.warning(f"加载 system_config 失败（可能表尚未创建）: {e}")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="多Agent + RAG 资料库平台",
        lifespan=lifespan,
    )

    # CORS (从 .env CORS_ORIGINS 读取,逗号分隔; * = 全部)
    origins_raw = settings.CORS_ORIGINS.strip()
    if origins_raw == "*":
        allow_origins = ["*"]
    else:
        allow_origins = [o.strip() for o in origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理
    register_exception_handlers(app)

    # Request-ID + 访问日志中间件
    app.add_middleware(RequestContextMiddleware)

    # 全局 IP 限流 (100 req/min)
    app.add_middleware(RateLimitMiddleware)

    # Trace/Span 记录（HTTP 请求 -> traces/spans 表）
    from app.core.trace_middleware import TraceMiddleware
    app.add_middleware(TraceMiddleware)

    # 操作审计日志中间件 (自动记录 POST/PATCH/PUT/DELETE)
    app.add_middleware(AuditLogMiddleware)

    # 路由
    app.include_router(api_router)

    # 静态文件: /files 映射到 uploads/ (图标/上传文件访问)
    upload_dir = str(settings.upload_dir_abs)
    app.mount("/files", StaticFiles(directory=upload_dir), name="files")

    @app.get("/health", tags=["系统"])
    def health():
        return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    return app


app = create_app()
