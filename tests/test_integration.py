"""集成测试：API 冒烟、工具链、沙箱、认证"""
import pytest


# ===== 集成：API 启动 + 健康检查 =====
def test_app_create():
    """FastAPI app 能创建、路由注册"""
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        # 登录路由存在（POST 不需要凭证，参数错误会返 422 而不是 404）
        r = client.post("/api/v1/auth/login", json={})
        assert r.status_code != 404, "auth/login route missing"
        # /health 返回 200
        assert client.get("/health").status_code == 200


def test_health_endpoint():
    import sys; sys.path.insert(0, ".")
    from fastapi.testclient import TestClient
    from app.main import create_app
    app = create_app()
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ===== 工具链集成：内置工具 + run_code =====
def test_all_builtin_tools_registered():
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry
    names = set(get_registry().names())
    for expected in ["rag_search", "web_search", "http_request", "calculator", "run_code"]:
        assert expected in names, f"missing tool: {expected}"


def test_openai_schema_includes_all():
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry
    schemas = get_registry().to_openai_tools()
    assert len(schemas) >= 5
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "parameters" in s["function"]


# ===== 沙箱 L1 安全测试 =====
def test_l1_blocks_network():
    import sys; sys.path.insert(0, ".")
    from app.sandbox.l1 import run_l1
    # import socket 应该被禁
    r = run_l1("import socket\ns = socket.socket()")
    assert r.ok is False


def test_l1_blocks_open():
    import sys; sys.path.insert(0, ".")
    from app.sandbox.l1 import run_l1
    r = run_l1("open('/etc/passwd').read()")
    assert r.ok is False


def test_l1_cant_escape_via_builtins():
    import sys; sys.path.insert(0, ".")
    from app.sandbox.l1 import run_l1
    payloads = [
        "().__class__",
        "__import__('os').system('echo hi')",
        "eval('1+1')",
        "globals()",
        "getattr(__builtins__, '__import__')('os')",
    ]
    for p in payloads:
        r = run_l1(p)
        assert r.ok is False or r.violations, f"L1 should block: {p!r}"


# ===== L3 沙箱 =====
def test_l3_files_isolation():
    import sys; sys.path.insert(0, ".")
    from app.sandbox.l3 import run_l3, reset_session
    reset_session("iso-test")
    # 不能读宿主文件
    r = run_l3("result = workspace.exists('../../../windows/win.ini')", "iso-test", timeout=10)
    assert r.ok is False
    assert "越界" in (r.error or "")
    reset_session("iso-test")


def test_l3_supports_pandas():
    import sys; sys.path.insert(0, ".")
    from app.sandbox.l3 import run_l3, reset_session
    reset_session("pd-test")
    r = run_l3("""
import pandas as pd
df = pd.DataFrame({'a':[1,2,3],'b':[4,5,6]})
result = df.describe().to_dict()
""", "pd-test", timeout=30)
    assert r.ok is True
    assert r.output is not None
    reset_session("pd-test")


def test_l3_persists_between_calls_same_session():
    """同一 session 文件持久"""
    import sys; sys.path.insert(0, ".")
    from app.sandbox.l3 import run_l3, reset_session
    reset_session("persist")
    run_l3("workspace.write('x.txt', 'hello')", "persist", timeout=10)
    r = run_l3("result = workspace.read('x.txt')", "persist", timeout=10)
    assert r.ok and r.output == "hello"
    reset_session("persist")


# ===== Auth =====
def test_jwt_roundtrip():
    import sys; sys.path.insert(0, ".")
    from app.core.security import create_token, decode_token
    t = create_token(user_id=42)
    assert decode_token(t) == 42


def test_password_hash():
    import sys; sys.path.insert(0, ".")
    from app.core.security import hash_password, verify_password
    h = hash_password("secret123")
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)


# ===== Fernet =====
def test_fernet_roundtrip():
    import sys; sys.path.insert(0, ".")
    from app.core.fernet import encrypt, decrypt
    c = encrypt("hello world")
    assert c.startswith("v1:")
    assert decrypt(c) == "hello world"
    assert decrypt("v1:invalid") is None
    assert decrypt("") is None
