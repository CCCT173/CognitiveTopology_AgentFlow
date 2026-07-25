"""
pytest 公共 fixture:
- tmp_db: 每个测试独立的 SQLite 临时库（自动建表+回滚）
- client: FastAPI TestClient
- mock_llm: 替换 LLM 调用为 mock
"""
import os
import sys
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 确保可以 import app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 以下文件是"在 import 阶段即执行真实逻辑（连接 live 服务 / 导入恶意 zip 验证沙箱）的手动走查脚本"，
# 不适合自动化 pytest 收集，故显式排除。
collect_ignore = ["test_e2e.py", "test_permissions.py", "test_walk.py", "test_zip_advanced.py"]


@pytest.fixture(autouse=True)
def _test_env(tmp_path, monkeypatch):
    """每个测试独立环境：临时 .agentflow 目录 + SQLite DB"""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-do-not-use-in-prod-xxxxxxxxxxxx")
    monkeypatch.setenv("FERNET_KEY", "test-fernet-key-0123456789abcdef")
    # QA 阶段：隔离 Milvus Lite 数据文件，避免并发争抢 data/milvus.db 锁死
    monkeypatch.setenv("MILVUS_DB_PATH", str(tmp_path / "milvus_test.db"))
    # QA 阶段：清理限流器，避免跨测试累积触发 429
    try:
        from app.core.security_utils import login_limiter, api_limiter
        login_limiter._hits.clear()
        api_limiter._hits.clear()
    except Exception:
        pass
    from app.core.config import Settings
    import app.core.config as cfg_mod
    cfg_mod.settings = Settings()
    # 重新绑定 engine/SessionLocal
    from app.db import session as sess_mod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    new_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    sess_mod.engine = new_engine
    sess_mod.SessionLocal = sessionmaker(bind=new_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    # 建表
    from app.db.session import Base
    import app.models  # noqa
    Base.metadata.create_all(bind=new_engine)
    # 建 admin user
    from app.core.security import hash_password
    from app.models.user import User
    from sqlalchemy import select, func
    with sess_mod.SessionLocal() as db:
        exists = db.scalar(select(User).where(User.account == "admin"))
        if not exists:
            next_uid = db.scalar(select(func.coalesce(func.max(User.user_id), 0))) + 1
            u = User(user_id=next_uid, username="admin", account="admin", email="admin@local",
                     password_hash=hash_password("admin123"), role="super_admin")
            db.add(u); db.commit()
    yield
    # QA 阶段：清理登录限流器，避免跨测试累积触发 429
    try:
        from app.core.security_utils import login_limiter, api_limiter
        login_limiter._hits.clear()
        api_limiter._hits.clear()
    except Exception:
        pass


@pytest.fixture
def db_session(_test_env):
    """每个测试独立的 DB session，测试结束自动回滚"""
    from app.db.session import Base, get_db
    from app.models import user, agent, rag, group, workflow, skill, audit  # noqa

    engine = create_engine(
        os.environ["DATABASE_URL"], connect_args={"check_same_thread": False}
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with DB dependency override"""
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.db.session import get_db

    app = create_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_llm(monkeypatch):
    """Patch LLM service to return deterministic responses."""

    class MockResponse:
        def __init__(self, content="mock response", tool_calls=None):
            self.content = content
            self.tool_calls = tool_calls or []
            self.usage = type("Usage", (), {"prompt_tokens": 10, "completion_tokens": 20})()

    def _fake_chat(*args, **kwargs):
        return MockResponse()

    from app.services import llm as llm_mod
    monkeypatch.setattr(llm_mod, "chat_completion", _fake_chat, raising=False)
    monkeypatch.setattr(llm_mod, "chat_stream", _fake_chat, raising=False)
    yield _fake_chat
