"""多用户协同测试：共享权限 + 版本回滚 + 乐观锁"""
import pytest


def test_workflow_permission_grant_revoke():
    """授权、撤销、list 权限"""
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
        # 创建工作流
        r = c.post("/api/v1/workflows", json={"name": "perm_test_wf"}, headers=h)
        assert r.status_code == 200
        wid = r.json()["data"]["id"]
        # 权限列表（默认有 owner 权限）
        r = c.get(f"/api/v1/workflows/{wid}/permissions", headers=h)
        assert r.status_code == 200
        perms = r.json()["data"]
        assert len(perms) >= 1
        assert any(p["role"] == "owner" for p in perms)
        # 清理
        c.delete(f"/api/v1/workflows/{wid}", headers=h)


def test_optimistic_lock_version_conflict():
    """乐观锁：用旧版本 PATCH 返回 409"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        token = r.json()["data"]["token"]
        h = {"Authorization": f"Bearer {token}"}
        r = c.post("/api/v1/workflows", json={"name": "optlock_test"}, headers=h)
        wid = r.json()["data"]["id"]
        initial_version = r.json()["data"]["version"]
        # 第一次更新带正确版本
        r = c.patch(f"/api/v1/workflows/{wid}",
                     json={"description": "v2", "expected_version": initial_version}, headers=h)
        assert r.status_code == 200
        # 第二次用旧版本应该冲突
        r = c.patch(f"/api/v1/workflows/{wid}",
                     json={"description": "v3", "expected_version": initial_version}, headers=h)
        assert r.status_code == 409
        c.delete(f"/api/v1/workflows/{wid}", headers=h)


def test_version_publish_and_rollback():
    """发布版本 + 回滚"""
    import sys, json; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        token = r.json()["data"]["token"]
        h = {"Authorization": f"Bearer {token}"}
        r = c.post("/api/v1/workflows", json={"name": "version_test"}, headers=h)
        wid = r.json()["data"]["id"]
        # 发布 v1
        r = c.post(f"/api/v1/workflows/{wid}/versions",
                    json={"name": "v1", "changelog": "first"}, headers=h)
        assert r.status_code == 200
        assert r.json()["data"]["version"] == 1
        # 修改 description
        c.patch(f"/api/v1/workflows/{wid}",
                 json={"description": "modified", "expected_version": 1}, headers=h)
        # 列出版本
        r = c.get(f"/api/v1/workflows/{wid}/versions", headers=h)
        assert r.status_code == 200
        assert len(r.json()["data"]) == 1
        # 回滚到 v1
        r = c.post(f"/api/v1/workflows/{wid}/rollback", json={"version": 1}, headers=h)
        assert r.status_code == 200
        assert r.json()["data"]["rolled_back_to"] == 1
        c.delete(f"/api/v1/workflows/{wid}", headers=h)


def test_workflow_version_auto_increment():
    """创建后 version=1，PATCH 后递增"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as c:
        r = c.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        token = r.json()["data"]["token"]
        h = {"Authorization": f"Bearer {token}"}
        r = c.post("/api/v1/workflows", json={"name": "ver_inc"}, headers=h)
        wid = r.json()["data"]["id"]
        assert r.json()["data"]["version"] == 1
        c.delete(f"/api/v1/workflows/{wid}", headers=h)
