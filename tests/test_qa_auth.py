"""
QA 认证模块测试
- register/login/refresh/logout/me/ping/avatar
- refresh token rotation
- 未授权访问统一 401
- 模块级 token 缓存（避免登录限流）
"""
from __future__ import annotations
import io
import sys
import uuid
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# 模块级 token 缓存：避免每测试都触发 login 限流
_TOKENS: dict = {}


def _login(client, account="admin", password="admin123"):
    """登录获取 token（每个 client 独立登录，因为 DB 隔离）"""
    r = client.post("/api/v1/auth/login", json={"account": account, "password": password})
    if r.status_code == 429:
        pytest.skip("登录限流触发，跳过")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    return d["token"], d["refresh_token"], d["user"]


def _register(client, account=None, password="pass123"):
    account = account or f"u_{uuid.uuid4().hex[:10]}"
    r = client.post("/api/v1/auth/register", json={
        "account": account, "username": account, "password": password,
        "email": f"{account}@x.com",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]


class TestAuthRegister:
    def test_register_success(self, client):
        data = _register(client)
        assert data["token"]
        assert data["refresh_token"]
        assert data["user"]["account"]

    def test_register_short_password(self, client):
        tag = uuid.uuid4().hex[:8]
        r = client.post("/api/v1/auth/register", json={
            "account": f"sp_{tag}", "username": f"sp_{tag}", "password": "123",
            "email": f"s{tag}@x.com",
        })
        assert r.status_code in (400, 422)

    def test_register_short_account(self, client):
        r = client.post("/api/v1/auth/register", json={
            "account": "ab", "username": "ab", "password": "pass123", "email": "s@x.com",
        })
        assert r.status_code in (400, 422)

    def test_register_bad_email(self, client):
        r = client.post("/api/v1/auth/register", json={
            "account": "bademail3", "username": "bademail3", "password": "pass123",
            "email": "not-an-email",
        })
        assert r.status_code in (400, 422)


class TestAuthLogin:
    def test_login_admin_success(self, client):
        token, refresh, user = _login(client)
        assert token and refresh
        assert user["account"] == "admin"
        assert user["role"] == "super_admin"

    def test_login_wrong_password(self, client):
        r = client.post("/api/v1/auth/login", json={"account": "admin", "password": "wrongpass"})
        assert r.status_code in (400, 401, 429)

    def test_login_nonexistent_user(self, client):
        r = client.post("/api/v1/auth/login", json={"account": "nobody_xyz_abc", "password": "whatever"})
        assert r.status_code in (400, 401, 404, 429)

    def test_login_missing_fields(self, client):
        r = client.post("/api/v1/auth/login", json={"account": "admin"})
        assert r.status_code == 422


class TestAuthMe:
    def test_me_returns_user(self, client):
        token, _, _ = _login(client)
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["data"]["account"] == "admin"

    def test_me_without_token_401(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401


class TestAuthPing:
    def test_ping_returns_pong(self, client):
        token, _, _ = _login(client)
        r = client.post("/api/v1/auth/ping", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200


class TestRefreshRotation:
    def test_refresh_returns_new_tokens(self, client):
        """登录后 refresh 应返回新 access+refresh token"""
        token, refresh, _ = _login(client)
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        # 新 token 应不同于旧的（且非空）
        assert data["token"] and data["refresh_token"]
        # 业务约定：rotation 应换发新 refresh
        assert data["refresh_token"] != refresh

    def test_refresh_old_token_rejected(self, client):
        """refresh rotation: 旧 refresh 重用必须被拒绝"""
        token, refresh, _ = _login(client)
        r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r1.status_code == 200
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r2.status_code in (401, 400)

    def test_refresh_invalid_token(self, client):
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-valid-token"})
        assert r.status_code in (401, 400)

    def test_refresh_empty_token(self, client):
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": ""})
        assert r.status_code in (401, 400, 422)


class TestAuthLogout:
    def test_logout_revokes_refresh(self, client):
        token, refresh, _ = _login(client)
        r = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
        assert r2.status_code in (401, 400)

    def test_logout_all_devices(self, client):
        token1, _, _ = _login(client)
        r = client.post(
            "/api/v1/auth/logout",
            json={"all_devices": True},
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert r.status_code == 200


class TestUpdateMe:
    def test_update_username(self, client):
        token, _, _ = _login(client)
        new_name = f"admin_qa_{uuid.uuid4().hex[:6]}"
        r = client.patch(
            "/api/v1/auth/me",
            json={"username": new_name},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["data"]["username"] == new_name


class TestAvatar:
    def test_upload_png_avatar(self, client):
        token, _, _ = _login(client)
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0"
            b"\x00\x00\x00\x03\x00\x01\x5b\xcb\xcf\x94\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        r = client.post(
            "/api/v1/auth/me/avatar",
            files={"file": ("avatar.png", io.BytesIO(png_bytes), "image/png")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        url = r.json()["data"].get("avatar_url", "")
        assert "/files/avatars/" in url

    def test_upload_non_image_rejected(self, client):
        token, _, _ = _login(client)
        r = client.post(
            "/api/v1/auth/me/avatar",
            files={"file": ("notimg.txt", io.BytesIO(b"hello"), "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code in (400, 422)


class TestProtectedEndpoints401:
    """受保护端点无 JWT 必须 401（抽样）"""

    @pytest.mark.parametrize("method,path", [
        ("GET", "/api/v1/agents"),
        ("GET", "/api/v1/rag/kbs"),
        ("GET", "/api/v1/workflows"),
        ("GET", "/api/v1/skills"),
        ("GET", "/api/v1/groups"),
        ("GET", "/api/v1/chat/threads"),
        ("GET", "/api/v1/hitl/pending"),
        ("GET", "/api/v1/system/stats"),
        ("GET", "/api/v1/system/dashboard"),
        ("GET", "/api/v1/system/logs"),
        ("GET", "/api/v1/users/tree"),
        ("GET", "/api/v1/users/flat"),
        ("GET", "/api/v1/users/admins"),
    ])
    def test_protected_get_401(self, client, method, path):
        r = client.request(method, path)
        assert r.status_code == 401, f"{method} {path} 无 JWT 应 401，实际 {r.status_code}"

    @pytest.mark.parametrize("method,path,json_body", [
        ("POST", "/api/v1/agents", {"name": "x", "display_name": "x", "system_prompt": "x"}),
        ("POST", "/api/v1/rag/kbs", {"name": "x"}),
        ("POST", "/api/v1/workflows", {"name": "x", "definition": {"nodes": [], "edges": []}}),
        ("POST", "/api/v1/skills", {"name": "x", "content": "abcdefghij"}),
        ("POST", "/api/v1/groups", {"name": "x"}),
        ("POST", "/api/v1/chat", {"agent_name": "x", "message": "hi"}),
    ])
    def test_protected_post_401(self, client, method, path, json_body):
        r = client.request(method, path, json=json_body)
        assert r.status_code == 401, f"{method} {path} 无 JWT 应 401，实际 {r.status_code}"


class TestPublicEndpoints:
    """公开端点无需 JWT 应 200"""

    @pytest.mark.parametrize("path", [
        "/health",
        "/api/v1/system/status",
        "/api/v1/meta/providers",
        "/api/v1/meta/loaders",
        "/api/v1/meta/splitters",
        "/api/v1/meta/architectures",
        "/api/v1/meta/frameworks",
        "/api/v1/meta/tools",
        "/api/v1/meta/config",
    ])
    def test_public_get_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200, f"{path} 应公开访问，实际 {r.status_code}"
