"""Phase 3 测试: jobs, traces, versioning"""
import pytest


def test_new_models_import():
    import sys; sys.path.insert(0, ".")
    from app.models.job import Job
    from app.models.trace import Trace, Span
    from app.models.versioning import ActivityLog, WorkflowVersion, AgentVersion
    assert Job.__tablename__ == "jobs"
    assert Trace.__tablename__ == "traces"
    assert Span.__tablename__ == "spans"
    assert ActivityLog.__tablename__ == "activity_logs"
    assert WorkflowVersion.__tablename__ == "workflow_versions"


def test_tables_created_sqlite():
    import sys; sys.path.insert(0, ".")
    from sqlalchemy import create_engine, inspect
    from app.db.session import Base
    import app.models  # noqa
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    for t in ("jobs", "traces", "spans", "activity_logs", "workflow_versions", "agent_versions"):
        assert t in tables, f"missing table: {t}"


def test_enqueue_and_run_task():
    """enqueue 应该能创建 Job 并异步执行（在 running loop 中）"""
    import sys, asyncio; sys.path.insert(0, ".")
    from app.core.tasks import TASK_REGISTRY, register_task, enqueue, recover_lost
    from app.db.session import SessionLocal, init_db
    init_db()

    calls = []
    @register_task("test-task")
    def _do(params):
        calls.append(params)
        return {"done": True}

    async def _test():
        db = SessionLocal()
        try:
            job = enqueue("test-task", {"x": 1}, db=db)
            assert job.id is not None
            # 等待后台协程
            for _ in range(50):
                db.expire_all()
                j = db.get(type(job), job.id)
                if j.status in ("done", "failed"):
                    return j, job
                await asyncio.sleep(0.1)
            return j, job
        finally:
            db.close()

    j, job = asyncio.run(_test())
    assert j.status == "done", f"expected done got {j.status}: {j.error}"
    assert len(calls) == 1
    # 清理注册表
    TASK_REGISTRY.pop("test-task", None)


def test_versioning_publish_workflow():
    import sys; sys.path.insert(0, ".")
    from app.db.session import SessionLocal, init_db
    from app.models.workflow import Workflow
    from app.services.versioning import publish_workflow
    from app.core.time import utc_now_naive
    init_db()
    db = SessionLocal()
    try:
        wf = Workflow(name="v-test-wf", description="", category="",
                     definition={"nodes": []}, created_by=1)
        db.add(wf); db.commit(); db.refresh(wf)
        wv = publish_workflow(db, wf, user_id=1, changelog="initial")
        db.commit()
        assert wv.version == 1
        assert wv.workflow_id == wf.id
        assert '"nodes": []' in wv.definition_json
    finally:
        db.close()
