"""Phase 4 测试: MetaRunner HTTP API (鉴权)"""
import pytest


def _auth_headers(client):
    """登录 admin/admin123 获取 token"""
    r = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
    if r.status_code != 200:
        pytest.skip(f"login failed: {r.status_code} {r.text[:100]}")
    token = r.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_meta_chat_requires_auth():
    """不带 token 应返回 401"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.post("/api/v1/meta/chat", json={"message": "hi"})
        assert r.status_code in (401, 403)


def test_meta_chat_endpoint_exists():
    """带 token 端点正常响应"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        headers = _auth_headers(client)
        r = client.post("/api/v1/meta/chat", json={"message": "hi"}, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert "reply" in data["data"]
        assert "tool_calls" in data["data"]
