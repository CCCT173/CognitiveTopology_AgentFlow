# 🔗 CognitiveTopology - 认知拓扑工作流平台

> 一个现代化的多Agent协作平台，支持可视化工作流编排、智能Agent框架、RAG知识库和技能系统，助力企业构建智能化业务流程。

![GitHub](https://img.shields.io/github/license/CCCT173/CognitiveTopology_AgentFlow)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![React](https://img.shields.io/badge/React-18+-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-blue.svg)

---

**语言版本** | [English](README_EN.md) | [中文](README.md)

---

## 🎯 项目简介

**CognitiveTopology** 是一个基于 FastAPI + React 构建的企业级多Agent协作平台，致力于帮助开发者快速构建、部署和管理智能工作流。平台融合了先进的AI技术，支持多种Agent架构模式和可视化工作流编排，为企业提供智能化的业务流程解决方案。

本项目开发的agent具备操控系统核心功能的完整能力，包括但不限于创建子agent实例、设计与执行工作流、管理数据库（含数据的增删改查操作）、管理用户群组及权限分配等关键功能模块。该agent为有经验的专业用户提供了更为高效、直接的系统操作方式，显著提升工作效率。同时，系统内置了多等级安全沙箱机制，通过严格的权限隔离与操作审计，确保核心数据与系统资源的安全性。

### ✨ 核心价值

- **🎨 可视化工作流**：拖拽式节点编辑器，轻松构建复杂业务流程
- **🤖 多Agent架构**：支持ReAct、单Agent、工作流封装等多种模式
- **📚 RAG知识库**：高效的文档检索和向量存储能力
- **🛠️ 技能系统**：可扩展的技能创建和共享机制
- **🔒 企业级安全**：完整的权限管理和审计日志
- **🧱 安全沙箱**：多层隔离架构确保执行安全

---

## 🚀 核心功能

### 1. Agent安全沙箱体系

平台提供多层安全隔离机制，根据不同的执行风险等级采用差异化的隔离策略，确保代码执行的安全性和可靠性。

**沙箱等级定义**：

| 沙箱等级 | 隔离能力 | 适用场景 | 执行限制 |
|---------|---------|---------|---------|
| **L1 - 基础沙箱** | AST静态检查 + 子进程隔离 | 简单脚本执行、数据处理、Skill执行 | 文件系统只读、网络受限、白名单标准库 |
| **L3 - 高级沙箱** | 专用venv + 工作目录隔离 | 复杂代码执行、数据科学计算、第三方依赖 | 完整网络访问、临时文件系统、资源限制 |

**安全特性**：

- **进程隔离**：每个执行任务运行在独立进程空间，进程结束后自动清理资源
- **超时保护**：L1默认超时5秒，L3默认超时60秒，超时后自动终止进程
- **资源限制**：CPU、内存、进程数等资源配额控制（L3）
- **路径安全**：L3 Workspace API包含路径越界检查，禁止访问工作目录以外的文件
- **危险操作拦截**：禁止系统命令执行和敏感文件访问
- **执行审计**：完整的执行日志和操作记录

**安全边界**：

| 边界类型 | L1沙箱 | L3沙箱 |
|---------|--------|--------|
| 文件系统 | 禁止访问 | 仅限工作目录 |
| 网络访问 | 禁止 | 允许HTTP/HTTPS |
| 系统命令 | 禁止 | 禁止直接执行 |
| 标准库 | 白名单（24个安全模块） | 完整访问 |
| 第三方包 | 禁止 | 预装包 + 动态安装 |

**Workspace API**（L3）：

- `ws.read(path)`：读取文件内容
- `ws.write(path, content)`：写入文件内容
- `ws.list_dir(path)`：列出目录内容
- `ws.exists(path)`：检查文件是否存在
- `ws.fetch(url)`：发送HTTP请求
- `ws.install_pkg(name)`：安装pip包

---

### 2. 认知拓扑环境全面控制

#### 2.1 环境配置管理

**配置项分类**：

| 配置类别 | 配置项 | 说明 |
|---------|-------|------|
| **应用配置** | APP_NAME, APP_VERSION, APP_ENV, DEBUG | 基础应用设置 |
| **网络配置** | HOST, PORT | 服务绑定地址 |
| **认证配置** | JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES | JWT令牌配置 |
| **数据库配置** | DATABASE_URL | MySQL连接字符串 |
| **LLM配置** | LLM_PROVIDER, API_KEY, BASE_URL, MODEL | 大模型服务配置 |
| **向量库配置** | VECTOR_STORE, MILVUS_HOST, MILVUS_PORT | 向量数据库配置 |

**配置文件结构**（`.env`）：
```env
# 应用配置
APP_NAME=AgentRAG Platform
APP_VERSION=0.2.0
APP_ENV=dev
DEBUG=true

# 数据库配置
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/db

# LLM配置
LLM_PROVIDER=ark
ARK_API_KEY=your_api_key
```

#### 2.2 配置版本控制

**功能特性**：
- 支持配置方案的保存、加载和切换
- 每个配置方案包含完整的参数集合
- 支持配置方案的导入/导出（JSON格式）
- 配置变更记录历史，支持回滚

**API接口**：
```
GET    /api/v1/meta/system-config    # 获取当前配置
PATCH  /api/v1/meta/system-config    # 更新配置
POST   /api/v1/meta/system-config/save    # 保存配置方案
GET    /api/v1/meta/system-config/list    # 获取配置方案列表
POST   /api/v1/meta/system-config/load    # 加载配置方案
```

#### 2.3 热更新机制

**实现原理**：
- 配置修改通过API实时更新到内存
- 使用`@lru_cache`缓存配置，更新时清除缓存
- 无需重启服务，配置立即生效

**代码示例**：
```python
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "CognitiveTopology"
    # ...其他配置项

@lru_cache
def get_settings() -> Settings:
    return Settings()

# 更新配置时调用
def reload_settings():
    get_settings.cache_clear()
```

#### 2.4 系统监控

**监控指标**：
- 系统状态：CPU、内存、磁盘使用
- API指标：请求数、响应时间、错误率
- 工作流指标：执行次数、成功率、耗时分布
- 数据库指标：连接数、查询性能

**监控接口**：
```
GET /api/v1/meta/health    # 健康检查
GET /api/v1/meta/stats     # 系统统计
GET /api/v1/meta/metrics   # 性能指标
```

---

### 3. 子Agent创建与管理

#### 3.1 子Agent创建

**创建流程**：
1. 选择父Agent模板
2. 配置子Agent参数（名称、描述、系统提示词）
3. 设置继承权限
4. 创建子Agent实例

**API接口**：
```
POST   /api/v1/agents/{parent_id}/sub-agents    # 创建子Agent
GET    /api/v1/agents/{parent_id}/sub-agents    # 获取子Agent列表
DELETE /api/v1/agents/{parent_id}/sub-agents/{sub_id}    # 删除子Agent
```

#### 3.2 层级关系管理

**层级结构**：
```
父Agent
├── 子Agent 1
│   └── 孙子Agent 1.1
├── 子Agent 2
└── 子Agent 3
```

**权限继承**：
- 子Agent继承父Agent的权限配置
- 支持权限覆盖：子Agent可自定义部分权限
- 权限变更支持层级同步

#### 3.3 批量管理

**批量操作**：
- 批量创建子Agent
- 批量更新配置
- 批量删除（需二次确认）

---

### 4. 工作流自动化工具

#### 4.1 定时触发

**CRON表达式支持**：
```
# 每天早上8点执行
0 8 * * *

# 每周一至周五下午6点执行
0 18 * * 1-5

# 每小时执行一次
0 * * * *
```

**API接口**：
```
POST /api/v1/workflows/{id}/schedule    # 设置定时任务
GET  /api/v1/workflows/{id}/schedule    # 获取定时任务
DELETE /api/v1/workflows/{id}/schedule    # 删除定时任务
```

#### 4.2 事件触发

**支持的事件类型**：
- 工作流完成事件
- 消息到达事件
- 文件上传事件
- 定时触发事件

**事件配置**：
```json
{
  "trigger_type": "event",
  "event_name": "message_received",
  "conditions": {
    "channel": "webhook",
    "min_length": 10
  }
}
```

#### 4.3 Webhook集成

**Webhook配置**：
```json
{
  "url": "https://your-server.com/webhook",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer token"
  },
  "retry_policy": {
    "max_retries": 3,
    "retry_delay": 5
  }
}
```

#### 4.4 执行追踪

**执行日志结构**：
```json
{
  "workflow_id": "wf_123",
  "run_id": "run_456",
  "status": "completed",
  "start_time": "2026-07-25T10:00:00Z",
  "end_time": "2026-07-25T10:00:30Z",
  "duration_ms": 30000,
  "nodes": [
    {"node_id": "n1", "status": "success", "duration_ms": 15000},
    {"node_id": "n2", "status": "success", "duration_ms": 10000},
    {"node_id": "n3", "status": "success", "duration_ms": 5000}
  ],
  "error": null
}
```

---

### 5. 团队协作与管理系统

#### 5.1 用户管理

**用户模型**：
```python
class User(BaseModel):
    id: str
    email: str
    username: str
    role: str  # admin, manager, user
    status: str  # active, inactive
    created_at: datetime
    updated_at: datetime
```

**API接口**：
```
POST   /api/v1/users    # 创建用户
GET    /api/v1/users    # 获取用户列表
GET    /api/v1/users/{id}    # 获取用户详情
PATCH  /api/v1/users/{id}    # 更新用户
DELETE /api/v1/users/{id}    # 删除用户
```

#### 5.2 权限控制

**权限模型**：
```python
class Permission(BaseModel):
    resource_type: str  # workflow, agent, skill, kb
    resource_id: str
    user_id: str
    actions: list[str]  # ["read", "write", "execute", "delete"]
```

**权限矩阵**：

| 角色 | 工作流 | Agent | Skill | 知识库 | 用户管理 |
|------|--------|-------|-------|--------|---------|
| admin | 全部 | 全部 | 全部 | 全部 | 全部 |
| manager | 全部 | 全部 | 全部 | 全部 | 查看 |
| user | 读写 | 读写 | 读写 | 读写 | 无 |

#### 5.3 协作功能

**资源共享**：
- 工作流共享：支持共享给特定用户或群组
- Skill共享：支持公开/私有/群组共享
- 知识库共享：支持多用户协同编辑

**版本管理**：
- 资源版本历史记录
- 支持版本对比和回滚
- 乐观锁机制防止并发冲突

---

### 6. 可视化工作流编辑器

#### 6.1 节点类型

| 节点类型 | 功能 | 配置参数 |
|---------|------|---------|
| **Start** | 流程起点 | 无 |
| **End** | 流程终点 | 输出字段、输出格式 |
| **LLM** | 大模型调用 | Provider、Model、Prompt、Temperature、TopP、MaxTokens |
| **Tool** | 工具调用 | 工具选择、参数配置 |
| **Skill** | 技能执行 | Skill选择、参数配置 |
| **Condition** | 条件判断 | 条件表达式、分支配置 |
| **Agent** | Agent调用 | Agent选择、消息模板 |
| **Code** | 代码执行 | 编程语言、代码内容、沙箱等级 |
| **Loop** | 循环处理 | 遍历变量、最大迭代次数 |
| **Parallel** | 并行执行 | 分支数、超时时间 |
| **Transform** | 数据转换 | 转换格式、映射规则 |
| **Delay** | 延迟等待 | 延迟时长、时间单位 |

#### 6.2 连线配置

**连线类型**：
- 普通连线：无条件跳转
- 条件连线：根据条件值跳转
- 默认连线：无匹配时的默认路径

**连线配置示例**：
```json
{
  "id": "edge_1",
  "source": "node_1",
  "target": "node_2",
  "condition": {
    "field": "output.status",
    "operator": "equals",
    "value": "success"
  }
}
```

#### 6.3 自动布局

**布局算法**：
- BFS广度优先遍历
- 从Start节点开始计算层级
- 自动调整节点位置和连线走向

---

### 7. 动态参数配置系统

#### 7.1 参数类型

| 参数类型 | 描述 | 输入控件 |
|---------|------|---------|
| text | 单行文本 | 文本输入框 |
| number | 数字 | 数字输入框 |
| slider | 滑块数值 | 滑块控件 |
| select | 选择项 | 下拉选择框 |
| switch | 布尔值 | 开关控件 |
| textarea | 多行文本 | 文本域 |
| json | JSON对象 | JSON编辑器 |
| code | 代码 | 代码编辑器 |

#### 7.2 参数Schema定义

**LLM节点参数Schema**：
```python
llm_node_schema = {
    "provider": {"type": "select", "options": ["ark", "giteeai", "deepseek"]},
    "model": {"type": "select", "options": ["glm-5.2", "deepseek-chat"]},
    "system_prompt": {"type": "textarea", "fullWidth": True},
    "temperature": {"type": "slider", "min": 0, "max": 1, "step": 0.01},
    "top_p": {"type": "slider", "min": 0, "max": 1, "step": 0.01},
    "max_tokens": {"type": "number", "min": 100, "max": 8192},
    "streaming": {"type": "switch", "default": True},
}
```

#### 7.3 动态渲染

**渲染流程**：
1. 根据节点类型获取参数Schema
2. 根据参数类型选择对应的渲染组件
3. 支持参数分组显示
4. 支持依赖显示（根据其他参数值决定是否显示）

---

### 8. Agent框架

#### 8.1 ReAct模式

**执行循环**：
```
思考(Thought) → 行动(Action) → 观察(Observation) → 思考(Thought) → ...
```

**实现代码**：
```python
class ReActAgent(BaseAgent):
    async def run(self, task: str) -> str:
        while not self.should_stop():
            # 思考
            thought = await self.think(task)
            
            # 行动
            action = await self.select_action(thought)
            
            # 执行
            result = await self.execute_action(action)
            
            # 观察
            observation = self.observe(result)
            
            # 更新任务状态
            task = self.update_task(task, observation)
        
        return self.final_answer()
```

#### 8.2 工作流代理

**封装模式**：
- 将工作流封装为Agent
- 通过API接口调用工作流
- 支持异步执行和结果回调

#### 8.3 MetaRunner

**多Agent协作**：
- 支持多个Agent协同完成复杂任务
- 负责Agent间的任务分配和协调
- 支持任务优先级和依赖关系

---

### 9. 技能系统

#### 9.1 Skill结构

**Skill定义**：
```python
class Skill(BaseModel):
    id: str
    name: str
    description: str
    type: str  # code, api, workflow
    code: str  # 执行代码
    params: list[ParamField]  # 参数定义
    entry: str  # 入口函数名
    version: str
```

#### 9.2 Skill执行

**执行流程**：
1. 解析Skill定义
2. 验证输入参数
3. 在L1沙箱中执行代码
4. 返回执行结果

**API接口**：
```
POST   /api/v1/skills    # 创建Skill
GET    /api/v1/skills    # 获取Skill列表
GET    /api/v1/skills/{id}    # 获取Skill详情
PATCH  /api/v1/skills/{id}    # 更新Skill
DELETE /api/v1/skills/{id}    # 删除Skill
POST   /api/v1/skills/{id}/execute    # 执行Skill
POST   /api/v1/skills/{id}/test    # 测试Skill
```

---

### 10. RAG知识库

#### 10.1 文档处理流程

**处理步骤**：
1. **上传**：支持PDF、DOCX、TXT等格式
2. **分块**：按段落/章节分割文档
3. **嵌入**：使用嵌入模型生成向量
4. **存储**：存入向量数据库（Milvus）

**分块策略**：
```python
# 默认分块配置
CHUNK_SIZE = 500      # 每个块的token数
CHUNK_OVERLAP = 50    # 块之间的重叠token数
```

#### 10.2 向量检索

**检索流程**：
1. 查询文本嵌入
2. 向量相似度搜索（Top-K）
3. 重排序（Reranker）
4. 返回最相关文档

**检索配置**：
```python
# 检索参数
TOP_K = 10            # 返回前10个结果
RE_RANK_TOP_K = 3     # 重排序后返回前3个
SIMILARITY_THRESHOLD = 0.7  # 相似度阈值
```

#### 10.3 API接口

```
POST   /api/v1/rag/kbs    # 创建知识库
GET    /api/v1/rag/kbs    # 获取知识库列表
POST   /api/v1/rag/kbs/{id}/documents    # 上传文档
GET    /api/v1/rag/kbs/{id}/documents    # 获取文档列表
POST   /api/v1/rag/kbs/{id}/search    # 搜索文档
DELETE /api/v1/rag/kbs/{id}    # 删除知识库
```

---

## 🎨 用户体验增强

### 高级用户特性

- ⌨️ **命令面板**：支持快捷键打开命令搜索面板
- ⚡ **快速操作**：常用功能一键访问
- 🎯 **智能提示**：基于上下文的操作建议
- 🔄 **主题切换**：支持白天/夜晚主题
- 🌐 **多语言支持**：中文/英文界面切换

### 高风险操作安全机制

所有高风险操作均需严格的手动确认，确保数据安全和完整性：

| 操作类型 | 安全机制 | 确认方式 |
|---------|---------|---------|
| 🗑️ 删除资源 | 二次确认弹窗 | 手动确认删除 |
| 🔄 版本回滚 | 影响范围预览 | 确认回滚范围 |
| 🔑 权限变更 | 权限变更日志 | 操作审批流程 |
| 📤 导出数据 | 数据范围确认 | 确认导出内容 |
| 🚀 部署操作 | 部署预览 | 确认部署配置 |

---

## 🏗️ 功能架构分析

### 架构设计原则

1. **分层架构**：前端展示层 → API网关层 → 业务逻辑层 → 数据访问层
2. **模块化设计**：每个功能模块独立开发和部署
3. **松耦合**：模块间通过API接口通信，降低依赖
4. **可扩展性**：支持插件化扩展新功能

### 核心模块架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端展示层                             │
│  WorkflowEditor | AgentManager | SkillCenter | Settings    │
├─────────────────────────────────────────────────────────────┤
│                      API网关层                              │
│  Router | Middleware | Authentication | RateLimit          │
├─────────────────────────────────────────────────────────────┤
│                      业务逻辑层                             │
│  AgentService | WorkflowService | SkillService | RagService │
│  AuthService | UserService | GroupService                   │
├─────────────────────────────────────────────────────────────┤
│                      数据访问层                             │
│  SQLAlchemy ORM | MySQL | Milvus Vector DB                 │
├─────────────────────────────────────────────────────────────┤
│                      AI服务层                               │
│  LLM Providers | Embedding | Reranker | Tool Execution     │
├─────────────────────────────────────────────────────────────┤
│                      安全沙箱层                             │
│  L1 Sandbox (AST检查+子进程) | L3 Sandbox (venv+工作目录)   │
└─────────────────────────────────────────────────────────────┘
```

### 竞争优势

- **安全沙箱**：多层隔离架构保障执行安全，AST静态检查+子进程隔离
- **可视化编排**：直观的工作流设计体验，12种节点类型覆盖全场景
- **动态配置**：灵活的参数配置系统，8种参数类型支持复杂场景
- **企业级特性**：完整的权限管理和协作功能，支持团队协作
- **高性能**：异步处理和缓存策略提升响应速度

---

## 🛠️ 技术栈

### 后端技术
| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.100+ | 高性能API框架 |
| SQLAlchemy | 2.0+ | ORM数据库操作 |
| MySQL | 8.0+ | 关系型数据库 |
| Alembic | 1.12+ | 数据库迁移 |
| JWT | - | 身份认证 |
| Fernet | - | 敏感信息加密 |

### 前端技术
| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18+ | UI框架 |
| TypeScript | 5+ | 类型安全 |
| Tailwind CSS | 3+ | 样式框架 |
| Vite | 5+ | 构建工具 |
| Zustand | 4+ | 状态管理 |

### AI服务
| 服务 | 说明 |
|------|------|
| 火山方舟 | LLM和嵌入模型 |
| GiteeAI | 重排序模型 |
| DeepSeek | 对话模型 |
| Milvus | 向量数据库 |

---

## 📦 安装指南

### 环境要求
- Python 3.9+
- Node.js 18+
- MySQL 8.0+

### 后端安装

```bash
# 克隆仓库
git clone https://github.com/CCCT173/CognitiveTopology_AgentFlow.git
cd CognitiveTopology

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接和API密钥

# 数据库迁移
alembic upgrade head

# 启动服务
python main.py
```

### 前端安装

```bash
cd web

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

### Docker部署

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

---

## 📖 使用方法

### 快速开始

1. **启动服务**
   ```bash
   # 后端
   python main.py
   
   # 前端
   cd web && npm run dev
   ```

2. **访问界面**
   - 前端地址：`http://localhost:5173`
   - 后端API：`http://localhost:8001/api/v1`
   - 文档地址：`http://localhost:8001/docs`

3. **登录系统**
   - 默认管理员账号：`admin@example.com`
   - 默认密码：`admin123`

### 创建工作流

1. 点击左侧菜单 **工作流**
2. 点击 **新建工作流**
3. 从左侧节点面板拖拽节点到画布
4. 连接节点建立流程关系
5. 点击节点配置参数
6. 点击 **运行** 执行工作流

### 创建Agent

1. 点击左侧菜单 **Agent**
2. 点击 **新建Agent**
3. 配置Agent名称、描述和系统提示词
4. 选择Agent类型（ReAct/工作流/Skill）
5. 点击 **保存**

---

## 🎯 主要特性

### 架构特点
- 📐 **模块化设计**：清晰的分层架构，易于扩展
- 🔌 **插件化系统**：支持自定义工具和技能
- 📡 **异步处理**：支持长任务和后台执行
- 🛡️ **沙箱隔离**：代码执行安全隔离（L1/L3双层防护）

### 性能优化
- ⚡ **缓存策略**：多级缓存提升响应速度
- 📊 **索引优化**：数据库查询性能优化
- 🔄 **异步任务**：任务队列处理耗时操作
- 📈 **监控指标**：系统监控集成

### 安全特性
- 🔐 **密码加密**：Fernet对称加密存储
- 🛡️ **输入验证**：严格的参数校验和过滤
- 🔑 **API密钥管理**：工作流API密钥生成和管理
- 📋 **审计日志**：完整的操作记录追踪
- 🧱 **沙箱隔离**：AST静态检查+子进程隔离

---

## 🤝 贡献指南

欢迎贡献代码！请遵循以下流程：

### 贡献步骤

1. **Fork仓库**
   - 点击页面右上角的 Fork 按钮

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **开发功能**
   - 编写代码
   - 添加测试
   - 更新文档

4. **提交代码**
   ```bash
   git add .
   git commit -m "feat: 添加新功能"
   ```

5. **推送分支**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **创建PR**
   - 在GitHub上创建 Pull Request
   - 等待审核和合并

### 代码规范

- 📝 **Python**：遵循 PEP8 规范
- 📘 **TypeScript**：遵循 Airbnb 规范
- 📄 **提交信息**：使用 Conventional Commits 格式
- 🧪 **测试覆盖**：新增功能需添加单元测试

---

## 📄 许可证

本项目采用 **MIT License** 开源许可。详见 [LICENSE](LICENSE) 文件。

---

## 📞 联系方式

- 📧 邮箱：1839964900@qq.com
- 🐙 GitHub：[CCCT173/CognitiveTopology_AgentFlow](https://github.com/CCCT173/CognitiveTopology_AgentFlow)
- 📚 文档：[项目文档](https://github.com/CCCT173/CognitiveTopology_AgentFlow/wiki)

---

## 🙏 致谢

感谢以下开源项目的支持：

- [FastAPI](https://fastapi.tiangolo.com/) - 高性能API框架
- [React](https://react.dev/) - UI框架
- [Tailwind CSS](https://tailwindcss.com/) - 样式框架
- [Milvus](https://milvus.io/) - 向量数据库
- [Alembic](https://alembic.sqlalchemy.org/) - 数据库迁移

---

**🌟 如果你喜欢这个项目，请给它一个 Star！**
