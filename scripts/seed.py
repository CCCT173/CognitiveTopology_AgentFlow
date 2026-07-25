"""
数据库初始化脚本：
1. 创建 admin/admin123 超级管理员（如不存在）
2. 注入内置 Skill 示例（web_search / rag_search / code_exec / summarize）
3. 打印统计摘要

运行: python -m scripts.seed   （项目根目录）
"""
import sys
from pathlib import Path

# 确保能 import app.*
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.skill import Skill  # noqa: E402
from app.core.security import hash_password  # noqa: E402


# ---------- 内置 skill 内容 ----------
BUILTIN_SKILLS = [
    {
        "name": "web_search",
        "description": "联网搜索公开网页并返回摘要结果。",
        "version": "1.0.0",
        "author": "system",
        "category": "tool",
        "tags": ["search", "web"],
        "content": """---
name: web_search
description: 联网搜索公开网页并返回摘要结果
version: 1.0.0
author: system
category: tool
tags: [search, web]
params:
  - name: query
    type: string
    required: true
    description: 搜索关键词
---

# web_search

调用外部搜索接口，返回 top-N 结果标题+URL+摘要。
""",
        "config": {"params": [{"name": "query", "type": "string", "required": True}]},
    },
    {
        "name": "rag_search",
        "description": "在本地知识库中进行向量检索。",
        "version": "1.0.0",
        "author": "system",
        "category": "rag",
        "tags": ["rag", "vector", "kb"],
        "content": """---
name: rag_search
description: 在本地知识库中进行向量检索
version: 1.0.0
author: system
category: rag
tags: [rag, vector, kb]
params:
  - name: kb_id
    type: integer
    required: true
  - name: query
    type: string
    required: true
  - name: top_k
    type: integer
    default: 5
---

# rag_search

调用 Milvus 向量库检索指定知识库中 top_k 相关片段。
""",
        "config": {"params": [{"name": "kb_id", "type": "integer", "required": True},
                              {"name": "query", "type": "string", "required": True},
                              {"name": "top_k", "type": "integer", "default": 5}]},
    },
    {
        "name": "summarize",
        "description": "对长文本进行摘要压缩。",
        "version": "1.0.0",
        "author": "system",
        "category": "utility",
        "tags": ["summary", "llm"],
        "content": """---
name: summarize
description: 对长文本进行摘要压缩
version: 1.0.0
author: system
category: utility
tags: [summary, llm]
params:
  - name: text
    type: string
    required: true
  - name: max_words
    type: integer
    default: 200
---

# summarize

调用 LLM 对输入文本做结构化摘要。
""",
        "config": {"params": [{"name": "text", "type": "string", "required": True},
                              {"name": "max_words", "type": "integer", "default": 200}]},
    },
]


def run():
    db = SessionLocal()
    try:
        # 1. admin 账号
        admin = db.query(User).filter(User.account == "admin").first()
        if admin:
            print(f"[OK] admin 账号已存在 (user_id={admin.user_id}, role={admin.role})")
        else:
            admin = User(
                username="管理员",
                account="admin",
                email="admin@local.dev",
                password_hash=hash_password("admin123"),
                role="super_admin",
                enabled=True,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
            print(f"[OK] 已创建 admin/admin123 (user_id={admin.user_id})")

        # 2. 内置 skills
        added = 0
        for s in BUILTIN_SKILLS:
            exists = db.query(Skill).filter(Skill.name == s["name"]).first()
            if exists:
                continue
            db.add(Skill(
                name=s["name"], description=s["description"], version=s["version"],
                author=s["author"], category=s["category"], tags=s["tags"],
                content=s["content"], config=s["config"],
                is_builtin=True, is_active=True, created_by=admin.user_id,
            ))
            added += 1
        db.commit()
        print(f"[OK] 内置 Skill 已初始化，新增 {added} 个（共 {len(BUILTIN_SKILLS)} 个）")

        # 3. 统计
        n_users = db.query(User).count()
        n_skills = db.query(Skill).count()
        n_builtin = db.query(Skill).filter(Skill.is_builtin == True).count()  # noqa: E712
        print("-" * 50)
        print(f"用户总数: {n_users}  Skill总数: {n_skills} (内置 {n_builtin})")
    finally:
        db.close()


if __name__ == "__main__":
    run()
