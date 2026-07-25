"""权限系统冒烟测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.services import user_service
from app.models.user import User
from app.core.security import hash_password, create_token
from app.models.agent import Agent as AgentModel
from app.models.skill import Skill
from app.models.workflow import Workflow
from app.models.rag import KnowledgeBase
import json

db = SessionLocal()
try:
    # 1. 创建两个测试用户: user1 (普通), admin2 (次级管理员)
    for acc, role, bind in [('perm_user1','user',None), ('perm_admin2','admin',None)]:
        ex = db.query(User).filter(User.account==acc).first()
        if ex: db.delete(ex)
    db.commit()
    u1 = User(username='perm_user1', account='perm_user1', email='p1@x.com',
              password_hash=hash_password('pass123'), role='user', enabled=True, is_active=True)
    a2 = User(username='perm_admin2', account='perm_admin2', email='p2@x.com',
              password_hash=hash_password('pass123'), role='admin', enabled=True, is_active=True)
    db.add_all([u1, a2]); db.commit(); db.refresh(u1); db.refresh(a2)

    # 2. 让 admin 用户创建一个 Agent, Skill, Workflow, KB
    agent = AgentModel(name='admin_private_agent', display_name='Admin Secret', system_prompt='x', created_by=a2.user_id, enabled=True)
    sk = Skill(name='admin_private_skill', content='---\nname: x\n---', created_by=a2.user_id, is_active=True)
    wf = Workflow(name='admin_private_wf', display_name='Admin WF', created_by=a2.user_id, enabled=True)
    kb = KnowledgeBase(name='admin_private_kb', created_by=a2.user_id)
    db.add_all([agent, sk, wf, kb]); db.commit()

    print("=== Test 1: 匿名访问 /agents 列表应被 401 ===")
    import urllib.request, urllib.error
    def call(method, path, token=None, data=None):
        url = f'http://127.0.0.1:8001{path}'
        headers = {'Content-Type':'application/json'}
        if token: headers['Authorization']=f'Bearer {token}'
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            r = urllib.request.urlopen(req)
            return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    s, _ = call('GET','/api/v1/agents')
    print(f'  匿名 GET /agents -> {s} (期望 401)')
    assert s == 401, '匿名访问应被拦截!'

    print("=== Test 2: user1 登录后 GET /agents 看不到 admin_private_agent ===")
    # 登录获取token
    s, body = call('POST','/api/v1/auth/login', data={'account':'perm_user1','password':'pass123'})
    tok1 = body['data']['token']
    s, body = call('GET','/api/v1/agents', token=tok1)
    names = [a['name'] for a in body['data']]
    print(f'  user1 agents: {names}')
    assert 'admin_private_agent' not in names, '普通用户不应看到别人的Agent!'

    print("=== Test 3: user1 尝试 GET /agents/admin_private_agent 详情应 403 ===")
    s, body = call('GET','/api/v1/agents/admin_private_agent', token=tok1)
    print(f'  user1 GET agent -> {s} (期望 403), msg: {body.get("msg","")[:50]}')
    assert s == 403

    print("=== Test 4: user1 尝试 DELETE /agents/admin_private_agent 应 403 ===")
    s, body = call('DELETE','/api/v1/agents/admin_private_agent', token=tok1)
    print(f'  user1 DELETE agent -> {s} (期望 403)')
    assert s == 403

    print("=== Test 5: user1 尝试 PATCH 别人的 workflow 应 403 ===")
    s, body = call('PATCH',f'/api/v1/workflows/{wf.id}', token=tok1, data={'display_name':'hacked'})
    print(f'  user1 PATCH workflow -> {s} (期望 403)')
    assert s == 403

    print("=== Test 6: user1 调用 /users/admins 公开接口(注册用) 应允许 ===")
    s, body = call('GET','/api/v1/users/admins')  # 匿名也能访问
    print(f'  匿名 GET /users/admins -> {s} (期望 200)')
    assert s == 200

    print("=== Test 7: user1 访问 /users 列表(admin)应 403 ===")
    s, body = call('GET','/api/v1/users', token=tok1)
    print(f'  user1 GET /users -> {s} (期望 403)')
    assert s == 403

    print("=== Test 8: user1 访问 /admin/users 前端受 RequireAuth requireAdmin 守卫(后端也挡) ===")
    s, body = call('GET','/api/v1/system/stats', token=tok1)
    print(f'  user1 GET /system/stats -> {s} (期望 403)')
    assert s == 403

    print("=== Test 9: admin2 能看到自己的 Agent ===")
    s, body = call('POST','/api/v1/auth/login', data={'account':'perm_admin2','password':'pass123'})
    tok2 = body['data']['token']
    s, body = call('GET','/api/v1/agents', token=tok2)
    names = [a['name'] for a in body['data']]
    print(f'  admin2 agents: {names}')
    assert 'admin_private_agent' in names

    print("=== Test 10: user1 不能把自己升级为 super_admin ===")
    # setRole 接口需要 super_admin, admin2 是 admin 应被拒
    s, body = call('POST',f'/api/v1/users/{u1.user_id}/role', token=tok2, data={'role':'super_admin'})
    print(f'  admin2 尝试任命 super_admin -> {s} (期望 403)')
    assert s == 403

    print("\n✅ 所有权限测试通过!")
finally:
    # 清理
    for acc in ['perm_user1','perm_admin2']:
        ex = db.query(User).filter(User.account==acc).first()
        if ex:
            db.query(AgentModel).filter(AgentModel.created_by==ex.user_id).delete()
            db.query(Skill).filter(Skill.created_by==ex.user_id).delete()
            db.query(Workflow).filter(Workflow.created_by==ex.user_id).delete()
            db.query(KnowledgeBase).filter(KnowledgeBase.created_by==ex.user_id).delete()
            db.delete(ex)
    db.commit()
    db.close()
