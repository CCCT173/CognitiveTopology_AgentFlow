"""
创建"行业情报简报"多Agent协同工作流 + 绑定的workflow架构Agent
"""
import sys, os, json, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:8001"

def token():
    r = requests.post(f"{BASE}/api/v1/auth/login", json={'account':'admin','password':'admin123'})
    return r.json()['data']['token']

T = token()
H = {'Authorization': f'Bearer {T}', 'Content-Type': 'application/json'}

# ===== 1. 创建"行业情报"知识库（存放过往简报归档）=====
print("[1] 创建行业情报 KB...")
r = requests.post(f"{BASE}/api/v1/rag/kbs", headers=H, json={
    'name': '行业情报归档',
    'description': '多Agent协同工作流生成的行业情报简报，自动归档供后续检索',
    'splitter_type': 'sentence', 'chunk_size': 400, 'chunk_overlap': 50,
})
print("  KB:", r.status_code, r.json().get('msg'))
kb_id = r.json()['data']['id']
print("  kb_id =", kb_id)

# ===== 2. 工作流定义 =====
# DAG:
#   start → search_news (tool) → search_competitors (tool) → search_tech (tool)
#         → analyze (agent: web-researcher) → format (llm) → end
nodes = [
    {
        "id": "start", "type": "start", "name": "开始",
        "position": {"x": 60, "y": 200},
        "config": {},
    },
    {
        "id": "search_news", "type": "tool", "name": "搜索最新新闻",
        "position": {"x": 260, "y": 80},
        "config": {
            "tool_name": "web_search",
            "params": {
                "query": "{{input}} 最新新闻 site:36kr.com OR site:jiqizhixin.com",
                "max_results": 5, "region": "cn-zh", "time_filter": "w",
            },
        },
    },
    {
        "id": "search_competitors", "type": "tool", "name": "搜索竞品动态",
        "position": {"x": 260, "y": 200},
        "config": {
            "tool_name": "web_search",
            "params": {
                "query": "{{input}} 竞品 融资 发布",
                "max_results": 5, "region": "cn-zh", "time_filter": "m",
            },
        },
    },
    {
        "id": "search_tech", "type": "tool", "name": "搜索技术趋势",
        "position": {"x": 260, "y": 320},
        "config": {
            "tool_name": "web_search",
            "params": {
                "query": "{{input}} 技术趋势 开源 论文",
                "max_results": 5, "region": "wt-wt", "time_filter": "m",
            },
        },
    },
    {
        "id": "analyze", "type": "agent", "name": "研究员分析汇总",
        "position": {"x": 540, "y": 200},
        "config": {
            "agent_name": "web-researcher",
            "message": (
                "基于以下三方面的联网搜索结果，对【{{input}}】进行综合分析，输出：\n"
                "1. 关键发现（3-5条）\n"
                "2. 主要竞品动向\n"
                "3. 技术趋势观察\n"
                "4. 对我司（智启科技，企业级AI Agent平台）的启示\n\n"
                "=== 最新新闻 ===\n{{search_news.result}}\n\n"
                "=== 竞品动态 ===\n{{search_competitors.result}}\n\n"
                "=== 技术趋势 ===\n{{search_tech.result}}"
            ),
        },
    },
    {
        "id": "format", "type": "llm", "name": "生成Markdown简报",
        "position": {"x": 820, "y": 200},
        "config": {
            "system_prompt": "你是智启科技的行业分析师，负责把研究结果整理成标准Markdown简报。",
            "prompt": (
                "请把以下分析结果整理成一份规范的行业情报简报，Markdown格式：\n\n"
                "# 行业情报简报：{{input}}\n\n"
                "📅 生成时间：当前\n"
                "🔍 分析员：AI 研究团队\n\n"
                "## 一、核心要点（TL;DR）\n"
                "用一句话概括本期发现。\n\n"
                "## 二、新闻动态\n"
                "列出 3-5 条重要新闻，每条附简要说明。\n\n"
                "## 三、竞品观察\n"
                "主要竞品的最新动向。\n\n"
                "## 四、技术趋势\n"
                "相关技术、开源、论文方面的进展。\n\n"
                "## 五、对智启科技的建议\n"
                "基于以上分析，给出 3-5 条具体建议。\n\n"
                "## 六、信息来源\n"
                "列出引用的来源 URL（从搜索结果中提取）。\n\n"
                "原始分析结果：\n{{analyze.reply}}\n\n"
                "注意：简报要专业、精炼，使用emoji分段，便于高管快速浏览。"
            ),
            "temperature": 0.5,
        },
    },
    {
        "id": "end", "type": "end", "name": "输出简报",
        "position": {"x": 1100, "y": 200},
        "config": {
            "output_key": "{{format.text}}",
        },
    },
]

edges = [
    {"id":"e1","source":"start","target":"search_news"},
    {"id":"e2","source":"start","target":"search_competitors"},
    {"id":"e3","source":"start","target":"search_tech"},
    {"id":"e4","source":"search_news","target":"analyze"},
    {"id":"e5","source":"search_competitors","target":"analyze"},
    {"id":"e6","source":"search_tech","target":"analyze"},
    {"id":"e7","source":"analyze","target":"format"},
    {"id":"e8","source":"format","target":"end"},
]

definition = {"nodes": nodes, "edges": edges}

print("\n[2] 创建工作流...")
r = requests.post(f"{BASE}/api/v1/workflows", headers=H, json={
    "name": "market-intel-brief",
    "display_name": "📰 行业情报简报生成",
    "description": "多Agent协同：三路联网搜索(新闻/竞品/技术)→研究员汇总→格式化Markdown简报",
    "category": "市场情报",
    "definition": definition,
})
print("  status:", r.status_code, r.json().get('msg'))
wf = r.json()['data']
wf_id = wf['id']
print("  wf_id =", wf_id)

# ===== 3. 创建绑定该工作流的 Agent =====
print("\n[3] 创建 workflow 架构 Agent...")
r = requests.post(f"{BASE}/api/v1/agents", headers=H, json={
    "name": "market-intel",
    "display_name": "📰 行业情报官",
    "description": "输入一个行业/主题，自动生成多源情报简报（新闻/竞品/技术/建议）",
    "architecture": "workflow",
    "workflow_id": wf_id,
    "system_prompt": "你是智启科技的行业情报官，输入一个主题后，会自动调度多路搜索、研究分析和格式化流程，生成专业的情报简报。",
    "rag_kb_ids": [kb_id],
})
print("  Agent:", r.status_code, r.json().get('msg'), "id =", r.json().get('data',{}).get('id'))

print("\n[Done] 工作流和 Agent 创建完成")
print(f"  Workflow ID: {wf_id}")
print(f"  KB ID: {kb_id}")
print(f"  Agent: market-intel")
