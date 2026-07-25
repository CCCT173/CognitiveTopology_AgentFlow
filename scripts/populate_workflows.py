"""
给所有业务工作流填充真实 DAG 定义（leave-request/expense-reimburse/onboarding-flow/code-review-flow/doc-qa-pipeline）
让它们在编辑器里能看到节点和连线。
"""
import sys, os, json, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://127.0.0.1:8001"

def token():
    r = requests.post(f"{BASE}/api/v1/auth/login", json={'account':'admin','password':'admin123'})
    return r.json()['data']['token']

T = token()
H = {'Authorization': f'Bearer {T}', 'Content-Type': 'application/json'}

def patch(wf_name, definition, display_name=None, description=None):
    # 找到 workflow by name
    r = requests.get(f"{BASE}/api/v1/workflows", headers=H)
    wfs = r.json()['data']
    wf = next((w for w in wfs if w['name'] == wf_name), None)
    if not wf:
        print(f"  ! not found: {wf_name}"); return
    body = {'definition': definition}
    if display_name: body['display_name'] = display_name
    if description: body['description'] = description
    r = requests.patch(f"{BASE}/api/v1/workflows/{wf['id']}", headers=H, json=body)
    print(f"  {wf_name} (id={wf['id']}): {r.status_code} {r.json().get('msg')}")

# ===== 1. 请假审批流 =====
leave_def = {
  "nodes": [
    {"id":"start","type":"start","name":"员工提交","position":{"x":60,"y":200},"config":{}},
    {"id":"mgr_approve","type":"llm","name":"主管审批建议","position":{"x":300,"y":200},
     "config":{"system_prompt":"你是请假审批助手，根据请假信息给出审批建议。",
               "prompt":"员工申请请假：{{input}}\n\n请给出：1) 建议批准/拒绝 2) 理由 3) 是否需要HR备案",
               "temperature":0.3}},
    {"id":"check_len","type":"condition","name":"假期>3天?","position":{"x":580,"y":200},
     "config":{"expression":"'3天' in '{{input}}' or int('{{input}}'.split('天')[0].strip()[-1:]) > 3 if '天' in '{{input}}' else False"}},
    {"id":"hr_record","type":"tool","name":"HR备案","position":{"x":860,"y":100},
     "config":{"tool_name":"calculator","params":{"expression":"1"}}},
    {"id":"notify","type":"llm","name":"生成通知","position":{"x":860,"y":300},
     "config":{"system_prompt":"你是行政通知助手，生成简洁的审批结果通知。",
               "prompt":"请假已审批：{{input}}\n主管意见：{{mgr_approve.text}}\n请生成员工通知。",
               "temperature":0.5}},
    {"id":"end","type":"end","name":"完成","position":{"x":1140,"y":200},"config":{"output_key":"{{notify.text}}"}},
  ],
  "edges": [
    {"id":"e1","source":"start","target":"mgr_approve"},
    {"id":"e2","source":"mgr_approve","target":"check_len"},
    {"id":"e3","source":"check_len","target":"hr_record","condition":"true"},
    {"id":"e4","source":"check_len","target":"notify","condition":"false"},
    {"id":"e5","source":"hr_record","target":"notify"},
    {"id":"e6","source":"notify","target":"end"},
  ],
}
patch("leave-request", leave_def)

# ===== 2. 报销审批流 =====
expense_def = {
  "nodes": [
    {"id":"start","type":"start","name":"员工提交","position":{"x":60,"y":200},"config":{}},
    {"id":"check_policy","type":"llm","name":"核对制度","position":{"x":280,"y":200},
     "config":{"system_prompt":"你是财务助手，核对报销是否符合公司差旅/招待制度。",
               "prompt":"报销信息：{{input}}\n核对：1) 金额是否在标准内 2) 发票是否齐全 3) 事项是否合理","temperature":0.2}},
    {"id":"mgr_approve","type":"llm","name":"主管审批","position":{"x":520,"y":200},
     "config":{"system_prompt":"","prompt":"报销：{{input}}\n财务核对：{{check_policy.text}}\n请给出审批意见","temperature":0.3}},
    {"id":"finance_review","type":"llm","name":"财务审核","position":{"x":760,"y":200},
     "config":{"system_prompt":"","prompt":"请做最终财务审核并安排打款计划","temperature":0.2}},
    {"id":"pay","type":"tool","name":"出纳打款","position":{"x":1000,"y":200},
     "config":{"tool_name":"calculator","params":{"expression":"0"}}},
    {"id":"end","type":"end","name":"完成","position":{"x":1240,"y":200},
     "config":{"output_key":"{{finance_review.text}}"}},
  ],
  "edges": [
    {"id":"e1","source":"start","target":"check_policy"},
    {"id":"e2","source":"check_policy","target":"mgr_approve"},
    {"id":"e3","source":"mgr_approve","target":"finance_review"},
    {"id":"e4","source":"finance_review","target":"pay"},
    {"id":"e5","source":"pay","target":"end"},
  ],
}
patch("expense-reimburse", expense_def)

# ===== 3. 入职流程 =====
onboarding_def = {
  "nodes": [
    {"id":"start","type":"start","name":"HR录入","position":{"x":60,"y":200},"config":{}},
    {"id":"it_setup","type":"agent","name":"IT开通账号","position":{"x":280,"y":100},
     "config":{"agent_name":"it-helpdesk","message":"为新员工开通账号，信息：{{input}}"}},
    {"id":"mentor_assign","type":"llm","name":"分配Mentor","position":{"x":280,"y":300},
     "config":{"system_prompt":"你是HR助手，根据部门分配合适的mentor。",
               "prompt":"新员工：{{input}}\n根据部门和职位推荐一位资深员工作为Mentor","temperature":0.3}},
    {"id":"welcome_email","type":"agent","name":"欢迎邮件","position":{"x":560,"y":200},
     "config":{"agent_name":"email-writer",
               "message":"写一封新员工入职欢迎邮件，新员工信息：{{input}}，Mentor：{{mentor_assign.text}}"}},
    {"id":"end","type":"end","name":"完成","position":{"x":840,"y":200},
     "config":{"output_key":"{{welcome_email.reply}}"}},
  ],
  "edges": [
    {"id":"e1","source":"start","target":"it_setup"},
    {"id":"e2","source":"start","target":"mentor_assign"},
    {"id":"e3","source":"it_setup","target":"welcome_email"},
    {"id":"e4","source":"mentor_assign","target":"welcome_email"},
    {"id":"e5","source":"welcome_email","target":"end"},
  ],
}
patch("onboarding-flow", onboarding_def)

# ===== 4. 代码审查流 =====
code_review_def = {
  "nodes": [
    {"id":"start","type":"start","name":"提交MR","position":{"x":60,"y":200},"config":{}},
    {"id":"lint","type":"tool","name":"静态检查","position":{"x":280,"y":200},
     "config":{"tool_name":"calculator","params":{"expression":"0"}}},
    {"id":"ai_review","type":"agent","name":"AI审查","position":{"x":520,"y":200},
     "config":{"agent_name":"code-reviewer","message":"审查这段代码的规范性和安全性：{{input}}"}},
    {"id":"human_review","type":"llm","name":"人工Review提示","position":{"x":780,"y":200},
     "config":{"system_prompt":"","prompt":"AI审查结果：{{ai_review.reply}}\n请生成给Reviewer的提示清单","temperature":0.3}},
    {"id":"end","type":"end","name":"完成","position":{"x":1040,"y":200},
     "config":{"output_key":"{{human_review.text}}"}},
  ],
  "edges": [
    {"id":"e1","source":"start","target":"lint"},
    {"id":"e2","source":"lint","target":"ai_review"},
    {"id":"e3","source":"ai_review","target":"human_review"},
    {"id":"e4","source":"human_review","target":"end"},
  ],
}
patch("code-review-flow", code_review_def)

# ===== 5. 文档问答链 =====
doc_qa_def = {
  "nodes": [
    {"id":"start","type":"start","name":"文档上传","position":{"x":60,"y":200},"config":{}},
    {"id":"chunk","type":"tool","name":"分块","position":{"x":280,"y":200},
     "config":{"tool_name":"calculator","params":{"expression":"0"}}},
    {"id":"retrieve","type":"tool","name":"检索","position":{"x":500,"y":200},
     "config":{"tool_name":"rag_search","params":{"query":"{{input}}","top_k":5}}},
    {"id":"answer","type":"llm","name":"生成答案","position":{"x":740,"y":200},
     "config":{"system_prompt":"你是文档问答助手，严格基于检索到的资料回答问题。",
               "prompt":"问题：{{input}}\n\n参考资料：{{retrieve.result}}\n\n给出准确答案，引用来源。",
               "temperature":0.3}},
    {"id":"end","type":"end","name":"输出","position":{"x":980,"y":200},
     "config":{"output_key":"{{answer.text}}"}},
  ],
  "edges": [
    {"id":"e1","source":"start","target":"chunk"},
    {"id":"e2","source":"chunk","target":"retrieve"},
    {"id":"e3","source":"retrieve","target":"answer"},
    {"id":"e4","source":"answer","target":"end"},
  ],
}
patch("doc-qa-pipeline", doc_qa_def)

print("\n完成")
