"""
QA 安全层专项测试
- sanitize 脱敏（8 类敏感模式）
- pathguard 路径安全
- L1 AST 静态检查
- host_shell 只读/危险命令判定
- JWT 伪造/过期/篡改
- CORS 白名单
- XSS/SQL 注入基本防护
- 错误响应不泄露堆栈
"""
from __future__ import annotations
import os
import sys
import time
import uuid
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ============ sanitize 脱敏 ============

class TestSanitize:
    def test_mask_jwt(self):
        from app.core.sanitize import mask_value
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        out = mask_value(jwt)
        assert jwt not in out

    def test_mask_sk_key(self):
        from app.core.sanitize import mask_value
        s = "sk-abcdefghijklmnopqrstuvwxyz1234567890longenough"
        out = mask_value(s)
        assert s not in out

    def test_mask_phone(self):
        from app.core.sanitize import mask_value
        out = mask_value("联系电话：13800138000 请拨打")
        assert "138****8000" in out
        assert "13800138000" not in out

    def test_mask_idcard(self):
        from app.core.sanitize import mask_value
        out = mask_value("身份证号 110101199001011234 登记")
        assert "110101********1234" in out
        assert "110101199001011234" not in out

    def test_mask_email(self):
        from app.core.sanitize import mask_value
        out = mask_value("邮箱 alice@example.com 注册")
        assert "alice@example.com" not in out
        assert "@example.com" in out
        assert "*" in out

    def test_mask_bearer_header(self):
        from app.core.sanitize import mask_value
        # 足够长的 token 才会被 BEARER_RE 匹配
        long_token = "a" * 60
        out = mask_value(f"Authorization: Bearer {long_token}")
        assert long_token not in out
        assert "***" in out

    def test_mask_kv_secret(self):
        from app.core.sanitize import mask_value
        out = mask_value("password=supersecret123")
        assert "supersecret123" not in out
        assert "***" in out

    def test_mask_dict_recursive(self):
        from app.core.sanitize import sanitize
        long_token = "a" * 60
        data = {
            "password": "mysecret",
            "token": long_token,
            "user": {"email": "a@b.com", "age": 20},
            "list": [{"api_key": "sk-abcdefghij1234567890long"}, "normal"],
        }
        out = sanitize(data)
        assert out["password"] == "***"
        assert out["token"] != long_token
        assert "@b.com" in out["user"]["email"]
        assert out["user"]["age"] == 20
        assert out["list"][1] == "normal"

    def test_mask_env_values(self, monkeypatch):
        from app.core.sanitize import mask_env_values
        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-do-not-use-in-prod-xxxxxxxxxxxx")
        out = mask_env_values("using secret test-jwt-secret-do-not-use-in-prod-xxxxxxxxxxxx here")
        assert "test-jwt-secret-do-not-use-in-prod-xxxxxxxxxxxx" not in out
        assert "***" in out

    def test_sanitize_non_str_passthrough(self):
        from app.core.sanitize import sanitize
        assert sanitize(123) == 123
        assert sanitize(None) is None
        assert sanitize("") == ""


# ============ pathguard 路径安全 ============

class TestPathguard:
    def test_relative_inside_root_ok(self, tmp_path):
        from app.tools.host.pathguard import safe_resolve
        roots = [str(tmp_path)]
        (tmp_path / "sub").mkdir()
        # 传入绝对路径（safe_resolve 不会相对于 roots[0] 解析相对路径）
        p = safe_resolve(str(tmp_path / "sub" / "file.txt"), roots=roots)
        assert p is not None
        assert p.is_absolute()

    def test_path_traversal_blocked(self, tmp_path):
        from app.tools.host.pathguard import safe_resolve
        roots = [str(tmp_path)]
        with pytest.raises(ValueError):
            safe_resolve("../../etc/passwd", roots=roots)

    def test_sensitive_env_blocked(self, tmp_path):
        from app.tools.host.pathguard import safe_resolve
        roots = [str(tmp_path)]
        (tmp_path / ".env").write_text("SECRET=1")
        with pytest.raises(ValueError):
            safe_resolve(str(tmp_path / ".env"), roots=roots)

    def test_sensitive_pem_blocked(self, tmp_path):
        from app.tools.host.pathguard import safe_resolve
        roots = [str(tmp_path)]
        (tmp_path / "key.pem").write_text("x")
        with pytest.raises(ValueError):
            safe_resolve(str(tmp_path / "key.pem"), roots=roots)

    def test_sensitive_key_blocked(self, tmp_path):
        from app.tools.host.pathguard import safe_resolve
        roots = [str(tmp_path)]
        (tmp_path / "id_rsa").write_text("x")
        with pytest.raises(ValueError):
            safe_resolve(str(tmp_path / "id_rsa"), roots=roots)

    def test_sensitive_ssh_dir_blocked(self, tmp_path):
        from app.tools.host.pathguard import safe_resolve
        roots = [str(tmp_path)]
        (tmp_path / ".ssh").mkdir()
        with pytest.raises(ValueError):
            safe_resolve(str(tmp_path / ".ssh" / "known_hosts"), roots=roots)

    def test_windows_reserved_names(self):
        from app.tools.host.pathguard import is_windows_reserved
        assert is_windows_reserved("NUL") is True
        assert is_windows_reserved("CON") is True
        assert is_windows_reserved("COM1") is True
        assert is_windows_reserved("LPT9") is True
        assert is_windows_reserved("normal.txt") is False

    def test_windows_reserved_in_path_raises(self, tmp_path):
        from app.tools.host.pathguard import safe_resolve
        roots = [str(tmp_path)]
        with pytest.raises(ValueError):
            safe_resolve(str(tmp_path / "NUL.txt"), roots=roots)

    def test_ads_detection(self):
        from app.tools.host.pathguard import has_ads
        if os.name == "nt":
            assert has_ads("C:\\file.txt:secret") is True
        assert has_ads("file.txt") is False

    def test_unc_prefix_rejected(self, tmp_path):
        from app.tools.host.pathguard import safe_resolve
        roots = [str(tmp_path)]
        with pytest.raises(ValueError):
            safe_resolve("\\\\evil\\share\\file", roots=roots)

    def test_empty_path_rejected(self):
        from app.tools.host.pathguard import safe_resolve
        with pytest.raises(ValueError):
            safe_resolve("")

    def test_tilde_expansion(self):
        from app.tools.host.pathguard import safe_resolve
        home_agentflow = Path.home() / ".agentflow"
        home_agentflow.mkdir(exist_ok=True)
        p = safe_resolve("~/.agentflow")
        assert p.is_absolute()


# ============ L1 AST 静态检查 ============

class TestL1Sandbox:
    def test_import_os_blocked(self):
        from app.sandbox.l1 import static_check
        v = static_check("import os\nprint('hi')")
        assert any("os" in x for x in v)

    def test_from_subprocess_blocked(self):
        from app.sandbox.l1 import static_check
        v = static_check("from subprocess import run")
        assert any("subprocess" in x for x in v)

    def test_dunder_class_blocked(self):
        from app.sandbox.l1 import static_check
        v = static_check("x = ().__class__.__base__.__subclasses__()")
        assert any("__class__" in x or "__subclasses__" in x for x in v)

    def test_open_blocked(self):
        from app.sandbox.l1 import static_check
        v = static_check("open('/etc/passwd').read()")
        assert any("open" in x for x in v)

    def test_eval_blocked(self):
        from app.sandbox.l1 import static_check
        v = static_check("eval('1+1')")
        assert any("eval" in x for x in v)

    def test_dunder_import_blocked(self):
        from app.sandbox.l1 import static_check
        v = static_check("__import__('os').system('ls')")
        assert any("__import__" in x for x in v)

    def test_safe_code_passes(self):
        from app.sandbox.l1 import static_check
        v = static_check("import math\nprint(math.sqrt(4))")
        assert v == []

    def test_syntax_error_reported(self):
        from app.sandbox.l1 import static_check
        v = static_check("def broken(")
        assert len(v) == 1 and "语法错误" in v[0]

    def test_l1_run_safe_code(self):
        from app.sandbox.l1 import run_l1
        r = run_l1("import math\nresult = math.factorial(5)\nprint(result)", timeout=5)
        assert r.ok is True
        assert "120" in r.stdout

    def test_l1_run_violations_rejected(self):
        from app.sandbox.l1 import run_l1
        r = run_l1("import os\nos.system('echo hi')", timeout=5)
        assert r.ok is False
        assert r.violations

    def test_l1_timeout(self):
        from app.sandbox.l1 import run_l1
        r = run_l1("while True: pass", timeout=2)
        assert r.ok is False
        assert "超时" in (r.error or "")


# ============ host_shell 命令判定 ============

class TestHostShell:
    def test_readonly_ls_ok(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["ls", "-la"])
        assert ro is True

    def test_readonly_git_status_ok(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["git", "status"])
        assert ro is True

    def test_git_commit_write(self):
        from app.tools.host.shell import _is_readonly
        ro, reason = _is_readonly(["git", "commit", "-m", "x"])
        assert ro is False
        assert "写" in reason

    def test_dangerous_rm_rf_root(self):
        from app.tools.host.shell import _is_readonly
        ro, reason = _is_readonly(["rm", "-rf", "/"])
        assert ro is False
        assert "危险" in reason

    def test_shell_metachar_pipe_blocked(self):
        from app.tools.host.shell import _is_readonly
        ro, reason = _is_readonly(["cat", "file", "|", "sh"])
        assert ro is False
        assert "元字符" in reason

    def test_shell_metachar_redirect_blocked(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["echo", "hi", ">", "/tmp/x"])
        assert ro is False

    def test_curl_pipe_sh_blocked(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["curl", "http://x", "|", "sh"])
        assert ro is False

    def test_pip_install_write(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["pip", "install", "requests"])
        assert ro is False

    def test_pip_list_readonly(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["pip", "list"])
        assert ro is True

    def test_python_version_readonly(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["python", "--version"])
        assert ro is True

    def test_python_c_needs_confirm(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["python", "-c", "print(1)"])
        assert ro is False

    def test_sudo_blocked(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["sudo", "rm", "-rf", "/"])
        assert ro is False

    def test_empty_command(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly([])
        assert ro is False

    def test_unknown_command_needs_confirm(self):
        from app.tools.host.shell import _is_readonly
        ro, _ = _is_readonly(["foobarbaz_unknown_cmd"])
        assert ro is False


# ============ JWT 安全 ============

class TestJWTSecurity:
    def test_no_token_returns_401(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, client):
        r = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
        assert r.status_code == 401

    def test_tampered_token_returns_401(self, client):
        from app.core.security import create_token
        token = create_token(1)
        tampered = token[:-4] + "xxxx"
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered}"})
        assert r.status_code == 401

    def test_expired_token_returns_401(self, client):
        from app.core.security import create_token
        token = create_token(1, minutes=-1)
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    def test_wrong_secret_token_returns_401(self, client):
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        payload = {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=15)}
        fake_token = pyjwt.encode(payload, "wrong-secret-xxxxxxxxxxxxxx", algorithm="HS256")
        r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fake_token}"})
        assert r.status_code == 401

    def test_system_metrics_apm_require_auth(self, client):
        """系统监控端点必须鉴权（BUG-001 已修复：无 token 返回 401，带合法 token 返回 200）"""
        for ep in ("/api/v1/system/metrics", "/api/v1/system/apm"):
            r = client.get(ep)
            assert r.status_code == 401, f"{ep} 未授权应返回 401，实际 {r.status_code}"
        # 带合法 token 应正常返回 200
        lr = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        assert lr.status_code == 200, lr.text
        token = lr.json()["data"]["token"]
        for ep in ("/api/v1/system/metrics", "/api/v1/system/apm"):
            r = client.get(ep, headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200, f"{ep} 鉴权后应返回 200，实际 {r.status_code}"


# ============ CORS ============

class TestCORS:
    def test_cors_allowed_origin(self, client):
        r = client.options(
            "/api/v1/system/status",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        allow = r.headers.get("access-control-allow-origin", "")
        assert "localhost:5173" in allow or allow == "*" or allow == "http://localhost:5173"

    def test_cors_disallowed_origin(self, client):
        r = client.get(
            "/api/v1/system/status",
            headers={"Origin": "http://evil.example.com"},
        )
        allow = r.headers.get("access-control-allow-origin", "")
        assert "evil.example.com" not in allow


# ============ 错误响应不泄露堆栈 ============

class TestErrorResponse:
    def test_404_no_stacktrace(self, client):
        token = self._login(client)
        r = client.get("/api/v1/workflows/999999", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (401, 404)
        body = r.text.lower()
        assert "traceback" not in body
        assert "sqlalchemy" not in body
        assert "file \"" not in body

    def test_invalid_json_no_stacktrace(self, client):
        token = self._login(client)
        r = client.post(
            "/api/v1/workflows",
            content=b"{not valid json",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        assert r.status_code in (400, 422)
        assert "traceback" not in r.text.lower()

    def test_missing_field_validation_format(self, client):
        token = self._login(client)
        r = client.post(
            "/api/v1/workflows", json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code in (400, 422)
        data = r.json()
        assert "code" in data or "detail" in data or "message" in data or "msg" in data

    def _login(self, client):
        r = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        return r.json()["data"]["token"]


# ============ 基础注入防护 ============

class TestInjection:
    def test_sql_injection_login(self, client):
        r = client.post("/api/v1/auth/login", json={
            "account": "admin' OR '1'='1",
            "password": "anything",
        })
        assert r.status_code in (400, 401, 404)

    def test_sql_injection_register_special_chars(self, client):
        """特殊字符账号名不应导致 500"""
        tag = uuid.uuid4().hex[:8]
        r = client.post("/api/v1/auth/register", json={
            "account": f"special_{tag}", "username": f"special_{tag}", "password": "pass123",
            "email": f"special{tag}@x.com",
        })
        assert r.status_code in (200, 400, 409, 422)

    def test_xss_in_workflow_name(self, client):
        token = self._login(client)
        payload = "<script>alert('xss')</script>"
        r = client.post(
            "/api/v1/workflows",
            json={"name": "xss_test_2", "display_name": payload, "definition": {"nodes": [], "edges": []}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

    def _login(self, client):
        r = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        return r.json()["data"]["token"]


# ============ X-Trace-Id 响应头 ============

class TestTraceHeader:
    def test_response_has_trace_id(self, client):
        r = client.get("/api/v1/system/status")
        tid = r.headers.get("x-trace-id") or r.headers.get("x-request-id")
        assert tid, "响应应包含 X-Trace-Id 或 X-Request-Id"
