"""MetaRunner / Platform tools 测试"""
import pytest


def test_platform_tools_registered():
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry, TOOL_TYPE_PLATFORM
    tools = get_registry().list({TOOL_TYPE_PLATFORM})
    names = sorted(t.name for t in tools)
    for expected in ["list_workflows", "get_workflow", "create_workflow",
                      "update_workflow", "delete_workflow"]:
        assert expected in names


def test_create_list_workflow_crud():
    """此测试需要运行中的数据库 (MySQL 或 SQLite)"""
    import sys; sys.path.insert(0, ".")
    import pytest
    from app.tools import get_registry
    from app.db.session import SessionLocal, init_db, engine
    from sqlalchemy import text
    # 检查数据库可连接
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        pytest.skip("database not available")
    # 确保表都建了
    init_db()
    import random, string
    reg = get_registry()
    db = SessionLocal()
    try:
        suffix = "".join(random.choices(string.ascii_lowercase, k=6))
        r = reg.get("create_workflow").run(name=f"AI-workflow-{suffix}",
                                           description="由测试创建", category="test")
        assert r.ok, f"create failed: {r.error}"
        import json
        wf = json.loads(r.output)
        wf_id = wf["id"]
        r2 = reg.get("list_workflows").run(keyword=suffix)
        assert r2.ok
        assert str(wf_id) in r2.output or suffix in r2.output
        r3 = reg.get("get_workflow").run(workflow_id=wf_id)
        assert r3.ok
        r4 = reg.get("update_workflow").run(workflow_id=wf_id, description="更新后")
        assert r4.ok
        r5 = reg.get("delete_workflow").run(workflow_id=wf_id)
        assert r5.ok
    finally:
        db.close()


def test_meta_agent_context():
    import sys; sys.path.insert(0, ".")
    from app.services.meta_runner import MetaRunner, build_meta_context, MetaAgent
    runner = MetaRunner()
    ctx = build_meta_context("列出所有工作流", thread_id="test-thread")
    # runner.run 时才注入工具，提前验证 agent 类型
    assert isinstance(ctx.agent, MetaAgent)
    assert ctx.thread_id == "test-thread"
