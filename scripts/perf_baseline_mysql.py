#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生产依赖性能基线复测脚本
==================================================
目标：在「真实生产依赖」(MySQL 引擎 + Milvus Lite + 真实 ARK LLM) 下复测性能基线，
与测试环境的 SQLite + mock LLM 基线对比。

设计原则：
- 不污染真实 agentflow 库：使用隔离库 agentflow_perf（同一 MySQL 实例 / InnoDB 引擎）。
- 不修改项目 .env：所有覆盖通过环境变量在进程内注入。
- schema 与线上完全一致：alembic upgrade head。
- 真实 LLM：使用项目 .env 中已配置的 ARK key（doubao-seed-evolving 为生产默认模型，
  deepseek-v4-flash 为快速档），不 mock。

运行：
    ./venv/Scripts/python.exe scripts/perf_baseline_mysql.py
"""
from __future__ import annotations

import os
import sys
import time
import json
import statistics
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------- 0. 先设置环境变量（必须在 import app 任何模块之前）----------
PERF_DB = "agentflow_perf"
MYSQL_URL = f"mysql+pymysql://root:02101!aoAWH@127.0.0.1:3306/{PERF_DB}?charset=utf8mb4"

os.environ["DATABASE_URL"] = MYSQL_URL
os.environ["APP_ENV"] = "test"            # 跳过 APScheduler，避免后台任务干扰基线
os.environ["EMBEDDING_PROVIDER"] = "fake"  # 列表/聊天端点不命中 embedding，用 fake 避免网络噪声
os.environ["RERANKER_PROVIDER"] = "bm25"
os.environ["VECTOR_STORE"] = "milvus_lite"
os.environ["MILVUS_DB_PATH"] = str(ROOT / "data" / "milvus_perf.db")
os.environ["JWT_SECRET"] = "perf-baseline-secret-do-not-use-in-prod-xxxxxxxx"
os.environ["FERNET_KEY"] = "perf-fernet-key-0123456789abcdef"

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------- 1. 重建 settings 指向隔离库 ----------
import app.core.config as cfg_mod

cfg_mod.settings = cfg_mod.Settings()

from app.db import session as sess_mod

engine = create_engine(
    MYSQL_URL, pool_pre_ping=True, pool_recycle=3600, pool_size=5, max_overflow=10
)
sess_mod.engine = engine
sess_mod.SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


# ---------- 2. 准备隔离库 + alembic 迁移 ----------
def prepare_db():
    conn = pymysql.connect(
        host="127.0.0.1", port=3306, user="root",
        password="02101!aoAWH", connect_timeout=10, autocommit=True,
    )
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {PERF_DB}")
    cur.execute(f"CREATE DATABASE {PERF_DB} CHARACTER SET utf8mb4")
    conn.close()

    # 注意：本项目 alembic 合并迁移（f9a0b1c2d3e4）在 MySQL 下会因
    # 「建表顺序不满足外键依赖」直接报错 (1824)，SQLite 因不强制 FK 而一直未暴露。
    # 生产 MySQL 部署用 alembic 同样会挂。基线库改用 Base.metadata.create_all
    # （SQLAlchemy 按 FK 依赖拓扑排序，MySQL 可用），等价建立与生产一致的表结构。
    import app.models  # noqa: 注册所有模型到 metadata
    from app.db.session import Base
    Base.metadata.create_all(bind=engine)

    # 标记 alembic_version 为 head，便于后续迁移接力
    from alembic.config import Config
    from alembic import command
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", MYSQL_URL)
    command.stamp(cfg, "head")
    return "create_all OK (MySQL FK-safe) + alembic stamp head"


# ---------- 3. 测量工具 ----------
def login(client) -> str:
    r = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["data"]["token"]


def measure(client, method, url, headers=None, json_body=None, n=21, warmup=1, pre_hook=None):
    for _ in range(warmup):
        if pre_hook:
            pre_hook()
        if method == "GET":
            client.get(url, headers=headers)
        else:
            client.post(url, json=json_body, headers=headers)
    times = []
    for _ in range(n):
        if pre_hook:
            pre_hook()
        t0 = time.perf_counter()
        if method == "GET":
            client.get(url, headers=headers)
        else:
            client.post(url, json=json_body, headers=headers)
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    return {
        "n": n,
        "min": round(times[0], 2),
        "median": round(statistics.median(times), 2),
        "p95": round(times[int(len(times) * 0.95) - 1], 2),
        "max": round(times[-1], 2),
    }


def measure_llm_raw(provider, model, n=4):
    from langchain_core.messages import HumanMessage
    from app.services.llm import get_chat_model
    m = get_chat_model(provider=provider, model=model, temperature=0.3)
    # warmup（含首连 + 模型加载）
    m.invoke([HumanMessage(content="hi")])
    times = []
    last_content = ""
    for _ in range(n):
        t0 = time.perf_counter()
        resp = m.invoke([HumanMessage(content="用一句话介绍你自己")])
        dt = (time.perf_counter() - t0) * 1000
        times.append(dt)
        last_content = str(getattr(resp, "content", "") or "")
    times.sort()
    return {
        "n": n,
        "min": round(times[0], 1),
        "median": round(statistics.median(times), 1),
        "p95": round(times[min(int(len(times) * 0.95), len(times) - 1)], 1),
        "max": round(times[-1], 1),
        "sample_reply": last_content[:40],
    }


def main():
    print("=" * 70)
    print("生产依赖性能基线复测 (MySQL + Milvus Lite + 真实 ARK LLM)")
    print("=" * 70)
    msg = prepare_db()
    print(f"[1/4] {msg}  (隔离库 {PERF_DB})")

    from fastapi.testclient import TestClient
    from app.main import create_app

    app = create_app()
    results: dict = {"env": {}, "rest_mysql": {}, "real_llm": {}, "e2e_chat": {}}

    with TestClient(app) as client:
        token = login(client)
        H = {"Authorization": f"Bearer {token}"}

        # ---------- REST 列表端点（真实 MySQL 后端）----------
        print("\n[2/4] REST 列表端点延迟（MySQL 后端, n=21）")
        endpoints = [
            ("GET", "/api/v1/workflows"),
            ("GET", "/api/v1/agents"),
            ("GET", "/api/v1/rag/kbs"),
            ("GET", "/api/v1/groups"),
            ("GET", "/api/v1/skills"),
            ("GET", "/api/v1/system/apm"),
            ("GET", "/health"),
        ]
        for method, url in endpoints:
            m = measure(client, method, url, headers=H)
            results["rest_mysql"][url] = m
            print(f"  {method:4} {url:28} min={m['min']:>7} median={m['median']:>7} p95={m['p95']:>7} max={m['max']:>7} ms")

        # login（bcrypt 校验主导，~250ms）
        # 每次测量前清空登录限流器，否则 LOGIN_RATE_LIMIT_MAX=5 会在多次测量后返回 429（被误判为低延迟）
        def _clear_login_limiter():
            try:
                from app.core.security_utils import login_limiter
                login_limiter._hits.clear()
            except Exception:
                pass
        ml = measure(client, "POST", "/api/v1/auth/login",
                     json_body={"account": "admin", "password": "admin123"}, n=11,
                     pre_hook=_clear_login_limiter)
        results["rest_mysql"]["POST /api/v1/auth/login"] = ml
        # 显式计时一次并打印状态码，避免 429/401 短路被误判为低延迟
        _clear_login_limiter()
        _t0 = time.perf_counter()
        _lr = client.post("/api/v1/auth/login", json={"account": "admin", "password": "admin123"})
        _ldt = (time.perf_counter() - _t0) * 1000
        print(f"  POST  /api/v1/auth/login        min={ml['min']:>7} median={ml['median']:>7} p95={ml['p95']:>7} max={ml['max']:>7} ms  (校验点 status={_lr.status_code} {_ldt:.0f}ms)")

        # ---------- 真实 LLM 原始延迟 ----------
        print("\n[3/4] 真实 LLM 原始调用延迟（ARK, n=3）")
        for model in ["doubao-seed-evolving", "deepseek-v4-flash"]:
            r = measure_llm_raw("ark", model, n=3)
            results["real_llm"][model] = r
            print(f"  {model:24} min={r['min']:>7} median={r['median']:>7} p95={r['p95']:>7} max={r['max']:>7} ms  reply={r['sample_reply']!r}")

        # ---------- 端到端 AI 助手（真实 LLM 经 HTTP）----------
        print("\n[4/4] 端到端 /meta/chat 延迟（真实 LLM 经 HTTP, n=3）")
        chat_url = "/api/v1/meta/chat"
        # warmup（含 tool 注册 + 首次 import + 首连）
        client.post(chat_url, json={"message": "你好"}, headers=H)
        times = []
        replies = []
        for _ in range(3):
            t0 = time.perf_counter()
            r = client.post(chat_url, json={
                "message": "请只用一句话直接回复我，不要调用任何工具，也不要查询知识库。"
            }, headers=H)
            dt = (time.perf_counter() - t0) * 1000
            times.append(dt)
            try:
                replies.append(f"<{r.status_code}> " + str(r.json().get("data", {}).get("reply", ""))[:60])
            except Exception:
                replies.append(f"<{r.status_code}> (no-json)")
        times.sort()
        e2e = {
            "n": 3,
            "min": round(times[0], 1),
            "median": round(statistics.median(times), 1),
            "p95": round(times[2], 1),
            "max": round(times[2], 1),
            "sample_replies": replies,
        }
        results["e2e_chat"][chat_url] = e2e
        print(f"  POST {chat_url:22} min={e2e['min']:>7} median={e2e['median']:>7} p95={e2e['p95']:>7} max={e2e['max']:>7} ms")
        for i, rep in enumerate(replies):
            print(f"      reply[{i}]={rep!r}")

    # 环境信息
    results["env"] = {
        "db": "MySQL (InnoDB) " + MYSQL_URL.split("@")[-1],
        "vector_store": cfg_mod.settings.VECTOR_STORE,
        "milvus_path": cfg_mod.settings.milvus_db_abs,
        "llm_provider": cfg_mod.settings.LLM_PROVIDER,
        "chat_model_default": cfg_mod.settings.ARK_CHAT_MODEL,
        "embedding_provider": cfg_mod.settings.EMBEDDING_PROVIDER,
    }

    out = ROOT / "tests" / "PERF_BASELINE_MYSQL.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入: {out}")
    print("=" * 70)


if __name__ == "__main__":
    main()
