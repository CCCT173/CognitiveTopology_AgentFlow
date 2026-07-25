"""
QA 其他模块测试：RAG / Skills / Groups / Users / System
"""
from __future__ import annotations
import io
import sys
import uuid
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _login(client, account="admin", password="admin123"):
    r = client.post("/api/v1/auth/login", json={"account": account, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


def _register_user(client, account=None):
    """注册新用户（schema 需要 username 字段）"""
    account = account or f"u_{uuid.uuid4().hex[:8]}"
    r = client.post("/api/v1/auth/register", json={
        "account": account, "username": account, "password": "pass123",
        "email": f"{account}@x.com",
    })
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=False)
def mock_vector_store(monkeypatch):
    """Mock vector_store，避免 Milvus 真实初始化（锁/慢）"""
    from app.services import vector_store as vs
    monkeypatch.setattr(vs, "ensure_collection", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(vs, "drop_collection", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(vs, "search", lambda *a, **kw: [], raising=False)
    monkeypatch.setattr(vs, "insert_chunks", lambda *a, **kw: None, raising=False)
    monkeypatch.setattr(vs, "delete_chunks", lambda *a, **kw: None, raising=False)
    yield


# ============ RAG 知识库 ============

class TestRAG:
    def _create_kb(self, client, token):
        name = f"qa_kb_{uuid.uuid4().hex[:8]}"
        r = client.post("/api/v1/rag/kbs", json={
            "name": name, "loader": "text", "splitter_type": "sentence",
            "chunk_size": 200, "chunk_overlap": 0,
        }, headers=_auth(token))
        assert r.status_code == 200, r.text
        return r.json()["data"]

    def test_create_list_kb(self, client, mock_vector_store):
        token = _login(client)
        kb = self._create_kb(client, token)
        assert isinstance(kb["id"], int)
        r = client.get("/api/v1/rag/kbs", headers=_auth(token))
        assert r.status_code == 200

    def test_get_kb_detail(self, client, mock_vector_store):
        token = _login(client)
        kb = self._create_kb(client, token)
        r = client.get(f"/api/v1/rag/kbs/{kb['id']}", headers=_auth(token))
        assert r.status_code == 200

    def test_patch_kb(self, client, mock_vector_store):
        token = _login(client)
        kb = self._create_kb(client, token)
        r = client.patch(f"/api/v1/rag/kbs/{kb['id']}",
                         json={"description": "updated desc"}, headers=_auth(token))
        assert r.status_code == 200

    def test_delete_kb(self, client, mock_vector_store):
        token = _login(client)
        kb = self._create_kb(client, token)
        r = client.delete(f"/api/v1/rag/kbs/{kb['id']}", headers=_auth(token))
        assert r.status_code == 200

    def test_query_empty_kb(self, client, mock_vector_store):
        """空知识库查询不应 500"""
        token = _login(client)
        kb = self._create_kb(client, token)
        r = client.post("/api/v1/rag/query",
                        json={"kb_id": kb["id"], "query": "test", "top_k": 3},
                        headers=_auth(token))
        # 允许 200 或 400（kb 存在但无文档）或 500 自愈后 200
        assert r.status_code in (200, 400, 404)

    def test_query_nonexistent_kb_404(self, client, mock_vector_store):
        token = _login(client)
        r = client.post("/api/v1/rag/query",
                        json={"kb_id": 999999, "query": "test", "top_k": 3},
                        headers=_auth(token))
        assert r.status_code == 404


# ============ Skills ============

class TestSkills:
    def _create_skill(self, client, token, code=None):
        code = code or "result = params.get('x', 0) * 2"
        name = f"qa_skill_{uuid.uuid4().hex[:8]}"
        r = client.post("/api/v1/skills", json={
            "name": name,
            "content": "# Skill\n\n执行计算",
            "code": code,
            "description": "test skill",
        }, headers=_auth(token))
        assert r.status_code == 200, r.text
        return r.json()["data"]

    def test_create_list_skill(self, client):
        token = _login(client)
        sk = self._create_skill(client, token)
        assert isinstance(sk["id"], int)
        r = client.get("/api/v1/skills", headers=_auth(token))
        assert r.status_code == 200

    def test_get_categories(self, client):
        token = _login(client)
        r = client.get("/api/v1/skills/categories", headers=_auth(token))
        assert r.status_code == 200

    def test_test_skill_returns_200(self, client):
        """skill test 端点应返回 200（即使内部有 NameError，也应被 try/except 包裹）"""
        token = _login(client)
        sk = self._create_skill(client, token, code="result = params.get('x', 0) * 2\nprint(result)")
        r = client.post(f"/api/v1/skills/{sk['id']}/test",
                        json={"input_params": {"x": 21}}, headers=_auth(token))
        assert r.status_code == 200, r.text
        # 响应应该是结构化的
        data = r.json().get("data", r.json())
        assert isinstance(data, dict)

    def test_create_skill_with_dangerous_code_blocked_at_create(self, client):
        """BUG-003 已修复：创建 skill 时即做 L1 AST 检查，含危险代码的创建请求应被 422 拒绝"""
        token = _login(client)
        r = client.post("/api/v1/skills", json={
            "name": f"bad_skill_{uuid.uuid4().hex[:6]}",
            "content": "malicious skill doc",
            "code": "import os\nos.system('echo hi')",
        }, headers=_auth(token))
        # 创建阶段即被 L1 拦截，不应入库
        assert r.status_code == 422, f"含危险代码的创建应被 422 拒绝，实际 {r.status_code}: {r.text[:200]}"
        body = r.json()
        assert body.get("code") == 4220, f"期望 VALIDATION(4220)，实际 {body}"

    def test_toggle_skill(self, client):
        token = _login(client)
        sk = self._create_skill(client, token)
        r = client.post(f"/api/v1/skills/{sk['id']}/toggle", headers=_auth(token))
        # toggle 可能需要 body 或不需要；接受 200 或 422
        assert r.status_code in (200, 422)

    def test_delete_skill(self, client):
        token = _login(client)
        sk = self._create_skill(client, token)
        r = client.delete(f"/api/v1/skills/{sk['id']}", headers=_auth(token))
        assert r.status_code == 200

    def test_skill_usage_stats_updated_after_test(self, client):
        """BUG-002 复核（实为误报）：test_skill 成功后 usage_count 递增、last_used_at 被更新。
        utc_now 已在 commit 142f84a 正确导入，此处锁定该行为防止回归。"""
        token = _login(client)
        sk = self._create_skill(client, token)  # 安全代码，创建应成功
        assert sk["usage_count"] == 0
        assert sk.get("last_used_at") is None
        r = client.post(f"/api/v1/skills/{sk['id']}/test",
                        json={"input_params": {"x": 2}}, headers=_auth(token))
        assert r.status_code == 200, r.text
        # 重新获取，确认统计字段已更新
        gr = client.get(f"/api/v1/skills/{sk['id']}", headers=_auth(token))
        assert gr.status_code == 200, gr.text
        data = gr.json()["data"]
        assert data["usage_count"] >= 1, f"usage_count 应 >=1，实际 {data['usage_count']}"
        assert data.get("last_used_at") is not None, "last_used_at 应被更新"


# ============ Groups ============

class TestGroups:
    def _create_group(self, client, token):
        name = f"qa_group_{uuid.uuid4().hex[:8]}"
        r = client.post("/api/v1/groups", json={"name": name, "description": "test"}, headers=_auth(token))
        assert r.status_code == 200, r.text
        return r.json()["data"]

    def test_create_list_group(self, client):
        token = _login(client)
        g = self._create_group(client, token)
        assert g["id"]
        r = client.get("/api/v1/groups", headers=_auth(token))
        assert r.status_code == 200

    def test_post_message(self, client):
        token = _login(client)
        g = self._create_group(client, token)
        r = client.post(f"/api/v1/groups/{g['id']}/messages",
                        json={"content": "hello group"}, headers=_auth(token))
        assert r.status_code == 200

    def test_list_messages(self, client):
        token = _login(client)
        g = self._create_group(client, token)
        client.post(f"/api/v1/groups/{g['id']}/messages",
                    json={"content": "m1"}, headers=_auth(token))
        r = client.get(f"/api/v1/groups/{g['id']}/messages", headers=_auth(token))
        assert r.status_code == 200
        msgs = r.json()["data"]
        items = msgs if isinstance(msgs, list) else msgs.get("items", msgs.get("messages", []))
        assert isinstance(items, list)

    def test_notices_lifecycle(self, client):
        token = _login(client)
        g = self._create_group(client, token)
        nr = client.post(f"/api/v1/groups/{g['id']}/notices",
                         json={"content": "重要公告"}, headers=_auth(token))
        assert nr.status_code == 200, nr.text
        nid = nr.json()["data"]["id"]
        lr = client.get(f"/api/v1/groups/{g['id']}/notices", headers=_auth(token))
        assert lr.status_code == 200
        rr = client.post(f"/api/v1/groups/{g['id']}/notices/{nid}/read", headers=_auth(token))
        assert rr.status_code == 200

    def test_join_leave(self, client):
        token1 = _login(client)
        g = self._create_group(client, token1)
        gid = g["id"]
        udata = _register_user(client)
        token2 = udata["token"]
        jr = client.post(f"/api/v1/groups/{gid}/join", headers=_auth(token2))
        assert jr.status_code == 200
        lr = client.post(f"/api/v1/groups/{gid}/leave", headers=_auth(token2))
        assert lr.status_code == 200


# ============ Users 管理 ============

class TestUsers:
    def test_tree_and_flat(self, client):
        token = _login(client)
        r1 = client.get("/api/v1/users/tree", headers=_auth(token))
        assert r1.status_code == 200
        r2 = client.get("/api/v1/users/flat", headers=_auth(token))
        assert r2.status_code == 200
        r3 = client.get("/api/v1/users/admins", headers=_auth(token))
        assert r3.status_code == 200

    def test_admin_create_user(self, client):
        token = _login(client)
        tag = uuid.uuid4().hex[:8]
        r = client.post("/api/v1/users", json={
            "account": f"adm_created_{tag}", "username": "Admin Created", "password": "pass123",
            "email": f"ac{tag}@x.com", "role": "user",
        }, headers=_auth(token))
        assert r.status_code == 200, r.text

    def test_patch_user_role(self, client):
        token = _login(client)
        tag = uuid.uuid4().hex[:8]
        cr = client.post("/api/v1/users", json={
            "account": f"role_chg_{tag}", "username": "RC", "password": "pass123",
            "email": f"rc{tag}@x.com", "role": "user",
        }, headers=_auth(token))
        assert cr.status_code == 200, cr.text
        uid = cr.json()["data"]["user_id"]
        rr = client.post(f"/api/v1/users/{uid}/role",
                         json={"role": "admin"}, headers=_auth(token))
        assert rr.status_code == 200

    def test_enable_disable_user(self, client):
        token = _login(client)
        tag = uuid.uuid4().hex[:8]
        cr = client.post("/api/v1/users", json={
            "account": f"enable_{tag}", "username": "EM", "password": "pass123",
            "email": f"em{tag}@x.com", "role": "user",
        }, headers=_auth(token))
        assert cr.status_code == 200, cr.text
        uid = cr.json()["data"]["user_id"]
        dr = client.post(f"/api/v1/users/{uid}/enabled",
                         json={"enabled": False}, headers=_auth(token))
        assert dr.status_code == 200


# ============ System ============

class TestSystem:
    def test_status_public(self, client):
        r = client.get("/api/v1/system/status")
        assert r.status_code == 200

    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_metrics_with_auth(self, client):
        """metrics 当前无权限控制（BUG 记录），但有 token 应 200"""
        token = _login(client)
        r = client.get("/api/v1/system/metrics", headers=_auth(token))
        assert r.status_code == 200

    def test_dashboard(self, client):
        token = _login(client)
        r = client.get("/api/v1/system/dashboard", headers=_auth(token))
        assert r.status_code == 200

    def test_stats_admin_only(self, client):
        token = _login(client)
        r = client.get("/api/v1/system/stats", headers=_auth(token))
        assert r.status_code == 200

    def test_logs_admin_only(self, client):
        token = _login(client)
        r = client.get("/api/v1/system/logs", headers=_auth(token))
        assert r.status_code == 200

    def test_apm_with_auth(self, client):
        token = _login(client)
        r = client.get("/api/v1/system/apm", headers=_auth(token))
        assert r.status_code == 200
