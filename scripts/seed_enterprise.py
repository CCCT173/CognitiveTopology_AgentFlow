"""
数据库重置 + 企业示例数据填充
- 清理所有非内置测试数据（保留 admin 账号 1，保留 3 个内置 skills）
- 创建 34 个员工账号，形成真实组织树
- 创建 3 个知识库，带企业文档（员工手册/IT制度/HR政策）
- 创建若干有意义的 Agent、Workflow
- 创建 4 个群组，共享不同组合的 Agent / KB / Workflow / Skill
"""
import sys, os, io, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal, engine
from app.models.user import User
from app.models.agent import Agent
from app.models.workflow import Workflow, WorkflowRun
from app.models.rag import KnowledgeBase, Document
from app.models.group import Group, GroupMember, GroupAgent, GroupKB, GroupWorkflow, GroupSkill, GroupMessage, GroupNotice
from app.models.skill import Skill
from app.core.security import hash_password
from app.schemas.rag import KBCreate
from app.services import rag_service
from sqlalchemy import text, select

db = SessionLocal()

try:
    # ========== 清理 ==========
    print("[1/6] 清理旧测试数据...")
    db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    for tbl in ['group_notice_reads', 'group_notices', 'group_messages', 'group_workflows', 'group_skills',
                'group_agents', 'group_kbs', 'group_members', 'work_groups',
                'workflow_runs', 'chunks', 'documents', 'knowledge_bases', 'workflows', 'agents']:
        db.execute(text(f"DELETE FROM {tbl}"))
    db.execute(text("DELETE FROM users WHERE user_id NOT IN (1)"))
    for tbl in ['users', 'agents', 'workflows', 'work_groups', 'knowledge_bases', 'documents',
                'group_notices', 'group_messages', 'group_workflows', 'group_skills']:
        db.execute(text(f"ALTER TABLE {tbl} AUTO_INCREMENT = 100"))
    db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    db.commit()
    print("  清理完成")

    # ========== 更新 admin ==========
    admin = db.get(User, 1)
    admin.username = '陈启明'; admin.account = 'admin'; admin.email = 'chen.qiming@corp.cn'
    admin.title = 'CEO / 首席执行官'; admin.department = '管理层'; admin.company = '智启科技'
    admin.location = '北京'; admin.bio = '带领团队打造下一代企业级 AI Agent 平台。'
    db.commit()

    # ========== 34 个员工组织树 ==========
    print("[2/6] 创建 34 个员工组织...")
    employees = [
        ('li.wei',       '李伟',     'li.wei@corp.cn',       'CTO / 首席技术官',       '技术中心'),
        ('wang.fang',    '王芳',     'wang.fang@corp.cn',    'CFO / 首席财务官',       '财务部'),
        ('zhang.lei',    '张磊',     'zhang.lei@corp.cn',    'COO / 首席运营官',       '运营中心'),
        ('chen.xiaoyu',  '陈骁宇',   'chen.xiaoyu@corp.cn',  '研发总监',              '研发部'),
        ('liu.meng',     '刘梦',     'liu.meng@corp.cn',     '产品总监',              '产品部'),
        ('zhao.jian',    '赵健',     'zhao.jian@corp.cn',    '算法总监',              'AI 实验室'),
        ('sun.ting',     '孙婷',     'sun.ting@corp.cn',     '运维负责人',            '运维部'),
        ('wu.hao',       '吴昊',     'wu.hao@corp.cn',       '后端技术主管',          '研发一组'),
        ('zhou.lin',     '周琳',     'zhou.lin@corp.cn',     '前端技术主管',          '研发二组'),
        ('huang.tao',    '黄涛',     'huang.tao@corp.cn',    '测试负责人',            '质量保障组'),
        ('xu.ran',       '徐然',     'xu.ran@corp.cn',       '高级后端工程师',        '研发一组'),
        ('feng.yu',      '冯宇',     'feng.yu@corp.cn',      '高级后端工程师',        '研发一组'),
        ('he.shuai',     '何帅',     'he.shuai@corp.cn',     '后端工程师',            '研发一组'),
        ('deng.xin',     '邓欣',     'deng.xin@corp.cn',     '前端工程师',            '研发二组'),
        ('cao.yue',      '曹悦',     'cao.yue@corp.cn',      '前端工程师',            '研发二组'),
        ('yan.qi',       '严琦',     'yan.qi@corp.cn',       '测试工程师',            '质量保障组'),
        ('bai.jun',      '白俊',     'bai.jun@corp.cn',      '测试工程师',            '质量保障组'),
        ('lin.yun',      '林芸',     'lin.yun@corp.cn',      '高级产品经理',          '产品部'),
        ('guo.jing',     '郭静',     'guo.jing@corp.cn',     '产品经理',              '产品部'),
        ('pan.yang',     '潘阳',     'pan.yang@corp.cn',     'UX 设计师',             '设计组'),
        ('tang.chao',    '唐超',     'tang.chao@corp.cn',    '高级算法工程师',        'AI 实验室'),
        ('ye.fan',       '叶凡',     'ye.fan@corp.cn',       '算法工程师',            'AI 实验室'),
        ('jiang.ting',   '蒋婷',     'jiang.ting@corp.cn',   '数据工程师',            'AI 实验室'),
        ('fan.li',       '范丽',     'fan.li@corp.cn',       '财务主管',              '财务部'),
        ('lu.yao',       '陆瑶',     'lu.yao@corp.cn',       '会计',                  '财务部'),
        ('ren.jie',      '任杰',     'ren.jie@corp.cn',      '市场总监',              '市场部'),
        ('kong.qin',     '孔芹',     'kong.qin@corp.cn',     '市场经理',              '市场部'),
        ('cui.wei',      '崔伟',     'cui.wei@corp.cn',      '销售总监',              '销售部'),
        ('bai.xiao',     '白晓',     'bai.xiao@corp.cn',     '大客户经理',            '销售部'),
        ('xue.mei',      '薛梅',     'xue.mei@corp.cn',      '客户经理',              '销售部'),
        ('hao.yan',      '郝燕',     'hao.yan@corp.cn',      'HR 主管',               '人力资源部'),
        ('ma.li',        '马丽',     'ma.li@corp.cn',        'HR 专员',               '人力资源部'),
        ('du.qiang',     '杜强',     'du.qiang@corp.cn',     '行政主管',              '行政部'),
        ('tian.yu',      '田宇',     'tian.yu@corp.cn',      '行政专员',              '行政部'),
    ]
    # 上级关系 (account -> manager_account)
    managers = {
        'li.wei':'admin', 'wang.fang':'admin', 'zhang.lei':'admin',
        'chen.xiaoyu':'li.wei', 'liu.meng':'li.wei', 'zhao.jian':'li.wei', 'sun.ting':'li.wei',
        'wu.hao':'chen.xiaoyu', 'zhou.lin':'chen.xiaoyu', 'huang.tao':'chen.xiaoyu',
        'xu.ran':'wu.hao', 'feng.yu':'wu.hao', 'he.shuai':'wu.hao',
        'deng.xin':'zhou.lin', 'cao.yue':'zhou.lin',
        'yan.qi':'huang.tao', 'bai.jun':'huang.tao',
        'lin.yun':'liu.meng', 'guo.jing':'liu.meng', 'pan.yang':'liu.meng',
        'tang.chao':'zhao.jian', 'ye.fan':'zhao.jian', 'jiang.ting':'zhao.jian',
        'fan.li':'wang.fang', 'lu.yao':'fan.li',
        'ren.jie':'zhang.lei', 'cui.wei':'zhang.lei', 'hao.yan':'zhang.lei', 'du.qiang':'zhang.lei',
        'kong.qin':'ren.jie',
        'bai.xiao':'cui.wei', 'xue.mei':'cui.wei',
        'ma.li':'hao.yan',
        'tian.yu':'du.qiang',
    }
    pw = hash_password('abc12345')
    account_map = {'admin': admin.user_id}
    created = {}
    for acc, name, email, title, dept in employees:
        u = User(
            username=name, account=acc, email=email,
            password_hash=pw, role='user',
            title=title, department=dept, company='智启科技',
            location='上海' if dept in ['销售部','市场部'] else '北京',
            enabled=True, is_active=True,
        )
        db.add(u); db.flush()
        created[acc] = u
        account_map[acc] = u.user_id
    for acc, mgr_acc in managers.items():
        created[acc].manager_id = account_map[mgr_acc]
    db.commit()
    print(f"  创建 {len(created)} 个员工")

    # ========== 知识库 + 企业文档 ==========
    print("[3/6] 创建知识库 + 企业文档...")
    kb_defs = [
        ('员工手册',     '智启科技员工手册，包含公司文化、考勤、福利、报销制度等'),
        ('IT 安全制度',  '信息安全、密码管理、数据分级、设备使用规范'),
        ('HR 政策',      '招聘、入职、晋升、绩效、离职流程说明'),
    ]
    kbs = {}
    for name, desc in kb_defs:
        kb = rag_service.create_kb(db, KBCreate(name=name, description=desc, splitter_type='sentence', chunk_size=400, chunk_overlap=50), user_id=1)
        kbs[name] = kb
    db.commit()
    handbook = """# 智启科技员工手册

## 第一章 公司简介
智启科技成立于 2023 年，专注于企业级 AI Agent 平台研发，我们的愿景是"让每一位知识工作者都拥有自己的智能助手"。

公司总部位于北京中关村，上海设有销售和市场分部，现有员工 34 人，研发人员占比超过 60%。

## 第二章 工作时间
- 标准工作时间：周一至周五 9:30-18:30，午休 1 小时（12:00-13:00）
- 弹性上下班：早晚可浮动 30 分钟，即 9:00-10:00 之间到岗，对应 18:00-19:00 离岗
- 加班需提前在 OA 系统申请，经部门负责人审批后生效；工作日加班可调休或按 1.5 倍时薪结算
- 法定节假日按国家规定执行，部分岗位（运维、值班）实行轮班制

## 第三章 考勤制度
- 每日两次打卡：到岗和离岗
- 忘打卡每月可申请 3 次补卡，超出按事假处理
- 迟到 30 分钟内扣 50 元/次，30 分钟以上按半天事假
- 病假需提供二级以上医院证明，带薪病假全年 10 天
- 事假需提前 1 天申请，事假期间不计发薪

## 第四章 薪酬福利
- 发薪日：每月 10 日发放上月工资，遇节假日提前
- 五险一金：入职即按实际工资基数足额缴纳
- 年终奖：根据公司业绩和个人绩效，通常为 1-4 个月薪水，每年 2 月发放
- 餐补：工作日每餐 35 元，按实际出勤天数计算
- 交通补贴：每月 300 元
- 年度体检：每年 5 月统一组织
- 带薪年假：入职满 1 年 5 天，每增加 1 年 +1 天，上限 15 天
- 节日福利：春节、端午、中秋发放礼品或购物卡
- 生日福利：生日当月 200 元购物卡 + 半天调休

## 第五章 绩效考核
- 考核周期：每季度一次（Q1/Q2/Q3/Q4），年终综合评定
- 考核维度：业绩 60% + 能力 20% + 价值观 20%
- 等级：S(卓越 5%)、A(优秀 20%)、B(良好 60%)、C(待改进 10%)、D(不合格 5%)
- C/D 员工需制定改进计划（PIP），连续两次 C 或一次 D 将面临调岗或解除合同

## 第六章 培训与发展
- 新员工入职培训：入职第一周统一进行（公司介绍、制度、安全、工具使用）
- 导师制度：每位新员工配备一位资深员工作为 Mentor，为期 3 个月
- 年度学习基金：每人每年 5000 元，可用于购买书籍、课程、参加行业会议
- 内部技术分享：每周五下午 16:00-17:30，各团队轮流分享

## 第七章 报销制度
- 差旅：高铁二等座/经济舱，住宿一线城市≤500/晚、二线≤400/晚
- 招待：需提前向部门负责人申请，单次 500 元以下主管审批，500-2000 元总监，2000+ CEO
- 报销周期：每月 5 日、20 日统一提交，5 个工作日内到账
- 所有发票需开具公司抬头（税号 91110108XXXXXXXXXX）

## 第八章 信息安全
- 严禁将公司代码、数据、文档上传至公网（包括个人云盘、公开 Git 仓库、公开 AI 工具）
- 工作电脑必须启用 BitLocker/FileVault 全盘加密
- 密码需≥12 位，包含大小写字母+数字+符号，每 90 天更换
- 离开工位必须锁屏（Win+L / Cmd+Ctrl+Q）
- 对外邮件发送敏感数据需加密并经部门负责人审批
- 发现安全漏洞或可疑邮件，立即报告 security@corp.cn

## 第九章 沟通与协作
- 即时通讯：企业微信（工作时间 1 小时内回复）
- 邮件：对外、正式通知、留痕场景使用，内部沟通尽量不发邮件
- 文档协作：飞书文档（内部知识库、会议纪要）
- 会议：30 分钟为单位，会议前发议程，会议后 24 小时内发纪要
- 每周一 10:00 全员周会，各中心同步重点进展

## 第十章 离职流程
1. 试用期内提前 3 天、正式员工提前 30 天提交书面离职申请
2. 离职面谈由 HR 和直属上级共同进行
3. 最后工作日需归还：工作电脑、门禁卡、工牌、公司信用卡、借阅资料
4. 撤销所有系统账号权限、企业微信、VPN、代码仓库
5. 签署保密协议、竞业限制协议（如适用）
6. 工资结算至最后工作日，年终奖按在职月份折算
"""
    it_policy = """# IT 安全与设备使用规范

## 1. 账号安全
- 公司 SSO 账号为个人唯一凭证，禁止出借他人
- 密码每 90 天强制更换，不得与外部网站密码相同
- 必须启用多因素认证（MFA），建议使用企业微信扫码或 Authenticator
- 发现账号异常登录立即联系 IT 支持（it@corp.cn，内部电话 8001）
- 离职员工账号当日 24:00 前停用，保留 30 天数据导出期后销毁

## 2. 设备管理
- 公司统一配备 MacBook Pro / ThinkPad，3 年更新周期
- 个人设备禁止接入公司内网和生产环境
- 工作设备必须：启用全盘加密、安装 EDR 终端防护、系统自动更新
- 设备丢失/被盗立即上报，IT 将远程擦除数据
- 禁止在工作设备上安装未授权软件（尤其是破解软件、盗版工具）

## 3. 数据分级
- L1 公开：对外宣传资料、官网内容
- L2 内部：制度文档、会议纪要、一般业务数据
- L3 机密：客户数据、财务数据、源代码、算法模型
- L4 绝密：核心算法、未发布产品规划、并购信息
- L3/L4 数据禁止外发、禁止拷贝到 U 盘、禁止在非公司设备上查看

## 4. 网络安全
- 公司内网通过 VPN 访问，VPN 开启 MFA
- 公共 Wi-Fi 必须先连 VPN 再访问任何公司系统
- 禁止使用公司邮箱注册非工作相关网站
- 警惕钓鱼邮件：检查发件人域名，不要点击可疑链接/附件
- 生产环境操作必须通过堡垒机，禁止直接 SSH 到服务器

## 5. AI 工具使用规范
- 使用 ChatGPT/Claude 等外部 AI 工具禁止粘贴：源代码、客户数据、未公开财务数据、员工个人信息
- 推荐使用公司内部部署的 Agent 平台处理含敏感信息的任务
- AI 生成的代码和文档必须经过人工审查才能提交/发布
- 禁止将客户提供的私有数据投喂到外部 AI 模型

## 6. 备份与数据恢复
- 重要文档必须保存在公司 OneDrive / 飞书云文档，本地仅作临时编辑
- 代码必须提交到公司 Git 仓库，禁止只存在本地
- 数据库每日自动备份，保留 30 天；关键业务数据库保留 90 天
- 每年进行一次灾备演练

## 7. 违规处理
- 一级违规（账号外借、私装软件）：警告 + 书面检讨
- 二级违规（拷贝 L3 数据到个人设备、未锁屏泄密风险）：记过 + 扣绩效
- 三级违规（外传 L4 数据、恶意破坏系统）：立即解除劳动合同 + 追究法律责任
"""
    hr_policy = """# HR 政策与流程手册

## 1. 招聘流程
### 1.1 需求提出
- 用人部门填写《人员增补申请单》，说明岗位、JD、预算、到岗时间
- 部门负责人 → 分管总监 → HR → CEO（>P7 或年度 HC 超编）审批

### 1.2 面试流程
| 岗位级别 | 面试轮次 | 面试官 |
|---------|---------|--------|
| P1-P3（初级） | 3 轮 | 直属主管 + 部门负责人 + HR |
| P4-P5（中级） | 4 轮 | 直属主管 + 部门负责人 + 跨部门同事 + HR |
| P6-P7（高级/专家） | 5 轮 | 主管 + 部门总监 + 跨部门总监 + CTO/COO + HR |
| P8+（管理/首席） | 6 轮 | 以上 + CEO |

### 1.3 Offer 发放
- HR 根据面试评分和薪资带宽起草 offer
- 薪资带宽外 offer 需 CEO 审批
- 背景调查：P5+ 强制，包含学历、前 2 份工作、竞业限制

## 2. 入职流程
### Day 0（入职前一周）
- IT 准备工作电脑、账号、门禁
- 行政安排工位、文具
- Mentor 收到新人介绍邮件

### Day 1
- HR：合同签署、制度宣讲、信息采集
- IT：设备发放、账号开通、VPN/邮箱配置
- Mentor：团队介绍、午餐、环境搭建
- 下午：新人入职培训（公司介绍 + 安全培训）

### Day 2-5
- 完成 onboarding checklist（Git 权限、知识库阅读、工具安装）
- 1on1 与直属主管设定 30/60/90 天目标
- 参加第一次全员周会自我介绍

### 试用期
- 3-6 个月，P5+ 统一 6 个月
- 试用期工资 100%
- 试用期结束前两周提交转正申请，进行转正答辩

## 3. 晋升机制
- 晋升窗口：每年 4 月、10 月两次
- 流程：自评 → 主管提名 → 晋升委员会评审 → 答辩 → 结果公示
- 晋升需满足：在当前级别满 1 年、近 2 个季度绩效≥A、通过下一级别能力评估
- 跨级晋升（跳级）需 CEO 特批，需有突出贡献

## 4. 职级体系
技术线（T 序列）：
- T1-T3 初级（0-2 年）
- T4-T5 中级（2-5 年）
- T6-T7 高级/专家（5-10 年）
- T8-T9 资深专家/首席（10+ 年）
- T10 Fellow

管理线（M 序列）：
- M1 主管（5-10 人团队）
- M2 总监（30-50 人部门）
- M3 VP / C 级（100+ 人中心）

## 5. 内部转岗
- 在当前岗位满 1 年可申请内部转岗
- 需原部门和新部门双方负责人同意
- HR 协调转岗流程，含 1 个月交接期
- 转岗后 3 个月试用期，通过后正式转入新部门

## 6. 离职类型
1. 主动离职：员工提出，按法定提前通知
2. 协商解除：双方协商一致（通常 N+1 补偿）
3. 过失性辞退：严重违反制度（无补偿）
4. 非过失性辞退：岗位撤销/绩效不达标（N+1 补偿）
5. 合同到期：公司或员工不续签（N 补偿）

补偿金 N = 在职年限（满半年不满一年按 1 年算）× 过去 12 个月平均工资。
"""

    docs = [
        ('employee-handbook.md', '员工手册', handbook, '员工手册'),
        ('it-security.md',      'IT 安全制度', it_policy, 'IT 安全制度'),
        ('hr-policy.md',        'HR 政策手册', hr_policy, 'HR 政策'),
    ]
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    for fname, title, content, kb_name in docs:
        fpath = os.path.join(upload_dir, f"seed_{uuid.uuid4().hex}_{fname}")
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        doc = Document(
            kb_id=kbs[kb_name].id, name=fname, display_name=title,
            file_path=fpath, file_size=len(content.encode('utf-8')),
            content_type='text/markdown', status='ready', chunk_count=0,
        )
        db.add(doc); db.flush()
        # 使用 split_text 切分 + 组装 chunk dicts
        try:
            text_chunks = rag_service.split_text(content, 'sentence', 400, 50, '')
            chunk_dicts = [{"content": t, "meta": {"type": "text", "page": 0}} for t in text_chunks]
            rag_service.index_chunks(db, doc, chunk_dicts)
            print(f"    {title}: {len(text_chunks)} chunks")
        except Exception as e:
            print(f"    警告：{title} 向量化失败 ({e})")
    db.commit()
    print(f"  创建 {len(kbs)} 个知识库, {len(docs)} 篇企业文档")

    # ========== Agent ==========
    print("[4/6] 创建 Agent...")
    agents_def = [
        # (name, display, desc, arch, tools, kb_ids)
        ('hr-assistant',    '🤝 HR 智能助手',      '回答员工关于考勤、福利、报销、绩效、离职等 HR 政策问题，依据 HR 政策手册',         'react',
         ['rag_search', 'calculator'], ['HR 政策']),
        ('it-helpdesk',     '💻 IT 服务台',        '处理账号、设备、网络、VPN、软件安装等 IT 问题，依据 IT 安全制度',                'react',
         ['rag_search', 'http_request'], ['IT 安全制度']),
        ('code-reviewer',   '👨‍💻 代码审查助手',    '对代码进行规范检查、安全扫描、性能建议，可联网搜索最佳实践',                      'react',
         ['web_search', 'http_request'], []),
        ('doc-writer',      '📝 文档写作助手',     '帮助撰写产品文档、技术文档、会议纪要、对外沟通邮件，统一公司风格',              'single',
         ['rag_search'], []),
        ('data-analyst',    '📊 数据分析师',       '回答业务数据问题、生成 SQL、制作数据看板、解读报表异常，会做数学计算',          'react',
         ['calculator', 'web_search'], []),
        ('onboarding-buddy','🎓 入职导师',         '为新员工解答公司制度、工具使用、流程问题，陪跑入职前 90 天',                   'react',
         ['rag_search'], ['员工手册', 'IT 安全制度', 'HR 政策']),
        ('contract-checker','📑 合同审查助手',     '审查商务合同的风险点：付款条款、违约责任、保密条款、知识产权归属，可联网参考',  'react',
         ['web_search'], []),
        ('meeting-minutes', '🗒️ 会议纪要生成器',   '根据要点自动生成结构化纪要：议题、决议、Action Item、责任人、DDL',             'single',
         [], []),
        ('web-researcher',  '🔎 联网研究员',       '搜索互联网最新资讯、竞品动态、技术文档，综合多个来源给出结构化研究报告',        'react',
         ['web_search', 'http_request', 'calculator'], []),
        ('translator',      '🌐 翻译专家',         '中英文互译，保留专业术语和格式，支持技术文档、商务邮件、合同条款翻译',          'single',
         [], []),
        ('email-writer',    '✉️ 邮件助手',         '根据要点起草商务邮件、回复邮件、润色语气，支持中英文',                         'single',
         [], []),
    ]
    agents = {}
    for name, display, desc, arch, tools_list, kb_names in agents_def:
        kb_ids = [kbs[n].id for n in kb_names if n in kbs]
        a = Agent(name=name, display_name=display, description=desc, architecture=arch,
                  system_prompt=f"你是智启科技的{display}。请专业、准确地回答员工问题，回答要简洁有条理。"
                                + (f" 你可以查阅企业知识库获取官方答案。" if kb_ids else "")
                                + (" 你可以联网搜索最新信息。" if 'web_search' in tools_list else ""),
                  tools=tools_list, rag_kb_ids=kb_ids,
                  enabled=True, created_by=1)
        db.add(a); db.flush()
        agents[name] = a
    db.commit()
    print(f"  创建 {len(agents)} 个 Agent")

    # ========== Workflow ==========
    print("[5/6] 创建工作流...")
    wfs_def = [
        ('leave-request', '🏖️ 请假审批流',     '员工提交请假 → 主管审批 → HR 备案 → 结果通知',      '人事'),
        ('expense-reimburse', '💰 报销审批流', '员工提交 → 直属主管 → 财务审核 → 出纳打款',         '财务'),
        ('onboarding-flow', '🎓 入职流程',     'HR 录入 → IT 开通账号 → Mentor 分配 → 欢迎邮件',   '人事'),
        ('code-review-flow', '🔍 代码审查',     '提交 MR → 自动静态检查 → AI 审查 → 人工 Review',   '研发'),
        ('doc-qa-pipeline', '📚 文档问答链',    '文档上传 → 分块 → 向量化 → 检索 → 生成答案',       '研发'),
    ]
    wfs = {}
    for name, display, desc, cat in wfs_def:
        w = Workflow(name=name, display_name=display, description=desc, category=cat,
                    definition='{"nodes":[],"edges":[]}', created_by=1, enabled=True)
        db.add(w); db.flush()
        wfs[name] = w
    db.commit()
    print(f"  创建 {len(wfs)} 个工作流")

    # ========== 群组 ==========
    print("[6/6] 创建群组并共享资源...")
    def make_group(name, desc, owner_acc, member_accs, shared_agents=None, shared_kbs=None, shared_wfs=None, shared_skills=None):
        g = Group(name=name, description=desc, owner_id=account_map[owner_acc])
        db.add(g); db.flush()
        # owner 作为 owner 成员
        db.add(GroupMember(group_id=g.id, user_id=account_map[owner_acc], role='owner'))
        for acc in member_accs:
            if acc == owner_acc: continue  # 避免重复
            db.add(GroupMember(group_id=g.id, user_id=account_map[acc], role='member'))
        for aname in (shared_agents or []):
            db.add(GroupAgent(group_id=g.id, agent_id=agents[aname].id, shared_by=account_map[owner_acc]))
        for kslug in (shared_kbs or []):
            db.add(GroupKB(group_id=g.id, kb_id=kbs[kslug].id, shared_by=account_map[owner_acc]))
        for wname in (shared_wfs or []):
            db.add(GroupWorkflow(group_id=g.id, workflow_id=wfs[wname].id, shared_by=account_map[owner_acc]))
        # 所有群共享 builtin skills
        if shared_skills is None:
            for sk in db.query(Skill).filter(Skill.is_builtin == True).all():
                db.add(GroupSkill(group_id=g.id, skill_id=sk.id, shared_by=account_map[owner_acc]))
        else:
            for sn in shared_skills:
                sk = db.query(Skill).filter(Skill.name == sn).first()
                if sk: db.add(GroupSkill(group_id=g.id, skill_id=sk.id, shared_by=account_map[owner_acc]))
        return g

    # 全员群：所有 KB + 所有 Agent + 所有 Workflow + 一个公告
    all_emps = [e[0] for e in employees]
    g_all = make_group('🏢 智启科技全员群', '公司级全员公告与协作空间', 'admin', all_emps,
                       shared_agents=list(agents.keys()),
                       shared_kbs=['员工手册', 'IT 安全制度', 'HR 政策'],
                       shared_wfs=list(wfs.keys()))
    db.add(GroupNotice(group_id=g_all.id, author_id=1, title='欢迎来到智启科技 Agent 平台',
                       content='各位同事：\n\n公司的 AI Agent 平台已正式上线，欢迎大家体验使用。\n\n平台当前已提供 HR 助手、IT 服务台、代码审查等多个智能助手，以及请假、报销、入职等常用流程工作流，可在本群直接调用。\n\n使用过程中如遇问题请联系技术中心陈骁宇。\n\n陈启明\nCEO', pinned=True))

    # 研发中心群
    tech_emps = ['chen.xiaoyu','liu.meng','zhao.jian','sun.ting','wu.hao','zhou.lin','huang.tao',
                 'xu.ran','feng.yu','he.shuai','deng.xin','cao.yue','yan.qi','bai.jun','lin.yun',
                 'guo.jing','pan.yang','tang.chao','ye.fan','jiang.ting']
    g_tech = make_group('💻 技术中心', '研发/产品/AI 实验室协作群', 'li.wei', tech_emps,
                        shared_agents=['code-reviewer','doc-writer','data-analyst','meeting-minutes'],
                        shared_kbs=['IT 安全制度'],
                        shared_wfs=['code-review-flow','doc-qa-pipeline'])
    db.add(GroupNotice(group_id=g_tech.id, author_id=account_map['li.wei'],
                       title='【重要】本周代码冻结通知',
                       content='各位研发同事：\n\n本周五 18:00 开始 v2.3 版本代码冻结，冻结期间除 hotfix 外不接受 MR。\n\n下周一发布完成后解除冻结。\n\n李伟\nCTO', pinned=True))
    db.add(GroupNotice(group_id=g_tech.id, author_id=account_map['chen.xiaoyu'],
                       title='研发规范更新',
                       content='代码审查流程更新：所有合并到 main 的 MR 需要至少 1 个 Approval + CI 通过 + AI 审查无 Blocker 级别问题。'))

    # HR 群
    hr_emps = ['hao.yan','ma.li','fan.li','lu.yao']
    g_hr = make_group('🤝 人事部', 'HR 团队内部讨论', 'hao.yan', hr_emps,
                      shared_agents=['hr-assistant','contract-checker','doc-writer'],
                      shared_kbs=['HR 政策'],
                      shared_wfs=['leave-request','onboarding-flow'])
    db.add(GroupNotice(group_id=g_hr.id, author_id=account_map['hao.yan'],
                       title='2026 秋季招聘启动',
                       content='各位：\n\n秋招已启动，重点招聘 T4-T5 后端/前端/算法工程师，JD 已更新到知识库。\n\n请在 9 月前完成简历筛选和初面安排。', pinned=True))

    # 销售/市场群
    sales_emps = ['ren.jie','kong.qin','cui.wei','bai.xiao','xue.mei']
    g_sales = make_group('📈 销售与市场', '销售、市场、BD 协作', 'cui.wei', sales_emps,
                         shared_agents=['doc-writer','data-analyst','contract-checker'],
                         shared_kbs=[],
                         shared_wfs=[])
    db.add(GroupNotice(group_id=g_sales.id, author_id=account_map['cui.wei'],
                       title='Q3 销售目标',
                       content='各位伙伴：\nQ3 销售目标 2000 万 ARR，目前完成 68%，8 月加把劲！\n重点客户：华盛集团、东方证券、智联云。', pinned=True))

    db.commit()
    print(f"  创建 4 个群组 + 公告 + 共享资源")

    # ========== 统计 ==========
    print("\n[Done] 数据填充完成，当前状态：")
    for tbl_label, tbl in [('用户', 'users'), ('Agent', 'agents'), ('工作流', 'workflows'),
                           ('知识库', 'knowledge_bases'), ('文档', 'documents'),
                           ('群组', 'work_groups'), ('群公告', 'group_notices'),
                           ('群共享Agent', 'group_agents'), ('群共享KB', 'group_kbs'),
                           ('群共享Workflow', 'group_workflows'), ('群共享Skill', 'group_skills')]:
        c = db.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
        print(f"  {tbl_label}: {c}")

finally:
    db.close()
