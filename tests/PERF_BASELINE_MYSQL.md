# 生产依赖性能基线复测报告（MySQL + Milvus + 真实 LLM）

- **日期**：2026-07-24
- **目标**：在「真实生产依赖」（MySQL 引擎 + Milvus Lite + 真实 ARK LLM）下复测性能基线，与测试环境（SQLite + mock LLM）基线对比。
- **复测脚本**：`scripts/perf_baseline_mysql.py`（独立脚本，不走 conftest 的 SQLite 覆盖）
- **隔离策略**：使用独立库 `agentflow_perf`（同一 MySQL 实例 / InnoDB 引擎），不污染真实 `agentflow` 库。

## 一、测试环境

| 项 | 值 |
|----|----|
| 数据库 | MySQL 8 (InnoDB)，`127.0.0.1:3306/agentflow_perf` |
| 向量库 | Milvus Lite（单文件 `data/milvus_perf.db`） |
| LLM | ARK 火山方舟（OpenAI 兼容），真实 key |
| 默认对话模型 | `doubao-seed-evolving`（思考模型） |
| 快速模型 | `deepseek-v4-flash` |
| 应用 | FastAPI + SQLAlchemy 2.0，`pool_size=5, max_overflow=10, pool_recycle=3600` |
| 数据量 | 空表（仅 seed 超级管理员 `admin`） |

> 注：本地 MySQL 与应用同机，网络往返 ≈ 0；生产若 DB 为远程实例，REST 延迟会再高几~十几 ms（仍远低于 500ms 基线）。

## 二、REST 列表端点延迟（MySQL 后端，单位 ms）

每个端点 n=21（1 次 warmup + 21 次计时），与 QA 报告中的 SQLite 基线并排对比：

| 接口 | MySQL min | MySQL median | MySQL p95 | MySQL max | SQLite 基线 p95 | 阈值 | 结论 |
|------|-----------|--------------|-----------|-----------|-----------------|------|------|
| GET /api/v1/workflows | 17.85 | 19.46 | **21.67** | 24.35 | ~20 | <500 | ✅ |
| GET /api/v1/agents | 16.58 | 18.29 | **18.57** | 19.72 | ~22 | <500 | ✅ |
| GET /api/v1/rag/kbs | 18.88 | 19.52 | **21.17** | 26.31 | ~21 | <500 | ✅ |
| GET /api/v1/groups | 18.33 | 18.98 | **19.68** | 21.38 | ~23 | <500 | ✅ |
| GET /api/v1/skills | 13.09 | 16.25 | **20.60** | 21.96 | ~23 | <500 | ✅ |
| GET /api/v1/system/apm | 13.10 | 13.75 | **14.84** | 15.31 | — | <500 | ✅ (已鉴权) |
| GET /health | 1.43 | 1.66 | **1.90** | 2.29 | — | — | ✅ |
| POST /api/v1/auth/login | — | — | **≈255** | — | ~290 | <500 | ✅ (bcrypt 主导) |

**结论**：本地小表下 MySQL 与 SQLite 基线基本一致（p95 18–22ms vs 20–23ms）。DB 引擎差异被框架/序列化开销掩盖——REST 延迟由 FastAPI + 中间件（Trace/Audit/RateLimit）+ 连接池 checkout 主导，而非 SQL 执行。所有端点远低于 500ms 基线。

> login 的 p95≈255ms 由 **bcrypt 密码校验**主导（与 SQLite 基线 ~290ms 吻合）。注意：脚本内因登录限流（见第五节）多次调用后返回 429 被快速短路（~13ms），此值为「每次清空限流器后实测」的真实延迟（已独立验证 11 次全 200 / ~250ms）。

## 三、真实 LLM 调用延迟（ARK，单位 ms）

直接调用 `get_chat_model(provider="ark").invoke(...)`，n=4（含 1 次 warmup），无任何 mock：

| 模型 | min | median | p95 | max | 样本回复 |
|------|-----|--------|-----|-----|----------|
| `doubao-seed-evolving`（生产默认，思考模型） | 8030 | **8895** | **13630** | 13630 | "我是由字节跳动开发训练的人工智能豆包…" |
| `deepseek-v4-flash`（快速档） | 4694 | **4833** | **4854** | 4854 | "我是DeepSeek，由深度求索公司创造的免费AI助手…" |

**结论**：真实 LLM 延迟在 **秒级**（4.7–13.6s），是任何 LLM 路径的**主导成本**，比 REST 框架开销（<25ms）高出 2~3 个数量级。这是平台用户体验的瓶颈，而非后端框架。

- `doubao-seed-evolving` 为思考模型，reasoning 深度波动大（8–13.6s）。
- `deepseek-v4-flash` 稳定 ~4.8s，适合延迟敏感场景。

## 四、端到端 AI 助手延迟（真实 LLM 经 HTTP）

`POST /api/v1/meta/chat`（自然语言操控平台），n=3（含 1 次 warmup），真实 LLM：

| 接口 | min | median | p95 | max | 状态 |
|------|-----|--------|-----|-----|------|
| POST /api/v1/meta/chat | 1489 | **1898** | **2483** | 2483 | 3/3 返回 200 + 真实回复 |

> 端到端中位 1.9s 低于原始 LLM doubao 的中位 8.9s，是因为测试消息要求「一句话直接回复、不调用工具」，模型只做浅层推理。原始 LLM 测试问「介绍你自己」触发更深推理。两者一致证明：**LLM 路径延迟由模型推理时间主导**。

## 五、发现项

### 发现 1（P2，部署阻塞）✅ 已修复：alembic init_schema 迁移缺失核心表 → 生产 MySQL 无法独立建库
- **根因**：`alembic upgrade head` 在 MySQL 上报 `(1824) Failed to open the referenced table 'agents'`——`init_schema` 迁移（cd0f621d3632）中 `group_messages` 引用了 `agents`/`work_groups`/`users`，但这三张核心表（及 `documents`/`knowledge_bases`/`chunks` 等 9+ 张基础表）**从未在任何迁移里创建过**。它们是项目初期 `Base.metadata.create_all()` 建的，alembic 仅作为增量 diff 没包含。
- **✅ 修复方案**：`app/db/session.py` 的 `init_db()` 改为：空库（任意 DB 类型）统一走 `Base.metadata.create_all() + alembic stamp head`。SQLAlchemy 按 FK 依赖拓扑排序建表，MySQL/PG/SQLite 均安全。验证：干净 MySQL 库 → 建 31 张表 → `alembic upgrade head` = 0（no-op）。
- **影响面**：`scripts/perf_baseline_mysql.py` 无需修改（已用相同方式建库）。后续增量迁移正常接力。

### 发现 2（P3，配置提示）：登录限流偏严
- `LOGIN_RATE_LIMIT_MAX=5`、`LOGIN_RATE_LIMIT_WINDOW_SEC=600`：同 (账号, IP) **10 分钟内仅 5 次登录**即返回 429。
- 作为防爆破控制合理，但偏严；压测/多端登录易误伤。基线测量中多次调用即触发 429（被快速短路为 ~13ms，已剔除并改用清空限流器后的真实值）。
- **建议**：评估是否放宽到 10–20 次/10min，或为可信内网 IP 加白名单。

### 发现 3（提示，非缺陷）：默认对话模型延迟高
- `ARK_CHAT_MODEL=doubao-seed-evolving` 为思考模型，对话首响 8–13s。若追求响应速度，建议将默认模型切换为 `deepseek-v4-flash`（~4.8s）或在 UI 标注「思考中」避免用户以为卡死。

## 六、结论与建议

1. **REST 性能达标**：MySQL 后端下所有列表/查询端点 p95 ≤ 22ms（<500ms 基线），与 SQLite 测试基线一致；login 由 bcrypt 主导 ~255ms，符合预期。生产就绪。
2. **LLM 是体验瓶颈**：真实 LLM 调用 4.7–13.6s，远超后端开销。**性能优化重点应放在 LLM 侧**（模型选型、流式首响、缓存、并发），而非框架。
3. **✅ 发现 1 已修复**：`init_db()` 空库自动 `create_all + stamp head`，生产 MySQL 部署不再受阻。
4. **本基线使用真实 LLM + 真实 MySQL/Milvus**，相较 QA 阶段（SQLite + mock LLM）更贴近生产，可作为后续回归基线的新基准。

> 数据原始记录见 `tests/PERF_BASELINE_MYSQL.json`。
