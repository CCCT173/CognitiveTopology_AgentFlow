"""
异步后台任务执行器
- enqueue(name, params) -> Job: 创建任务记录并异步执行
- _recover_lost(): 启动时把长时间 heartbeat 的 running 任务标为 lost
- 任务函数从 TASK_REGISTRY 注册
"""
from __future__ import annotations

import asyncio
import json
import traceback
import uuid
from datetime import timedelta
from typing import Any, Callable, Coroutine

from sqlalchemy import select, update as sa_update
from app.core.time import utc_now_naive
from app.db.session import SessionLocal
from app.models.job import Job


# 任务名 -> 协程函数（同步函数自动包线程池）
TASK_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_task(name: str):
    """装饰器：注册后台任务"""
    def deco(fn):
        TASK_REGISTRY[name] = fn
        return fn
    return deco


def enqueue(name: str, params: dict | None = None, db=None) -> Job:
    """写入 jobs 表并启动 asyncio task 执行。
    若无 running event loop（CLI/脚本场景），则任务保持 pending，等 scheduler/lifespan 启动后由 recover_lost 重跑。
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        job = Job(name=name, params_json=json.dumps(params or {}, ensure_ascii=False),
                  status="pending")
        db.add(job)
        db.commit()
        db.refresh(job)
    finally:
        if close_db:
            db.close()

    # 启动后台协程（仅在有 running loop 时，即 lifespan 内）
    try:
        running_loop = asyncio.get_running_loop()
        asyncio.ensure_future(_run_job(job.id))
    except RuntimeError:
        # 无 running loop，任务保持 pending，下次 scheduler 恢复时处理
        pass
    return job


async def _run_job(job_id: int):
    """异步执行任务：更新状态 -> 调 handler -> 写结果"""
    def _sync():
        db = SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return None, None, None
            handler = TASK_REGISTRY.get(job.name)
            return db, job, handler
        except Exception:
            db.close()
            raise

    loop = asyncio.get_event_loop()
    db, job, handler = await loop.run_in_executor(None, _sync)
    if not job:
        return

    if not handler:
        job.status = "failed"
        job.error = f"未注册的任务: {job.name}"
        job.finished_at = utc_now_naive()
        db.commit()
        db.close()
        return

    # 标记 running
    job.status = "running"
    job.started_at = utc_now_naive()
    job.heartbeat_at = job.started_at
    job.locked_by = f"local-{uuid.uuid4().hex[:8]}"
    db.commit()

    try:
        params = job.params
        if asyncio.iscoroutinefunction(handler):
            result = await handler(params)
        else:
            result = await loop.run_in_executor(None, lambda: handler(params))
        job.status = "done"
        job.result_json = json.dumps(result, ensure_ascii=False, default=str) if result is not None else ""
    except Exception as e:
        job.status = "failed"
        job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
    finally:
        job.finished_at = utc_now_naive()
        db.commit()
        db.close()


def recover_lost(timeout_sec: int = 600):
    """启动时把 heartbeat 超过 timeout 的 running 任务标为 lost"""
    db = SessionLocal()
    try:
        cutoff = utc_now_naive() - timedelta(seconds=timeout_sec)
        db.execute(
            sa_update(Job)
            .where(Job.status == "running", Job.heartbeat_at < cutoff)
            .values(status="lost", error="heartbeat 超时，任务可能已崩溃", finished_at=utc_now_naive())
        )
        db.commit()
    finally:
        db.close()
