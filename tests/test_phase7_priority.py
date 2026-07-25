"""Phase 7 高优先级测试: platform tools 补齐 + SSE + JWT refresh"""
import pytest


def test_platform_tools_registered():
    """Platform tools 应包含 agent/skill/kb 相关工具"""
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry, TOOL_TYPE_PLATFORM
    r = get_registry()
    names = r.names({TOOL_TYPE_PLATFORM})
    # workflow 5 个 + agent 3 + skill 2 + kb 2 = 12
    expected = [
        "list_workflows", "get_workflow", "create_workflow", "update_workflow", "delete_workflow",
        "list_agents", "get_agent", "toggle_agent",
        "list_skills", "toggle_skill",
        "list_knowledge_bases", "kb_stats",
    ]
    for name in expected:
        assert name in names, f"{name} not registered"
    print(f"  {len(names)} platform tools registered")


def test_platform_list_agents():
    """list_agents 工具返回数据"""
    import sys; sys.path.insert(0, ".")
    import pytest
    from app.tools import get_registry
    r = get_registry()
    res = r.get("list_agents").run()
    if not res.ok and ("Connection" in (res.error or "") or "denied" in (res.error or "")):
        pytest.skip(f"DB not available: {res.error}")
    assert res.ok, res.error
    assert res.data["count"] >= 0


def test_platform_list_kbs():
    """list_knowledge_bases 工具返回数据"""
    import sys; sys.path.insert(0, ".")
    import pytest
    from app.tools import get_registry
    r = get_registry()
    res = r.get("list_knowledge_bases").run()
    if not res.ok and ("Connection" in (res.error or "") or "denied" in (res.error or "")):
        pytest.skip(f"DB not available: {res.error}")
    assert res.ok, res.error


def test_sse_stream_endpoint_returns_events():
    """SSE /meta/chat/stream 返回事件序列"""
    import sys; sys.path.insert(0, ".")
    import asyncio, json, httpx
    from app.main import create_app

    async def run():
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
            assert r.status_code == 200
            token = r.json()["data"]["token"]
            h = {"Authorization": f"Bearer {token}"}
            events = []
            async with c.stream("POST", "/api/v1/meta/chat/stream",
                                  json={"message": "ping"}, headers=h, timeout=60) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        ev = json.loads(data)
                        events.append(ev["type"])
            assert "done" in events, f"missing done event: {events}"
            # 至少有一个 iter_start/iter_end
            assert "iter_start" in events
            return events

    events = asyncio.run(run())
    print(f"  events: {events}")


def test_jwt_refresh_flow():
    """登录 → refresh → 旧 token 失效 → logout"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        # 登录
        r = c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["token"]
        assert d["refresh_token"]
        assert d["expires_in"] > 0  # access token ttl 秒
        # 用 access 访问 /me
        r = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {d['token']}"})
        assert r.status_code == 200
        # refresh
        r = c.post("/api/v1/auth/refresh", json={"refresh_token": d["refresh_token"]})
        assert r.status_code == 200, r.text
        d2 = r.json()["data"]
        # refresh token 必须轮换（安全关键）
        assert d2["refresh_token"] != d["refresh_token"]
        assert d2["token"]
        # 旧 refresh 不能再用（rotation）
        r = c.post("/api/v1/auth/refresh", json={"refresh_token": d["refresh_token"]})
        assert r.status_code == 401
        # 新 access 可用
        r = c.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {d2['token']}"})
        assert r.status_code == 200
        # logout
        r = c.post("/api/v1/auth/logout",
                   json={"refresh_token": d2["refresh_token"]},
                   headers={"Authorization": f"Bearer {d2['token']}"})
        assert r.status_code == 200
        # 已登出的 refresh 不能再用
        r = c.post("/api/v1/auth/refresh", json={"refresh_token": d2["refresh_token"]})
        assert r.status_code == 401
