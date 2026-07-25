import os, sys, zipfile, io, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.services.skill_service import SkillService
from app.schemas.skill import SkillTestRequest
from app.models.skill import Skill

# === Test 1: main.py 自动识别入口 ===
print("=== Test 1: auto-detect main.py entry ===")
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as zf:
    zf.writestr('calc/SKILL.md', '---\nname: calc_skill\ndescription: calc\n---\n# Calc')
    zf.writestr('calc/main.py', 'def run(params):\n    return {"sum": params.get("a",0)+params.get("b",0)}\n')
    zf.writestr('calc/math_utils.py', 'PI = 3.14159\n')
raw = buf.getvalue()

db = SessionLocal()
try:
    for n in ('calc_skill',):
        ex = db.query(Skill).filter(Skill.name==n).first()
        if ex: db.delete(ex)
    db.commit()
    s = SkillService.import_skill_from_zip(db, raw)
    print(f"Imported: entry={s.config.get('entry')} files={list(s.config['bundle'].keys())}")
    res = SkillService.test_skill(db, s, SkillTestRequest(input_params={"a":3,"b":4}))
    print("Output:", res.get('output'), "success:", res['success'])
finally:
    db.close()

# === Test 2: zip-slip 防护 ===
print("\n=== Test 2: zip-slip protection ===")
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as zf:
    zf.writestr('evil/SKILL.md', '---\nname: evil_skill\ndescription: x\n---\n# Evil')
    zf.writestr('../../etc/passwd', 'bad')
raw = buf.getvalue()
db = SessionLocal()
try:
    ex = db.query(Skill).filter(Skill.name=='evil_skill').first()
    if ex: db.delete(ex)
    db.commit()
    try:
        s = SkillService.import_skill_from_zip(db, raw)
        print("ERROR: zip-slip not blocked!")
    except ValueError as e:
        print(f"Correctly blocked: {e}")
finally:
    db.close()

# === Test 3: 危险模块 import 应被沙箱拦截 ===
print("\n=== Test 3: restricted import in sandbox ===")
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as zf:
    zf.writestr('bad/SKILL.md', '---\nname: bad_skill\ndescription: x\n---\n# Bad')
    zf.writestr('bad/main.py', 'import os\ndef run(p): os.system("echo hi")\n')
raw = buf.getvalue()
db = SessionLocal()
try:
    ex = db.query(Skill).filter(Skill.name=='bad_skill').first()
    if ex: db.delete(ex)
    db.commit()
    s = SkillService.import_skill_from_zip(db, raw)
    res = SkillService.test_skill(db, s, SkillTestRequest(input_params={}))
    print("success:", res['success'], "error:", res.get('error'))
finally:
    db.close()
