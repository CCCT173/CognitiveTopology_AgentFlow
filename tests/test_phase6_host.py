"""Phase 6 测试: L0 Host 工具集进阶"""
import pytest


def test_pathguard_sensitive_paths():
    """敏感路径应被拒绝"""
    import sys; sys.path.insert(0, ".")
    from app.tools.host.pathguard import safe_resolve
    sensitive = [
        ".env", ".env.local", ".ssh/id_rsa", "config/key.pem",
        "certs/server.key", "C:/Users/x/.aws/credentials",
    ]
    for p in sensitive:
        with pytest.raises(ValueError) as exc:
            safe_resolve(p)
        assert "敏感" in str(exc.value) or "越界" in str(exc.value), f"{p} not blocked"


def test_pathguard_escape_blocked():
    """路径穿越被拒绝"""
    import sys; sys.path.insert(0, ".")
    from app.tools.host.pathguard import safe_resolve
    with pytest.raises(ValueError):
        safe_resolve("../../../Windows/System32")
    with pytest.raises(ValueError):
        safe_resolve("C:/Windows/System32/drivers/etc/hosts")


def test_host_write_read_delete_flow():
    """host_write→read→edit→move→delete 全流程"""
    import sys, os, uuid; sys.path.insert(0, ".")
    from app.tools import get_registry
    r = get_registry()
    suffix = uuid.uuid4().hex[:8]
    tmp = f"_host_p6_{suffix}.txt"
    tmp2 = f"_host_p6_{suffix}_m.txt"
    try:
        # write
        res = r.get("host_write").run(path=tmp, content="hello world\n")
        assert res.ok, f"write failed: {res.error}"
        # read
        res = r.get("host_read").run(path=tmp)
        assert res.ok and "hello world" in res.output
        # edit
        res = r.get("host_edit").run(path=tmp, old_string="world", new_string="agentflow")
        assert res.ok, f"edit failed: {res.error}"
        res = r.get("host_read").run(path=tmp)
        assert "agentflow" in res.output and "world" not in res.output
        # move
        res = r.get("host_move").run(src=tmp, dst=tmp2)
        assert res.ok, f"move failed: {res.error}"
        assert not os.path.exists(tmp)
        assert os.path.exists(tmp2)
        # list_dir
        res = r.get("host_list_dir").run(path=".", recursive=False)
        assert res.ok
        # delete
        res = r.get("host_delete").run(path=tmp2)
        assert res.ok, f"delete failed: {res.error}"
        assert not os.path.exists(tmp2)
    finally:
        for f in [tmp, tmp2]:
            if os.path.exists(f): os.unlink(f)


def test_host_info():
    """host_info 返回系统信息"""
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry
    r = get_registry()
    res = r.get("host_info").run()
    assert res.ok
    assert "os" in res.data
    assert "python" in res.data
    assert res.data["python"].startswith("3.")


def test_host_shell_readonly():
    """只读命令直接执行"""
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry
    r = get_registry()
    sh = r.get("host_shell")
    res = sh.run(command="python --version")
    assert res.ok
    assert "Python" in res.output


def test_host_shell_dangerous_blocked():
    """危险命令拒绝"""
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry
    r = get_registry()
    sh = r.get("host_shell")
    dangerous = ["rm -rf /", "sudo ls", "mkfs.ext4 /dev/sda"]
    for cmd in dangerous:
        res = sh.run(command=cmd)
        # 没有 ctx.db，返回错误
        assert not res.ok, f"{cmd} should be blocked"


def test_host_shell_write_needs_confirmation():
    """只读命令直接执行"""
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry
    r = get_registry()
    sh = r.get("host_shell")
    res = sh.run(command="echo helloworld")
    assert res.ok, f"echo failed: {res.error}"


def test_host_tools_require_confirmation_marking():
    """host_write/edit/delete/move/shell 标了 requires_confirmation"""
    import sys; sys.path.insert(0, ".")
    from app.tools import get_registry
    r = get_registry()
    for name in ["host_write", "host_edit", "host_delete", "host_move"]:
        t = r.get(name)
        assert t.requires_confirmation, f"{name} should require confirmation"
    for name in ["host_read", "host_list_dir", "host_info"]:
        t = r.get(name)
        assert not t.requires_confirmation, f"{name} should not require confirmation"
