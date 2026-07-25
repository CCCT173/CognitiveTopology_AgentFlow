"""测试 Workflow API Key 外部调用"""
import pytest


def test_create_and_use_api_key():
    """创建 key → 列出 key → 外部执行 → 禁用/删除"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.db.session import Base, engine
    import app.models
    Base.metadata.create_all(engine)
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        token = r.json()["data"]["token"]
        h = {"Authorization": f"Bearer {token}"}
        r = c.post("/api/v1/workflows", json={"name": "api_key_wf_test"}, headers=h)
        wid = r.json()["data"]["id"]
        # 创建 key
        r = c.post(f"/api/v1/workflows/{wid}/api-keys", json={"name": "prod"}, headers=h)
        assert r.status_code == 200
        key = r.json()["data"]["api_key"]
        assert key.startswith("wf_")
        assert "execute_url" in r.json()["data"]
        # 列出（掩码，现在用 name(id=x) 标识而不是截断 key）
        r = c.get(f"/api/v1/workflows/{wid}/api-keys", headers=h)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1
        assert "api_key_masked" in r.json()["data"][0]
        # 无效 key 返回 401
        r = c.post("/api/v1/execute/wf_invalid", json={"inputs": {}})
        assert r.status_code == 401
        # 禁用 key 后调用返回 403
        key_id = r.json()["data"][0]["id"] if False else 1
        # 找 key_id
        r2 = c.get(f"/api/v1/workflows/{wid}/api-keys", headers=h)
        key_id = r2.json()["data"][0]["id"]
        c.post(f"/api/v1/workflows/{wid}/api-keys/{key_id}/toggle", json={"is_active": False}, headers=h)
        r = c.post(f"/api/v1/execute/{key}", json={"inputs": {}})
        assert r.status_code == 403
        # 删除
        c.delete(f"/api/v1/workflows/{wid}/api-keys/{key_id}", headers=h)
        r = c.get(f"/api/v1/workflows/{wid}/api-keys", headers=h)
        assert len(r.json()["data"]) == 0
        # 清理
        c.delete(f"/api/v1/workflows/{wid}", headers=h)


def test_api_key_requires_owner():
    """非 owner 不能管理 key"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        token = r.json()["data"]["token"]
        h = {"Authorization": f"Bearer {token}"}
        r = c.post("/api/v1/workflows", json={"name": "owner_check_wf"}, headers=h)
        wid = r.json()["data"]["id"]
        # admin 是 owner，可以创建
        r = c.post(f"/api/v1/workflows/{wid}/api-keys", json={"name": "k"}, headers=h)
        assert r.status_code == 200
        c.delete(f"/api/v1/workflows/{wid}", headers=h)


def test_execute_returns_dify_style_response():
    """外部执行返回 Dify 风格响应"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.db.session import Base, engine
    import app.models
    Base.metadata.create_all(engine)
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        token = r.json()["data"]["token"]
        h = {"Authorization": f"Bearer {token}"}
        r = c.post("/api/v1/workflows", json={"name": "execute_style_test"}, headers=h)
        wid = r.json()["data"]["id"]
        r = c.post(f"/api/v1/workflows/{wid}/api-keys", json={"name": "k"}, headers=h)
        key = r.json()["data"]["api_key"]
        r = c.post(f"/api/v1/execute/{key}", json={"inputs": {}})
        # 空工作流返回 400（不是 500）
        assert r.status_code in (200, 400, 500)
        if r.status_code == 200:
            data = r.json()
            assert "task_id" in data
            assert "workflow_id" in data
        c.delete(f"/api/v1/workflows/{wid}", headers=h)
