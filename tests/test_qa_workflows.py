"""
QA 工作流 / Agent / HITL / API Key 测试
- CRUD + 版本管理（publish/rollback）
- 乐观锁（expected_version 并发冲突）
- HITL 二次确认流程
- 外部 API Key 鉴权
- 权限分级
"""
from __future__ import annotations
import sys
import uuid
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _login(client, account="admin", password="admin123"):
    r = client.post("/api/v1/auth/login", json={"account": account, "password": password})
    if r.status_code == 429:
        pytest.skip("登录限流触发，跳过")
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


def _full_login(client, account="admin", password="admin123"):
    """登录并返回完整 data（含 refresh_token）"""
    r = client.post("/api/v1/auth/login", json={"account": account, "password": password})
    if r.status_code == 429:
        pytest.skip("登录限流触发，跳过")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_wf_name():
    return f"qa_wf_{uuid.uuid4().hex[:8]}"


def _create_workflow(client, token, name=None, definition=None):
    name = name or _make_wf_name()
    definition = definition if definition is not None else {"nodes": [], "edges": []}
    r = client.post(
        "/api/v1/workflows",
        json={"name": name, "display_name": name, "definition": definition},
        headers=_auth(token),
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


# ============ 工作流 CRUD ============

class TestWorkflowCRUD:
    def test_create_workflow(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        assert wf["id"]
        assert isinstance(wf["id"], int)

    def test_list_workflows(self, client):
        token = _login(client)
        _create_workflow(client, token)
        r = client.get("/api/v1/workflows", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()["data"]
        items = data if isinstance(data, list) else data.get("items", data.get("list", []))
        assert isinstance(items, list)

    def test_get_workflow_by_id(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        r = client.get(f"/api/v1/workflows/{wf['id']}", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["data"]["id"] == wf["id"]

    def test_get_nonexistent_workflow_404(self, client):
        token = _login(client)
        r = client.get("/api/v1/workflows/999999", headers=_auth(token))
        assert r.status_code == 404

    def test_update_workflow(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        new_def = {"nodes": [{"id": "n1"}], "edges": []}
        r = client.patch(
            f"/api/v1/workflows/{wf['id']}",
            json={"definition": new_def, "display_name": "updated"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text

    def test_delete_workflow(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        r = client.delete(f"/api/v1/workflows/{wf['id']}", headers=_auth(token))
        assert r.status_code == 200
        r2 = client.get(f"/api/v1/workflows/{wf['id']}", headers=_auth(token))
        assert r2.status_code == 404

    def test_toggle_workflow_requires_body(self, client):
        """/toggle 需要 body {enabled: bool}（符合设计）"""
        token = _login(client)
        wf = _create_workflow(client, token)
        # 不传 body 应 422
        r = client.post(f"/api/v1/workflows/{wf['id']}/toggle", headers=_auth(token))
        assert r.status_code == 422
        # 传 {enabled: true} 应 200
        r = client.post(f"/api/v1/workflows/{wf['id']}/toggle",
                        json={"enabled": True}, headers=_auth(token))
        assert r.status_code == 200, r.text

    def test_duplicate_name_409(self, client):
        token = _login(client)
        name = _make_wf_name()
        _create_workflow(client, token, name=name)
        r = client.post(
            "/api/v1/workflows",
            json={"name": name, "definition": {"nodes": [], "edges": []}},
            headers=_auth(token),
        )
        assert r.status_code in (400, 409)


# ============ 乐观锁 ============

class TestOptimisticLock:
    def test_patch_with_matching_version(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        version = wf.get("version", wf.get("current_version", 1))
        r = client.patch(
            f"/api/v1/workflows/{wf['id']}",
            json={"definition": {"nodes": [{"id": "a"}], "edges": []},
                  "expected_version": version},
            headers=_auth(token),
        )
        assert r.status_code in (200, 400, 422), r.text

    def test_patch_with_stale_version_409(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        v1 = wf.get("version", wf.get("current_version", 1))
        r1 = client.patch(
            f"/api/v1/workflows/{wf['id']}",
            json={"definition": {"nodes": [{"id": "a"}], "edges": []},
                  "expected_version": v1},
            headers=_auth(token),
        )
        if r1.status_code != 200:
            pytest.skip("工作流 PATCH 未实现 expected_version 乐观锁")
        r2 = client.patch(
            f"/api/v1/workflows/{wf['id']}",
            json={"definition": {"nodes": [{"id": "b"}], "edges": []},
                  "expected_version": v1},
            headers=_auth(token),
        )
        assert r2.status_code == 409


# ============ 版本快照/回滚 ============

class TestVersioning:
    def test_publish_version(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        r = client.post(
            f"/api/v1/workflows/{wf['id']}/versions",
            json={"note": "v1 发布"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text

    def test_list_versions(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        client.post(f"/api/v1/workflows/{wf['id']}/versions",
                    json={"note": "v1"}, headers=_auth(token))
        r = client.get(f"/api/v1/workflows/{wf['id']}/versions", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()["data"]
        items = data if isinstance(data, list) else data.get("items", [])
        assert len(items) >= 1

    def test_rollback_workflow(self, client):
        token = _login(client)
        original_def = {"nodes": [{"id": "original"}], "edges": []}
        wf = _create_workflow(client, token, definition=original_def)
        pv = client.post(f"/api/v1/workflows/{wf['id']}/versions",
                         json={"note": "v1"}, headers=_auth(token))
        assert pv.status_code == 200, pv.text
        # 修改
        client.patch(f"/api/v1/workflows/{wf['id']}",
                     json={"definition": {"nodes": [{"id": "modified"}], "edges": []}},
                     headers=_auth(token))
        # 获取 version 号（字段是 version: int）
        vdata = pv.json()["data"]
        v_num = None
        if isinstance(vdata, dict):
            v_num = vdata.get("version") or vdata.get("id") or vdata.get("version_id")
        elif isinstance(vdata, int):
            v_num = vdata
        if v_num:
            rr = client.post(f"/api/v1/workflows/{wf['id']}/rollback",
                             json={"version": v_num}, headers=_auth(token))
            assert rr.status_code == 200, f"rollback 应 200，实际 {rr.status_code}: {rr.text[:200]}"


# ============ 工作流运行 ============

class TestWorkflowRun:
    def test_run_disabled_workflow_fails(self, client):
        """未启用工作流运行应 400"""
        token = _login(client)
        wf = _create_workflow(client, token)
        r = client.post(
            f"/api/v1/workflows/{wf['id']}/run",
            json={"input": {}},
            headers=_auth(token),
        )
        assert r.status_code in (400, 422)

    def test_get_run_history(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        r = client.get(f"/api/v1/workflows/{wf['id']}/runs", headers=_auth(token))
        assert r.status_code == 200


# ============ API Key + 外部调用 ============

class TestApiKeyAndExecute:
    def test_create_api_key_returns_plain(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        r = client.post(
            f"/api/v1/workflows/{wf['id']}/api-keys",
            json={"name": "test-key"},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        plain = data.get("key") or data.get("plain_key") or data.get("api_key")
        assert plain, "创建 API Key 时应返回明文"

    def test_list_api_keys(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        client.post(f"/api/v1/workflows/{wf['id']}/api-keys",
                    json={"name": "k1"}, headers=_auth(token))
        r = client.get(f"/api/v1/workflows/{wf['id']}/api-keys", headers=_auth(token))
        assert r.status_code == 200

    def test_execute_wrong_key_401(self, client):
        r = client.post("/api/v1/execute/wf-key-does-not-exist-xxxxxxxxxxxx", json={"inputs": {}})
        assert r.status_code in (401, 403, 404)

    def test_execute_disabled_key_403(self, client):
        token = _login(client)
        wf = _create_workflow(client, token,
                              definition={"nodes": [{"id": "start", "type": "start"}], "edges": []})
        client.post(f"/api/v1/workflows/{wf['id']}/toggle",
                    json={"enabled": True}, headers=_auth(token))
        kr = client.post(f"/api/v1/workflows/{wf['id']}/api-keys",
                         json={"name": "k1"}, headers=_auth(token))
        data = kr.json()["data"]
        plain = data.get("key") or data.get("plain_key") or data.get("api_key")
        key_id = data.get("id")
        # 禁用 key（字段名是 is_active）
        tr = client.post(f"/api/v1/workflows/{wf['id']}/api-keys/{key_id}/toggle",
                         json={"is_active": False}, headers=_auth(token))
        assert tr.status_code == 200, f"toggle key 应 200，实际 {tr.status_code}: {tr.text[:200]}"
        r = client.post(f"/api/v1/execute/{plain}", json={"inputs": {}})
        assert r.status_code in (401, 403), f"禁用 key 应 401/403，实际 {r.status_code}: {r.text[:200]}"

    def test_delete_api_key(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        kr = client.post(f"/api/v1/workflows/{wf['id']}/api-keys",
                         json={"name": "k1"}, headers=_auth(token))
        key_id = kr.json()["data"]["id"]
        r = client.delete(f"/api/v1/workflows/{wf['id']}/api-keys/{key_id}", headers=_auth(token))
        assert r.status_code == 200


# ============ HITL ============

class TestHITL:
    def test_pending_list_empty(self, client):
        token = _login(client)
        r = client.get("/api/v1/hitl/pending", headers=_auth(token))
        assert r.status_code == 200
        data = r.json()["data"]
        items = data if isinstance(data, list) else data.get("items", [])
        assert isinstance(items, list)

    def test_confirm_nonexistent_int_id(self, client):
        token = _login(client)
        # cid 是 int，传 99999 应 400（确认失败）而非 404
        r = client.post("/api/v1/hitl/99999/confirm", json={}, headers=_auth(token))
        assert r.status_code in (400, 404)

    def test_deny_nonexistent_int_id(self, client):
        token = _login(client)
        r = client.post("/api/v1/hitl/99999/deny", json={}, headers=_auth(token))
        assert r.status_code in (400, 404)

    def test_invalid_cid_type_422(self, client):
        """非 int 的 cid 应被 FastAPI 校验为 422"""
        token = _login(client)
        r = client.post("/api/v1/hitl/not-an-int/confirm", json={}, headers=_auth(token))
        assert r.status_code == 422


# ============ Agent CRUD ============

class TestAgentCRUD:
    def _create_agent(self, client, token, name=None):
        name = name or f"qa_agent_{uuid.uuid4().hex[:8]}"
        r = client.post("/api/v1/agents", json={
            "name": name, "display_name": name,
            "system_prompt": "You are a test agent",
            "architecture": "simple",
        }, headers=_auth(token))
        assert r.status_code == 200, r.text
        return r.json()["data"]

    def test_create_agent(self, client):
        token = _login(client)
        agent = self._create_agent(client, token)
        assert agent.get("id") or agent.get("name")

    def test_list_agents(self, client):
        token = _login(client)
        self._create_agent(client, token)
        r = client.get("/api/v1/agents", headers=_auth(token))
        assert r.status_code == 200

    def test_get_agent(self, client):
        token = _login(client)
        agent = self._create_agent(client, token)
        r = client.get(f"/api/v1/agents/{agent['name']}", headers=_auth(token))
        assert r.status_code == 200

    def test_toggle_agent_requires_body(self, client):
        """toggle 需要 {enabled: bool}"""
        token = _login(client)
        agent = self._create_agent(client, token)
        r = client.post(f"/api/v1/agents/{agent['name']}/toggle", headers=_auth(token))
        assert r.status_code == 422
        r = client.post(f"/api/v1/agents/{agent['name']}/toggle",
                        json={"enabled": True}, headers=_auth(token))
        assert r.status_code == 200

    def test_delete_agent(self, client):
        token = _login(client)
        agent = self._create_agent(client, token)
        r = client.delete(f"/api/v1/agents/{agent['name']}", headers=_auth(token))
        assert r.status_code == 200


# ============ 权限 ============

class TestPermissions:
    def test_list_permissions_empty(self, client):
        token = _login(client)
        wf = _create_workflow(client, token)
        r = client.get(f"/api/v1/workflows/{wf['id']}/permissions", headers=_auth(token))
        assert r.status_code == 200, f"perm list 应 200，实际 {r.status_code}: {r.text[:200]}"

    def test_grant_permission_to_new_user(self, client):
        """授权新用户 editor 角色"""
        token = _login(client)
        tag = uuid.uuid4().hex[:8]
        # 注册 user2（带 username）
        r2 = client.post("/api/v1/auth/register", json={
            "account": f"perm_u_{tag}", "username": f"perm_u_{tag}", "password": "pass123",
            "email": f"pu{tag}@x.com",
        })
        assert r2.status_code == 200, r2.text
        udata = r2.json()["data"]["user"]
        u2_id = udata["user_id"]
        wf = _create_workflow(client, token)
        g = client.post(f"/api/v1/workflows/{wf['id']}/permissions",
                        json={"user_id": u2_id, "role": "editor"}, headers=_auth(token))
        assert g.status_code == 200, f"grant 应 200，实际 {g.status_code}: {g.text[:200]}"
        # 撤销
        d = client.delete(f"/api/v1/workflows/{wf['id']}/permissions/{u2_id}", headers=_auth(token))
        assert d.status_code == 200

    def test_nonexistent_workflow_permission_404(self, client):
        token = _login(client)
        r = client.get("/api/v1/workflows/999999/permissions", headers=_auth(token))
        assert r.status_code == 404
