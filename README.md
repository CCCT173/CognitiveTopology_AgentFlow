# 🔗 CognitiveTopology - 认知拓扑工作流平台

> 一个现代化的多Agent协作平台，支持可视化工作流编排、智能Agent框架、RAG知识库和技能系统，助力企业构建智能化业务流程。

![GitHub](https://img.shields.io/github/license/CCCT173/CognitiveTopology_AgentFlow)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![React](https://img.shields.io/badge/React-18+-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-blue.svg)

---

## 🎯 项目简介

**CognitiveTopology** 是一个基于 FastAPI + React 构建的企业级多Agent协作平台，致力于帮助开发者快速构建、部署和管理智能工作流。平台融合了先进的AI技术，支持多种Agent架构模式和可视化工作流编排，为企业提供智能化的业务流程解决方案。

### ✨ 核心价值

- **🎨 可视化工作流**：拖拽式节点编辑器，轻松构建复杂业务流程
- **🤖 多Agent架构**：支持ReAct、单Agent、工作流封装等多种模式
- **📚 RAG知识库**：高效的文档检索和向量存储能力
- **🛠️ 技能系统**：可扩展的技能创建和共享机制
- **🔒 企业级安全**：完整的权限管理和审计日志

---

## 🚀 核心功能

### 1. 可视化工作流编辑器
- 🎯 12种节点类型：LLM、工具、Skill、条件、Agent、代码、循环、并行、转换、延迟、开始、结束
- 🔗 磁吸效果与自动布局调整
- ⚡ 实时连线编辑和条件配置
- 🖱️ 右键上下文菜单（复制、删除、重命名）

### 2. 动态参数配置系统
- 📋 8种参数类型：文本、数字、滑块、选择、开关、文本域、JSON、代码
- 🎯 节点类型专属配置面板
- 🔄 参数分组、依赖显示、条件渲染
- ⚡ 实时参数验证和智能提示

### 3. Agent框架
- 🧠 **ReAct模式**：推理+行动的智能决策循环
- 🔄 **工作流代理**：将工作流封装为Agent
- 🛠️ **Skill代理**：基于技能的任务执行
- 📊 **MetaRunner**：多Agent协作编排

### 4. 技能系统
- 📦 技能创建、导入、导出
- 🧪 技能测试和调试面板
- 🔄 技能版本管理
- 📤 技能市场和共享

### 5. RAG知识库
- 📁 文档上传和分块
- 🔍 向量检索和重排序
- 📊 知识库管理和统计
- 🔗 多模态嵌入支持

### 6. 企业级特性
- 👥 用户和群组管理
- 📝 细粒度权限控制
- 📋 操作审计日志
- 🔄 资源版本管理
- 🌐 多语言支持（中文/英文）

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
- 🛡️ **沙箱隔离**：代码执行安全隔离

### 性能优化
- ⚡ **缓存策略**：多级缓存提升响应速度
- 📊 **索引优化**：数据库查询性能优化
- 🔄 **异步任务**：Celery任务队列处理耗时操作
- 📈 **监控指标**：Prometheus监控集成

### 安全特性
- 🔐 **密码加密**：Fernet对称加密存储
- 🛡️ **输入验证**：严格的参数校验和过滤
- 🔑 **API密钥管理**：工作流API密钥生成和管理
- 📋 **审计日志**：完整的操作记录追踪

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

- 📧 邮箱：contact@cognitivetopology.dev
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
