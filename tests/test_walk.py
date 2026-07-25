"""真人交互走查:通过前端代理(5173)走后端,模拟浏览器操作"""
import io, uuid, time, requests as R

FE = 'http://localhost:5173'
BE = 'http://127.0.0.1:8001'
s = R.Session()
TAG = uuid.uuid4().hex[:6]
ok = 0; fail = 0

def check(name, cond, detail=''):
    global ok, fail
    if cond: ok += 1; print(f'  [OK] {name}')
    else: fail += 1; print(f'  [FAIL] {name} {detail[:120]}')

# 1. 前端静态资源
r = s.get(f'{FE}/', timeout=5)
check('前端首页 HTML', r.status_code==200 and '<div id="root">' in r.text)

# 2. 代理 /api 到后端(首次 Vite 编译可能慢,超时加大)
import time
for _ in range(3):
    try:
        r = s.get(f'{FE}/api/v1/meta/config', timeout=30)
        break
    except Exception as e:
        time.sleep(2)
check('前端代理 /api 通后端', r.status_code==200 and r.json()['code']==0, f'{r.status_code} {r.text[:100]}')

# 3. 代理 /files 到后端 (无文件返回 404 即可,只要不 502)
r = s.get(f'{FE}/files/icons/__nonexist__', timeout=5)
check('前端代理 /files', r.status_code in (404, 200))

# 4. 登录
r = s.post(f'{BE}/api/v1/auth/login', json={'account':'admin','password':'admin123'})
check('admin 登录', r.status_code==200 and r.json()['code']==0)
t = r.json()['data']['token']
s.headers['Authorization'] = f'Bearer {t}'

# 5. meta 选项
for p in ['providers','loaders','splitters','architectures','frameworks','tools']:
    r = s.get(f'{BE}/api/v1/meta/{p}')
    check(f'meta/{p}', r.status_code==200 and isinstance(r.json()['data'], (list, dict)))

# 6. 创建 KB + 上传
kb = s.post(f'{BE}/api/v1/rag/kbs', json={'name':f'walk_{TAG}','loader':'text','splitter_type':'sentence','chunk_size':200,'chunk_overlap':0}).json()['data']
check('创建 KB', kb['id'])
up = s.post(f'{BE}/api/v1/rag/kbs/{kb["id"]}/upload',
            files={'file': ('hello.txt', io.BytesIO('Python是编程语言. FastAPI好用. Milvus向量库.'.encode()), 'text/plain')},
            data={'loader':'text','splitter_type':'sentence','chunk_size':'200','chunk_overlap':'0'})
check('上传文档', up.json()['code']==0, up.text[:200])
doc_id = up.json()['data']['document_id']
for _ in range(30):
    d = s.get(f'{BE}/api/v1/rag/kbs/{kb["id"]}/documents').json()['data']
    doc = next((x for x in d if x['id']==doc_id), None)
    if doc and doc['status']=='indexed': break
    time.sleep(0.3)
check('文档 indexed', doc and doc['status']=='indexed', str(doc))

# 7. 检索
hits = s.post(f'{BE}/api/v1/rag/query', json={'kb_id':kb['id'],'query':'Python','top_k':3}).json()['data']
check('检索 Python', len(hits)>=1)

# 8. 创建 Agent + 对话
ag = s.post(f'{BE}/api/v1/agents', json={'name':f'walk_agent_{TAG}','display_name':'Walk测试','architecture':'react',
    'tools':['rag_search'],'rag_kb_ids':[kb['id']],'llm_config':{'temperature':0.3},'max_iterations':3}).json()['data']
check('创建 Agent', ag['id'])
chat = s.post(f'{BE}/api/v1/chat', json={'agent_name':f'walk_agent_{TAG}','message':'Python是什么'}).json()['data']
check('对话返回 reply', bool(chat.get('reply')), str(chat)[:200])
check('返回 thread_id', bool(chat.get('thread_id')))
check('tool_calls 是 list', isinstance(chat.get('tool_calls'), list))
tid = chat['thread_id']
th = s.get(f'{BE}/api/v1/chat/threads/{tid}').json()['data']
check('会话历史含消息', len(th['messages'])>=2, str(th)[:200])

# 9. 工作流
wf = s.post(f'{BE}/api/v1/workflows', json={'name':f'walk_wf_{TAG}','definition':{'nodes':[],'edges':[]}}).json()['data']
check('创建工作流', wf['id'])
check('工作流列表', len(s.get(f'{BE}/api/v1/workflows').json()['data'])>=1)

# 10. 群组
g = s.post(f'{BE}/api/v1/groups', json={'name':f'walk_g_{TAG}','description':'E2E'}).json()['data']
gid = g['id']
check('建群', gid)
check('群成员', len(s.get(f'{BE}/api/v1/groups/{gid}/members').json()['data'])>=1)
s.post(f'{BE}/api/v1/groups/{gid}/agents/{ag["id"]}')
msgs = s.post(f'{BE}/api/v1/groups/{gid}/messages', json={'content':'hello'}).json()['data']
check('群聊发消息', len(msgs)>=1)
msgs2 = s.post(f'{BE}/api/v1/groups/{gid}/messages', json={'content':'@agent','agent_name':f'walk_agent_{TAG}'}).json()['data']
check('@agent 群聊返回多条', len(msgs2)>=1)
s.delete(f'{BE}/api/v1/groups/{gid}')

# 11. 个人资料
me = s.patch(f'{BE}/api/v1/auth/me', json={'username':'admin_walk'}).json()
check('改用户名', me['code']==0 and me['data']['username']=='admin_walk')
s.patch(f'{BE}/api/v1/auth/me', json={'username':'admin'})  # 还原

# 12. 清理
s.delete(f'{BE}/api/v1/agents/walk_agent_{TAG}')
s.delete(f'{BE}/api/v1/rag/kbs/{kb["id"]}')
s.delete(f'{BE}/api/v1/workflows/{wf["id"]}')

print(f'\n{"="*50}\n通过: {ok}  失败: {fail}')
