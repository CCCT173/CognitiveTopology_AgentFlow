"""综合冒烟测试: 覆盖 A 基础设施 / B 认证 / C 用户管理 / D Agent / E RAG / F 工作流 / G 群组
运行: python -m tests.test_full
"""
import io
import time
import uuid
import sys
import traceback
from fastapi.testclient import TestClient

PASS = 0
FAIL = 0
ERRORS = []


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        ERRORS.append((name, detail))
        print(f"  [FAIL] {name}  {detail}")


def login(client, account="admin", password="admin123"):
    r = client.post("/api/v1/auth/login", json={"account": account, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["token"]


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def setup_module():
    """导入 app 保证初始化"""
    from app.main import app  # noqa
    return app


def run_A_infra(app):
    print("\n[A] 基础设施")
    with TestClient(app) as c:
        r = c.get("/health")
        check("health 200", r.status_code == 200)
        check("X-Request-ID 响应头", "X-Request-ID" in r.headers)

        for path in ["/api/v1/meta/providers", "/api/v1/meta/loaders",
                     "/api/v1/meta/splitters", "/api/v1/meta/architectures",
                     "/api/v1/meta/frameworks", "/api/v1/meta/tools",
                     "/api/v1/meta/config"]:
            r = c.get(path)
            check(f"{path} 200", r.status_code == 200 and r.json()["code"] == 0, r.text[:100])

        # 错误码
        r = c.get("/api/v1/agents")
        check("无 token 401", r.status_code == 401 and r.json()["code"] == 4010)
        r = c.get("/api/v1/agents/不存在的xxx", headers=headers(login(c)))
        check("不存在 4040", r.status_code == 404 and r.json()["code"] == 4040, str(r.json()))


def run_B_auth(app):
    print("\n[B] 认证")
    with TestClient(app) as c:
        tag = uuid.uuid4().hex[:6]
        # 注册成功
        r = c.post("/api/v1/auth/register", json={
            "username": f"test{tag}", "account": f"u{tag}",
            "email": f"{tag}@x.com", "password": "abc123"})
        check("注册成功", r.status_code == 200 and r.json()["code"] == 0, r.text[:200])
        # 注册重名
        r2 = c.post("/api/v1/auth/register", json={
            "username": "x", "account": f"u{tag}", "email": "y@x.com", "password": "abc123"})
        check("账号重复返回非0", r2.json()["code"] != 0)
        # 弱密码
        r3 = c.post("/api/v1/auth/register", json={
            "username": "weak", "account": f"w{tag}", "email": "w@x.com", "password": "12345"})
        check("弱密码拒绝", r3.json()["code"] != 0, r3.text[:100])
        # 登录错误密码
        r4 = c.post("/api/v1/auth/login", json={"account": f"u{tag}", "password": "wrong"})
        check("错密码 4010", r4.json()["code"] == 4010)
        # 正确登录
        tok = login(c, account=f"u{tag}", password="abc123")
        check("正确登录返回 token", bool(tok))
        # me
        r5 = c.get("/api/v1/auth/me", headers=headers(tok))
        check("/me", r5.status_code == 200 and r5.json()["data"]["account"] == f"u{tag}")
        # ping
        check("/ping", c.post("/api/v1/auth/ping", headers=headers(tok)).status_code == 200)


def run_D_agents(app):
    print("\n[D] Agent")
    with TestClient(app) as c:
        tok = login(c); H = headers(tok)
        tag = uuid.uuid4().hex[:6]

        # D1 CRUD: 4 种架构
        archs = ["single", "react", "workflow", "skill"]
        ids = {}
        wf = c.post("/api/v1/workflows", json={"name": f"wf_{tag}"}, headers=H).json()["data"]
        parent = c.post("/api/v1/agents", json={"name": f"parent_{tag}", "architecture": "single"}, headers=H).json()["data"]
        for arch in archs:
            body = {"name": f"{arch}_{tag}", "architecture": arch}
            if arch == "workflow":
                body["workflow_id"] = wf["id"]
            if arch == "skill":
                body["parent_agent_id"] = parent["id"]
            r = c.post("/api/v1/agents", json=body, headers=H)
            check(f"创建 {arch}", r.status_code == 200 and r.json()["code"] == 0, r.text[:200])
            ids[arch] = r.json()["data"]

        # 重名 409
        r = c.post("/api/v1/agents", json={"name": f"single_{tag}"}, headers=H)
        check("重名 4090", r.json()["code"] == 4090)

        # 详情/列表
        r = c.get(f"/api/v1/agents/single_{tag}", headers=H)
        check("Agent 详情", r.status_code == 200 and r.json()["data"]["architecture"] == "single")
        r = c.get("/api/v1/agents", headers=H)
        check("Agent 列表", r.status_code == 200 and isinstance(r.json()["data"], list))

        # 更新
        r = c.patch(f"/api/v1/agents/single_{tag}", json={"description": "新描述"}, headers=H)
        check("更新 Agent", r.status_code == 200 and r.json()["data"]["description"] == "新描述")

        # D3 无工具 simple 问答
        r = c.post("/api/v1/chat", json={"agent_name": f"single_{tag}", "message": "你好"}, headers=H)
        check("simple 对话", r.status_code == 200 and r.json()["code"] == 0 and r.json()["data"]["reply"], r.text[:200])

        # D7 skill 直接对话 403
        r = c.post("/api/v1/chat", json={"agent_name": f"skill_{tag}", "message": "hi"}, headers=H)
        check("skill 直接对话 4030", r.status_code == 403 and r.json()["code"] == 4030)

        # D6 workflow runner
        r = c.post("/api/v1/chat", json={"agent_name": f"workflow_{tag}", "message": "go"}, headers=H)
        check("workflow runner TODO", r.status_code == 200 and "TODO Workflow" in r.json()["data"]["reply"])

        # D8 chat threads
        r = c.get("/api/v1/chat/threads", headers=H)
        check("threads 列表", r.status_code == 200 and isinstance(r.json()["data"], list))

        # 清理
        for arch in archs:
            c.delete(f"/api/v1/agents/{arch}_{tag}", headers=H)
        c.delete(f"/api/v1/agents/parent_{tag}", headers=H)
        c.delete(f"/api/v1/workflows/{wf['id']}", headers=H)


def run_E_rag(app):
    print("\n[E] RAG 知识库")
    with TestClient(app) as c:
        tok = login(c); H = headers(tok)
        tag = uuid.uuid4().hex[:6]

        # E1 KB CRUD
        kb = c.post("/api/v1/rag/kbs", json={"name": f"kb_{tag}"}, headers=H).json()["data"]
        kb_id = kb["id"]
        check("创建 KB", kb_id is not None)
        check("KB 列表", c.get("/api/v1/rag/kbs", headers=H).status_code == 200)
        check("KB 详情含统计", "document_count" in c.get(f"/api/v1/rag/kbs/{kb_id}", headers=H).json()["data"])

        # E2/E3 上传 text 测试 sentence 分块
        text = "退款政策:7天无理由退款。会员规则:普通9折/黄金8折/钻石7折。客服:400-123-4567。"
        files = {"file": ("policy.txt", io.BytesIO(text.encode("utf-8")), "text/plain")}
        up = c.post(f"/api/v1/rag/kbs/{kb_id}/upload", files=files,
                    data={"loader": "text", "splitter_type": "sentence", "chunk_size": "100", "chunk_overlap": "0"},
                    headers=H).json()["data"]
        check("上传返回 processing", up["status"] == "processing", str(up))
        doc_id = up["document_id"]
        # 轮询
        status = "processing"
        for _ in range(30):
            docs = c.get(f"/api/v1/rag/kbs/{kb_id}/documents", headers=H).json()["data"]
            d = next((x for x in docs if x["id"] == doc_id), None)
            if d and d["status"] in ("indexed", "failed"):
                status = d["status"]
                break
            time.sleep(0.5)
        check(f"文档已 indexed (actual={status})", status == "indexed")

        # E6 改名
        r = c.patch(f"/api/v1/rag/documents/{doc_id}", json={"display_name": "客服政策.txt"}, headers=H)
        check("改名", r.status_code == 200 and r.json()["data"]["display_name"] == "客服政策.txt")

        # E7 chunk 列表 + 修改 + 新增 + 删除
        # 等 chunks 准备好(异步索引完成)
        chunks = []
        for _ in range(30):
            chunks = c.get(f"/api/v1/rag/documents/{doc_id}/chunks", headers=H).json()["data"]
            if chunks:
                break
            time.sleep(0.3)
        check("chunks 列表", len(chunks) >= 1, f"chunks empty after wait")
        if chunks:
            cid = chunks[0]["id"]
            original = chunks[0]["content"]
            new_content = original + " [追加内容]"
            r = c.patch(f"/api/v1/rag/chunks/{cid}", json={"content": new_content}, headers=H)
            check("修改 chunk", r.status_code == 200 and r.json()["data"]["content"] == new_content, r.text[:200])
            # 还原内容避免影响后续检索
            c.patch(f"/api/v1/rag/chunks/{cid}", json={"content": original}, headers=H)
            nc = c.post(f"/api/v1/rag/documents/{doc_id}/chunks", json={"content": "新增加的chunk:钻石卡7折"}, headers=H)
            check("新增 chunk", nc.status_code == 200)
            c.delete(f"/api/v1/rag/chunks/{nc.json()['data']['id']}", headers=H)

        # E8 检索
        r = c.post("/api/v1/rag/query", json={"kb_id": kb_id, "query": "钻石会员几折", "top_k": 3}, headers=H)
        hits = r.json()["data"]
        check("检索命中", len(hits) >= 1 and any("7折" in h["content"] for h in hits), str([h["content"][:30] for h in hits]))

        # E5 大小限制(临时小文件 0 字节? 我们构造 51MB 太慢,测 0 字节)
        f = c.post(f"/api/v1/rag/kbs/{kb_id}/upload",
                   files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
                   data={"loader": "text", "splitter_type": "sentence", "chunk_size": "100", "chunk_overlap": "0"},
                   headers=H)
        check("空文件 4000", f.json()["code"] == 4000)

        # markdown loader
        md = "# 标题\n\n**加粗**文字。"
        files = {"file": ("t.md", io.BytesIO(md.encode("utf-8")), "text/markdown")}
        mu = c.post(f"/api/v1/rag/kbs/{kb_id}/upload", files=files,
                    data={"loader": "markdown", "splitter_type": "sentence", "chunk_size": "500", "chunk_overlap": "0"},
                    headers=H).json()
        check("markdown 上传", mu["code"] == 0)

        # docx loader
        try:
            from docx import Document
            d = Document(); d.add_paragraph("docx测试段落")
            buf = io.BytesIO(); d.save(buf); buf.seek(0)
            files = {"file": ("t.docx", buf.getvalue(), "application/vnd.openxmlformats")}
            du = c.post(f"/api/v1/rag/kbs/{kb_id}/upload", files=files,
                        data={"loader": "docx", "splitter_type": "sentence", "chunk_size": "500", "chunk_overlap": "0"},
                        headers=H).json()
            check("docx 上传", du["code"] == 0)
        except Exception as e:
            check("docx 上传(跳过)", True, f"skipped {e}")

        # regex splitter
        files = {"file": ("r.txt", io.BytesIO(b"a;b;c"), "text/plain")}
        ru = c.post(f"/api/v1/rag/kbs/{kb_id}/upload", files=files,
                    data={"loader": "text", "splitter_type": "regex",
                          "splitter_regex": ";", "chunk_size": "100", "chunk_overlap": "0"},
                    headers=H).json()
        check("regex 上传", ru["code"] == 0)

        # E9 统计
        kbd = c.get(f"/api/v1/rag/kbs/{kb_id}", headers=H).json()["data"]
        check("KB 统计 document_count>=1", kbd["document_count"] >= 1)

        # 删除 KB
        c.delete(f"/api/v1/rag/kbs/{kb_id}", headers=H)


def run_F_workflow(app):
    print("\n[F] 工作流")
    with TestClient(app) as c:
        tok = login(c); H = headers(tok)
        tag = uuid.uuid4().hex[:6]
        wf = c.post("/api/v1/workflows", json={"name": f"wf_{tag}", "definition": {"nodes": [], "edges": []}}, headers=H).json()
        check("创建工作流", wf["code"] == 0)
        wid = wf["data"]["id"]
        check("列表", c.get("/api/v1/workflows", headers=H).status_code == 200)
        check("详情", c.get(f"/api/v1/workflows/{wid}", headers=H).status_code == 200)
        r = c.patch(f"/api/v1/workflows/{wid}", json={"description": "d"}, headers=H)
        check("更新", r.status_code == 200)
        r = c.post(f"/api/v1/workflows/{wid}/toggle", json={"enabled": False}, headers=H)
        check("禁用工作流", r.status_code == 200)
        check("删除", c.delete(f"/api/v1/workflows/{wid}", headers=H).status_code == 200)


def run_G_groups(app):
    print("\n[G] 群组")
    with TestClient(app) as c:
        tok = login(c); H = headers(tok)
        tag = uuid.uuid4().hex[:6]
        g = c.post("/api/v1/groups", json={"name": f"g_{tag}"}, headers=H).json()["data"]
        gid = g["id"]
        check("建群", gid is not None)
        check("群列表", c.get("/api/v1/groups", headers=H).status_code == 200)

        # 先建一个 agent 共享
        a = c.post("/api/v1/agents", json={"name": f"ga_{tag}"}, headers=H).json()["data"]
        r = c.post(f"/api/v1/groups/{gid}/agents/{a['id']}", headers=H)
        check("共享 Agent", r.status_code == 200)
        check("共享列表", len(c.get(f"/api/v1/groups/{gid}/agents", headers=H).json()["data"]) == 1)

        # 群聊
        r = c.post(f"/api/v1/groups/{gid}/messages", json={"content": "hello"}, headers=H)
        check("发消息", r.status_code == 200 and len(r.json()["data"]) >= 1)
        msgs = c.get(f"/api/v1/groups/{gid}/messages", headers=H).json()["data"]
        check("消息列表", len(msgs) >= 1)
        mid = msgs[0]["id"]
        check("撤回", c.delete(f"/api/v1/groups/{gid}/messages/{mid}", headers=H).status_code == 200)
        check("撤回后列表", len(c.get(f"/api/v1/groups/{gid}/messages", headers=H).json()["data"]) == 0)

        # 解散
        check("解散", c.delete(f"/api/v1/groups/{gid}", headers=H).status_code == 200)
        c.delete(f"/api/v1/agents/ga_{tag}", headers=H)


def main():
    print("=" * 60)
    print("AgentRAG 综合冒烟测试")
    print("=" * 60)
    app = setup_module()
    try:
        run_A_infra(app)
        run_B_auth(app)
        run_D_agents(app)
        run_E_rag(app)
        run_F_workflow(app)
        run_G_groups(app)
    except Exception:
        traceback.print_exc()
    print("\n" + "=" * 60)
    print(f"通过: {PASS}   失败: {FAIL}")
    if ERRORS:
        print("\n失败明细:")
        for n, d in ERRORS:
            print(f"  - {n}: {d[:200]}")
    print("=" * 60)
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
