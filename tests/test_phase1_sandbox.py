"""L1 严格沙箱 smoke test"""
import pytest


def test_l1_basic():
    from app.sandbox.l1 import run_l1
    r = run_l1("result = 2 ** 10")
    assert r.ok is True
    assert r.output == 1024


def test_l1_blocks_os_import():
    from app.sandbox.l1 import run_l1
    r = run_l1("import os\nos.system('echo pwn')")
    assert r.ok is False
    assert any("禁止 import: os" in v for v in r.violations)


def test_l1_blocks_dunder():
    from app.sandbox.l1 import run_l1
    r = run_l1("x = ().__class__.__bases__[0].__subclasses__()")
    assert r.ok is False
    assert r.violations


def test_l1_allows_math():
    from app.sandbox.l1 import run_l1
    r = run_l1("import math\nresult = math.sqrt(144)")
    assert r.ok is True
    assert r.output == 12.0


def test_l3_basic():
    from app.sandbox.l3 import run_l3, reset_session
    reset_session("pytest")
    r = run_l3("import math\nresult = math.factorial(6)", "pytest", timeout=30)
    assert r.ok is True
    assert r.output == 720
    reset_session("pytest")


def test_l3_path_escape_blocked():
    from app.sandbox.l3 import run_l3, reset_session
    reset_session("pytest-esc")
    r = run_l3('workspace.read("../../../windows/win.ini")', "pytest-esc", timeout=10)
    assert r.ok is False
    assert "越界" in (r.error or "")
    reset_session("pytest-esc")


def test_run_code_tool_registered():
    from app.tools import get_registry
    r = get_registry()
    assert r.get("run_code") is not None
    res = r.get("run_code").run(code="result = 2 ** 20")
    assert res.ok
    assert "1048576" in res.to_text()
