"""Phase 5 测试: HITL 确认机制 + L0 Host 工具"""
import pytest


def test_hitl_confirm_deny_flow():
    """完整流程：创建 pending → confirm 真正执行 → 校验结果"""
    import sys; sys.path.insert(0, ".")
    from app.db.session import SessionLocal, init_db
    from app.services import hitl
    from app.tools import get_registry
    from app.models.hitl import PendingConfirmation
    from sqlalchemy import select
    init_db()
    r = get_registry()
    db = SessionLocal()
    try:
        # 先建一个工作流
        res = r.get("create_workflow").run(name="hitl-test", description="x", category="t")
        assert res.ok
        import json
        wid = json.loads(res.output)["id"]
        # 创建 pending
        pc = hitl.create_confirmation(
            db, user_id=1, tool_name="delete_workflow",
            args={"workflow_id": wid},
            summary=f"删除工作流 #{wid}",
            risk_level="high",
        )
        assert pc.id > 0
        assert pc.status == "pending"
        # 确认前工作流还在
        assert r.get("get_workflow").run(workflow_id=wid).ok
        # confirm
        res = hitl.confirm(db, pc.id, user_id=1)
        assert res["ok"] is True
        assert res["result"]["ok"] is True
        # 工作流被删
        assert not r.get("get_workflow").run(workflow_id=wid).ok
        # 状态变更
        db.expire_all()
        pc2 = db.get(PendingConfirmation, pc.id)
        assert pc2.status == "confirmed"
    finally:
        db.close()


def test_hitl_deny_flow():
    """拒绝后不执行"""
    import sys; sys.path.insert(0, ".")
    from app.db.session import SessionLocal, init_db
    from app.services import hitl
    from app.tools import get_registry
    init_db()
    r = get_registry()
    db = SessionLocal()
    try:
        res = r.get("create_workflow").run(name="hitl-deny", description="x", category="t")
        import json; wid = json.loads(res.output)["id"]
        pc = hitl.create_confirmation(
            db, user_id=1, tool_name="delete_workflow",
            args={"workflow_id": wid}, summary=f"del #{wid}",
        )
        # deny
        res = hitl.deny(db, pc.id, user_id=1, reason="不要删")
        assert res["ok"] is True
        # 工作流还在
        assert r.get("get_workflow").run(workflow_id=wid).ok
    finally:
        db.close()


def test_host_read_path_isolation():
    """Host 工具路径越界被拦截"""
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry
    r = get_registry()
    # 白名单内（项目根目录）OK
    res = r.get("host_list_dir").run(path=".")
    assert res.ok, f"list . failed: {res.error}"
    # 白名单外被拒
    res = r.get("host_read").run(path="C:/Windows/System32/drivers/etc/hosts")
    assert not res.ok
    assert "越界" in (res.error or "")


def test_metarunner_wraps_dangerous_tools():
    """MetaRunner 应拦截 requires_confirmation=True 的工具"""
    import sys; sys.path.insert(0, ".")
    from app.db.session import SessionLocal, init_db
    from app.services.meta_runner import (
        build_meta_context, MetaRunner, TOOL_TYPE_PLATFORM, TOOL_TYPE_CODE, TOOL_TYPE_BUILTIN,
    )
    from app.tools import get_registry
    from app.models.hitl import PendingConfirmation
    init_db()
    r = get_registry()
    db = SessionLocal()
    try:
        res = r.get("create_workflow").run(name="wrap-test", description="x", category="t")
        import json; wid = json.loads(res.output)["id"]
        runner = MetaRunner()
        ctx = build_meta_context(f"del {wid}", db=db, user_id=1, thread_id="t")
        visible = r.list({TOOL_TYPE_PLATFORM, TOOL_TYPE_CODE, TOOL_TYPE_BUILTIN})
        restore = runner._wrap_dangerous_tools(ctx, visible)
        try:
            wrapped = r.get("delete_workflow")
            out = wrapped.run(ctx, workflow_id=wid)
            assert "需要用户确认" in out
            assert len(runner.pending_confirmations) == 1
        finally:
            restore()
        # 工作流还在
        assert r.get("get_workflow").run(workflow_id=wid).ok
    finally:
        db.close()


def test_hitl_api_endpoints():
    """HITL HTTP 端点：无 token 返回 401，带 token 正常"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        # 无 token
        r = c.get("/api/v1/hitl/pending")
        assert r.status_code in (401, 403)
        # 登录
        r = c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        assert r.status_code == 200
        token = r.json()["data"]["token"]
        h = {"Authorization": f"Bearer {token}"}
        # list pending
        r = c.get("/api/v1/hitl/pending", headers=h)
        assert r.status_code == 200
        assert isinstance(r.json()["data"], list)
