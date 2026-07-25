"""
agentflow CLI:
  agentflow dev             启动开发服务器（含 APScheduler）
  agentflow db migrate      运行 Alembic 迁移
  agentflow db stamp head   标记当前 schema 为最新版
  agentflow backup create   备份 data 目录到 backups/
  agentflow backup restore  从备份恢复
  agentflow doctor          环境检查（fernet key、Node.js、ripgrep、磁盘）
  agentflow init            在当前目录初始化 .agentflow/
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer

app = typer.Typer(help="agentflow CLI")
db_app = typer.Typer(help="Database commands")
backup_app = typer.Typer(help="Backup commands")
app.add_typer(db_app, name="db")
app.add_typer(backup_app, name="backup")

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_settings():
    """延迟 import settings（避免 CLI 启动阻塞）"""
    sys.path.insert(0, str(PROJECT_ROOT))
    from app.core.config import settings
    return settings


@app.command()
def dev(host: str = None, port: int = None, reload: bool = True):
    """启动开发服务器"""
    settings = _load_settings()
    uvicorn_host = host or settings.HOST
    uvicorn_port = port or settings.PORT
    typer.echo(f"🚀 Starting agentflow v{settings.APP_VERSION} on http://{uvicorn_host}:{uvicorn_port}")
    typer.echo(f"   DB: {settings.DATABASE_URL[:60]}")
    import uvicorn
    uvicorn.run(
        "app.main:create_app",
        host=uvicorn_host, port=uvicorn_port,
        reload=reload, factory=True,
    )


@db_app.command("migrate")
def db_migrate(revision: str = "head"):
    """运行 Alembic 迁移"""
    from alembic.config import Config
    from alembic import command
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    settings = _load_settings()
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.upgrade(cfg, revision)
    typer.echo("✅ Migration complete")


@db_app.command("stamp")
def db_stamp(revision: str = "head"):
    """标记当前数据库 schema 为指定版本（不跑迁移）"""
    from alembic.config import Config
    from alembic import command
    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    settings = _load_settings()
    cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    command.stamp(cfg, revision)
    typer.echo(f"✅ Stamped to {revision}")


@backup_app.command("create")
def backup_create():
    """备份 data/ 和 ~/.agentflow/fernet.key 到 backups/"""
    settings = _load_settings()
    backups_dir = PROJECT_ROOT / "backups"
    backups_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"agentflow_backup_{ts}"
    backup_path.mkdir()
    # 数据目录
    data_src = PROJECT_ROOT / "data"
    if data_src.exists():
        shutil.copytree(data_src, backup_path / "data")
    # uploads
    up_src = PROJECT_ROOT / settings.UPLOAD_DIR
    if up_src.exists():
        shutil.copytree(up_src, backup_path / settings.UPLOAD_DIR)
    # fernet key
    fernet_key = Path.home() / ".agentflow" / "fernet.key"
    if fernet_key.exists():
        shutil.copy2(fernet_key, backup_path / "fernet.key")
    typer.echo(f"✅ Backup saved to {backup_path}")


@backup_app.command("restore")
def backup_restore(path: str = typer.Argument(..., help="Backup directory path")):
    """从备份恢复"""
    bp = Path(path)
    if not bp.exists():
        typer.echo(f"❌ Backup not found: {bp}", err=True)
        raise typer.Exit(1)
    typer.confirm("This will overwrite current data. Continue?", abort=True)
    settings = _load_settings()
    # Restore data/
    data_src = bp / "data"
    if data_src.exists():
        data_dst = PROJECT_ROOT / "data"
        if data_dst.exists():
            shutil.rmtree(data_dst)
        shutil.copytree(data_src, data_dst)
    # Restore uploads
    up_src = bp / settings.UPLOAD_DIR
    if up_src.exists():
        up_dst = PROJECT_ROOT / settings.UPLOAD_DIR
        if up_dst.exists():
            shutil.rmtree(up_dst)
        shutil.copytree(up_src, up_dst)
    typer.echo(f"✅ Restored from {bp}")


@app.command()
def doctor():
    """环境检查"""
    settings = _load_settings()
    ok = True
    checks = []

    # 1. fernet key
    fernet_key = Path.home() / ".agentflow" / "fernet.key"
    if fernet_key.exists():
        checks.append(("✅ Fernet key", str(fernet_key)))
    else:
        checks.append(("⚠️  Fernet key will be auto-generated on first start", ""))

    # 2. database
    from sqlalchemy import create_engine, inspect
    from app.db.session import Base
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {})
    try:
        tables = inspect(engine).get_table_names()
        checks.append((f"✅ Database ({settings.DATABASE_URL[:40]}...)", f"{len(tables)} tables"))
    except Exception as e:
        checks.append((f"❌ Database connection failed", str(e)))
        ok = False

    # 3. Node.js for MCP
    try:
        r = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            checks.append(("✅ Node.js", r.stdout.strip()))
        else:
            checks.append(("⚠️  Node.js not found (MCP stdio servers with npm won't work)", ""))
    except Exception:
        checks.append(("⚠️  Node.js not found (MCP stdio servers with npm won't work)", ""))

    # 4. Python version
    checks.append(("✅ Python", sys.version.split()[0]))

    # 5. .env
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        checks.append(("✅ .env exists", ""))
    else:
        checks.append(("⚠️  .env not found (will use defaults)", ""))

    for label, detail in checks:
        typer.echo(f"  {label}  {detail}")

    if not ok:
        raise typer.Exit(1)


@app.command()
def init():
    """在当前目录初始化 agentflow 配置"""
    d = Path.cwd() / ".agentflow"
    d.mkdir(exist_ok=True)
    typer.echo(f"✅ Initialized .agentflow/ in {Path.cwd()}")
    typer.echo("   Next steps: edit .env, then `agentflow db migrate`, then `agentflow dev`")


if __name__ == "__main__":
    app()
