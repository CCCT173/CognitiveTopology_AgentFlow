import os, sys, zipfile, io, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 构造一个多文件 skill zip
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as zf:
    zf.writestr('hello-skill/SKILL.md', '''---
name: hello_skill
description: "Test multi-file bundle skill"
version: "1.0.0"
---
# Hello Skill

This skill demonstrates multi-file imports.

```python
from helper import greet
def run(params):
    return {"greeting": greet(params.get("name", "world"))}
```
''')
    zf.writestr('hello-skill/helper.py', '''def greet(name):
    return f"Hello, {name} from helper!"
''')
    zf.writestr('hello-skill/references/notes.txt', 'Just some notes.')

raw = buf.getvalue()

from app.db.session import SessionLocal
from app.services.skill_service import SkillService
from app.schemas.skill import SkillTestRequest

db = SessionLocal()
try:
    from app.models.skill import Skill
    existing = db.query(Skill).filter(Skill.name == 'hello_skill').first()
    if existing:
        db.delete(existing); db.commit()
    s = SkillService.import_skill_from_zip(db, raw)
    print(f"Imported skill: id={s.id} name={s.name} entry={s.config.get('entry')} files={s.config.get('bundle_count')}")
    print(f"Bundle files: {list((s.config.get('bundle') or {}).keys())}")

    res = SkillService.test_skill(db, s, SkillTestRequest(input_params={"name": "Agent"}))
    print("Test success:", res['success'])
    print("Output:", json.dumps(res.get('output'), ensure_ascii=False))
    if res.get('error'):
        print("Error:", res['error'])
    for line in res.get('logs', [])[-10:]:
        print("LOG:", line)
finally:
    db.close()
