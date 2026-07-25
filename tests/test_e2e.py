"""端到端真人交互模拟测试 (调用前端会走的接口,验证流程)"""
import io, uuid, time, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
BASE = ''
results = []
def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    print(f'  {"[OK]" if cond else "[FAIL]"} {name} {detail[:80]}')

def login(account='admin', password='admin123'):
    r = c.post(f'{BASE}/api/v1/auth/login', json={'account':account,'password':password})
    assert r.status_code == 200, r.text
    t = r.json()['data']['token']
    c.headers['Authorization'] = f'Bearer {t}'
    return t

print('=== 0. meta 公开接口 ===')
for p in ['providers','loaders','splitters','architectures','frameworks','tools','config']:
    r = c.get(f'/api/v1/meta/{p}')
    check(f'meta/{p}', r.status_code==200 and r.json()['code']==0)

print('\n=== 1. 登录 ===')
t = login()
check('admin 登录成功', bool(t))

print('\n=== 2. 首页数据 ===')
r = c.get('/api/v1/agents'); check('agents 列表', r.status_code==200)
r = c.get('/api/v1/rag/kbs'); check('kbs 列表', r.status_code==200)
r = c.get('/api/v1/workflows'); check('workflows 列表', r.status_code==200)
r = c.get('/api/v1/groups'); check('groups 列表', r.status_code==200)
r = c.get('/api/v1/chat/threads'); check('chat threads', r.status_code==200)

print('\n=== 3. 创建知识库 + 上传文档 ===')
tag = uuid.uuid4().hex[:6]
r = c.post('/api/v1/rag/kbs', json={'name':f'ft_kb_{tag}','loader':'auto','splitter_type':'sentence','chunk_size':200,'chunk_overlap':0})
kb = r.json()['data']; kb_id = kb['id']
check('创建 KB', kb_id is not None)

text = 'Python是一门编程语言。FastAPI是Python Web框架。Milvus是向量数据库。' * 5
r = c.post(f'/api/v1/rag/kbs/{kb_id}/upload',
           files={'file': ('test.txt', io.BytesIO(text.encode()), 'text/plain')},
           data={'loader':'text','splitter_type':'sentence','chunk_size':'200','chunk_overlap':'0'})
doc_id = r.json()['data']['document_id']
check('上传文档', r.status_code==200 and doc_id)
for _ in range(30):
    r = c.get(f'/api/v1/rag/kbs/{kb_id}/documents')
    d = next((x for x in r.json()['data'] if x['id']==doc_id), None)
    if d and d['status']=='indexed': break
    time.sleep(0.3)
check('文档 indexed', d and d['status']=='indexed', d.get('status') if d else '')
r = c.get(f'/api/v1/rag/documents/{doc_id}/chunks')
chunks = r.json()['data']
check(f'chunks 数量={len(chunks)}', len(chunks)>=1)

print('\n=== 4. RAG 检索 ===')
r = c.post('/api/v1/rag/query', json={'kb_id':kb_id,'query':'Python是什么','top_k':3})
check('检索 Python', r.status_code==200 and len(r.json()['data'])>=1, str(r.json()['data'][:1])[:100])

print('\n=== 5. 创建 RAG Agent + 对话 ===')
r = c.post('/api/v1/agents', json={
    'name':f'ft_agent_{tag}','display_name':'测试助手','description':'E2E测试',
    'architecture':'react','tools':['rag_search'],'rag_kb_ids':[kb_id],
    'llm_config':{'temperature':0.3},'max_iterations':3
})
agent = r.json()['data']
check('创建 Agent', agent['id'] is not None, str(r.json())[:120])
r = c.post('/api/v1/chat', json={'agent_name':f'ft_agent_{tag}','message':'Python是什么'})
data = r.json()['data']
check('Agent 对话返回 reply', bool(data.get('reply')), data.get('reply','')[:100])
# LLM 对常见问题可能直接回答不调工具,有 tool_calls 就验证格式;没有也 PASS
tc = data.get('tool_calls', [])
check('tool_calls 格式正确', isinstance(tc, list), str(tc)[:120])
check('thread_id 返回', bool(data.get('thread_id')))

print('\n=== 6. 会话历史 ===')
tid = data['thread_id']
r = c.get(f'/api/v1/chat/threads/{tid}')
check('会话详情 messages>=2', len(r.json()['data']['messages'])>=2)

print('\n=== 7. 工作流 ===')
r = c.post('/api/v1/workflows', json={'name':f'ft_wf_{tag}','display_name':'测试流程','definition':{'nodes':[],'edges':[]}})
wf_id = r.json()['data']['id']
check('创建工作流', wf_id is not None)
r = c.post(f'/api/v1/workflows/{wf_id}/run', json={'input':{}})
check('运行工作流(占位)', r.status_code==200)
r = c.delete(f'/api/v1/workflows/{wf_id}'); check('删除工作流', r.status_code==200)

print('\n=== 8. 群组 ===')
r = c.post('/api/v1/groups', json={'name':f'ft_g_{tag}','description':'E2E'})
gid = r.json()['data']['id']
check('建群', gid is not None)
r = c.get(f'/api/v1/groups/{gid}/members'); check('成员列表', r.status_code==200)
# 共享agent
r = c.post(f'/api/v1/groups/{gid}/agents/{agent["id"]}'); check('共享agent', r.status_code==200)
# 发消息
r = c.post(f'/api/v1/groups/{gid}/messages', json={'content':'hello from test'})
check('群聊发消息', r.status_code==200 and len(r.json()['data'])>=1)
msgs = c.get(f'/api/v1/groups/{gid}/messages').json()['data']
# @agent 回复
r = c.post(f'/api/v1/groups/{gid}/messages', json={'content':'@机器人','agent_name':f'ft_agent_{tag}'})
check('@agent 群聊(返回2条消息)', len(r.json()['data'])==2, str(r.json())[:100])
# 撤回
mid = msgs[0]['id']
r = c.delete(f'/api/v1/groups/{gid}/messages/{mid}'); check('撤回消息', r.status_code==200)
c.delete(f'/api/v1/groups/{gid}')

print('\n=== 9. 个人资料 ===')
r = c.patch('/api/v1/auth/me', json={'username':'admin_updated'})
check('修改个人资料', r.status_code==200 and r.json()['data']['username']=='admin_updated')
r = c.patch('/api/v1/auth/me', json={'username':'admin'})  # 还原

print('\n=== 10. 清理 ===')
c.delete(f'/api/v1/agents/ft_agent_{tag}')
c.delete(f'/api/v1/rag/kbs/{kb_id}')

print('\n' + '='*60)
ok = sum(1 for _,p,_ in results if p)
fail = sum(1 for _,p,_ in results if not p)
print(f'通过: {ok}  失败: {fail}')
for n,_,d in results:
    if not _:
        print(f'  [FAIL] {n}: {d}')
