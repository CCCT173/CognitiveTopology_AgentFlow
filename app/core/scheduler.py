"""APScheduler 定时任务

cron 任务：
- 每日 3:00 自动备份（data/ 目录打包）
- 每小时清理过期 ws_dir (~/.agentflow/ws/* 超过 7 天)
- 每小时清理过期 span
- 每小时回收 orphan job（heartbeat 超时）
- 每 30 分钟 HITL pending 过期标记
- 每日 3:30 清理过期 refresh token
"""
from __future__ import annotations
import logging
import os
from pathlib import Path
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _backup_daily():
    """每日备份（调用 CLI backup_create）"""
    try:
        import datetime as _dt
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        from app.cli import backup_create
        backup_create(name=f"scheduled_{stamp}")
        logger.info(f"[scheduler] daily backup completed: {stamp}")
    except Exception as e:
        logger.error(f"[scheduler] backup failed: {e}")


def _cleanup_ws():
    """清理 ~/.agentflow/ws/* 超过 7 天未访问的"""
    try:
        import time
        ws_root = Path.home() / ".agentflow" / "ws"
        if not ws_root.exists():
            return
        cutoff = time.time() - 7 * 86400
        cleaned = 0
        for d in ws_root.iterdir():
            if not d.is_dir():
                continue
            try:
                if d.stat().st_mtime < cutoff:
                    import shutil
                    shutil.rmtree(d, ignore_errors=True)
                    cleaned += 1
            except Exception:
                pass
        if cleaned:
            logger.info(f"[scheduler] cleaned {cleaned} stale ws dirs")
    except Exception as e:
        logger.error(f"[scheduler] ws cleanup failed: {e}")


def _recover_orphan_jobs():
    """孤儿 job 恢复（heartbeat 超时）"""
    try:
        from app.core.tasks import recover_lost
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            n = recover_lost(db)
            if n:
                logger.info(f"[scheduler] recovered {n} lost jobs")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[scheduler] job recover failed: {e}")


def _expire_hitl():
    """过期 HITL pending 标记"""
    try:
        from app.services import hitl
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            n = hitl.expire_old(db)
            if n:
                logger.info(f"[scheduler] expired {n} HITL confirmations")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[scheduler] HITL expire failed: {e}")


def _cleanup_refresh_tokens():
    """清理过期 refresh token"""
    try:
        from app.services.auth_service import cleanup_expired
        from app.db.session import SessionLocal
        db = SessionLocal()
        try:
            n = cleanup_expired(db)
            if n:
                logger.info(f"[scheduler] cleaned {n} expired refresh tokens")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[scheduler] refresh cleanup failed: {e}")


def _cleanup_traces():
    """清理 30 天前的 trace/span"""
    try:
        from app.db.session import SessionLocal
        from app.models.trace import Trace, Span
        from sqlalchemy import delete
        from datetime import timedelta
        from app.core.time import utc_now_naive
        db = SessionLocal()
        try:
            cutoff = utc_now_naive() - timedelta(days=30)
            db.execute(delete(Span).where(Span.created_at < cutoff))
            db.execute(delete(Trace).where(Trace.created_at < cutoff))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[scheduler] trace cleanup failed: {e}")


def start_scheduler():
    """启动 scheduler（幂等）"""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    # 每日 3:00 备份
    _scheduler.add_job(_backup_daily, CronTrigger(hour=3, minute=0), id="backup_daily", replace_existing=True)
    # 每小时清理 ws
    _scheduler.add_job(_cleanup_ws, IntervalTrigger(hours=1), id="cleanup_ws", replace_existing=True)
    # 每小时恢复孤儿 job
    _scheduler.add_job(_recover_orphan_jobs, IntervalTrigger(hours=1), id="recover_jobs", replace_existing=True)
    # 每 30 分钟过期 HITL
    _scheduler.add_job(_expire_hitl, IntervalTrigger(minutes=30), id="expire_hitl", replace_existing=True)
    # 每日 3:30 清理 refresh token
    _scheduler.add_job(_cleanup_refresh_tokens, CronTrigger(hour=3, minute=30), id="cleanup_refresh", replace_existing=True)
    # 每日 4:00 清理 traces
    _scheduler.add_job(_cleanup_traces, CronTrigger(hour=4, minute=0), id="cleanup_traces", replace_existing=True)
    _scheduler.start()
    logger.info(f"[scheduler] started with {len(_scheduler.get_jobs())} jobs")
    return _scheduler


def shutdown_scheduler():
    """关闭 scheduler"""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
