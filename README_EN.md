# 🔗 CognitiveTopology - Cognitive Topology Workflow Platform

> A modern multi-agent collaboration platform that supports visual workflow orchestration, intelligent agent frameworks, RAG knowledge bases, and skill systems, empowering enterprises to build intelligent business processes.

![GitHub](https://img.shields.io/github/license/CCCT173/CognitiveTopology_AgentFlow)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![React](https://img.shields.io/badge/React-18+-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5+-blue.svg)

---

**Language** | [English](README_EN.md) | [中文](README.md)

---

## 🎯 Project Overview

**CognitiveTopology** is an enterprise-grade multi-agent collaboration platform built on FastAPI + React, designed to help developers quickly build, deploy, and manage intelligent workflows. The platform integrates advanced AI technologies, supports multiple agent architecture patterns and visual workflow orchestration, providing intelligent business process solutions for enterprises.

The agents developed in this project possess complete capabilities to control core system functions, including but not limited to creating sub-agent instances, designing and executing workflows, managing databases (including CRUD operations), managing user groups and permission assignments, and other key functional modules. These agents provide experienced professional users with a more efficient and direct system operation method, significantly improving work efficiency. Meanwhile, the system incorporates multi-level security sandbox mechanisms, ensuring the security of core data and system resources through strict permission isolation and operation auditing.

### ✨ Core Value

- **🎨 Visual Workflow**: Drag-and-drop node editor for building complex business processes
- **🤖 Multi-Agent Architecture**: Supports ReAct, single agent, workflow encapsulation, and other patterns
- **📚 RAG Knowledge Base**: Efficient document retrieval and vector storage capabilities
- **🛠️ Skill System**: Extensible skill creation and sharing mechanism
- **🔒 Enterprise-Grade Security**: Complete permission management and audit logging
- **🧱 Security Sandbox**: Multi-layer isolation architecture ensuring execution safety

---

## 🚀 Core Features

### 1. Agent Security Sandbox Levels

The platform provides multi-layer security isolation mechanisms with differentiated isolation strategies based on execution risk levels:

| Sandbox Level | Isolation Capability | Use Case | Execution Restrictions |
|--------------|---------------------|----------|----------------------|
| **L1 - Basic Sandbox** | Code execution environment isolation | Simple script execution, data processing | Read-only filesystem, restricted network |
| **L3 - Advanced Sandbox** | Full containerized isolation | Complex code execution, third-party dependencies | Full network access, temporary filesystem |

**Security Features**:
- 🛡️ **Process Isolation**: Each execution task runs in an independent process space
- 🔒 **Resource Limits**: CPU, memory, and disk I/O quota control
- 📋 **Execution Audit**: Complete execution logs and operation records
- ⏱️ **Timeout Protection**: Automatic termination of timeout execution tasks
- 🚫 **Dangerous Operation Interception**: Blocking system command execution and sensitive file access

### 2. Full Operational Control Over Cognitive Topology Environment

- 🎯 **Environment Configuration Management**: Unified management of LLM parameters, API keys, and connection configurations
- 🔄 **Configuration Version Control**: Support for saving, loading, and switching configuration schemes
- ⚡ **Hot Update Mechanism**: Configuration changes take effect in real-time without service restart
- 📊 **System Monitoring**: Real-time monitoring of system status, resource usage, and execution metrics
- 🛠️ **Operations Tools**: Command-line tools supporting automated operations

### 3. Sub-Agent Creation Functionality

- 👶 **Sub-Agent Creation**: Create specialized sub-agents based on parent agents
- 🔗 **Hierarchical Relationships**: Maintain parent-child hierarchical structures between agents
- 📋 **Permission Inheritance**: Sub-agents inherit permission configurations from parent agents
- 🔄 **Sync Mechanism**: Support hierarchical synchronization of configuration changes
- 🧹 **Batch Management**: Support batch operations and management of sub-agents

### 4. Workflow Automation Tools

- ⏰ **Scheduled Triggers**: Support CRON expression configuration for scheduled tasks
- 📡 **Event Triggers**: Trigger workflow execution based on external events
- 🔄 **Loop Processing**: Support loop nodes for iterating over datasets
- ⚡ **Parallel Execution**: Support multi-branch parallel processing for improved efficiency
- 📤 **Webhook Integration**: Support external systems to trigger via Webhook
- 📊 **Execution Tracking**: Complete workflow execution logs and status tracking

### 5. Team Collaboration and Management Systems

- 👥 **User Management**: Complete user registration, authentication, and role management
- 👨‍👩‍👧 **Group Management**: Support for creating groups and assigning members
- 📝 **Permission Control**: Fine-grained resource access permission management
- 🔄 **Collaboration Features**: Support for sharing and collaboration on workflows and skills
- 📋 **Version Management**: Resource version history and rollback functionality
- 📈 **Optimistic Locking**: Concurrent editing conflict detection and handling

### 6. Visual Workflow Editor

- 🎯 12 node types: LLM, Tool, Skill, Condition, Agent, Code, Loop, Parallel, Transform, Delay, Start, End
- 🔗 Magnetic snap effect with auto-layout adjustment
- ⚡ Real-time connection editing and condition configuration
- 🖱️ Right-click context menu (copy, delete, rename)

### 7. Dynamic Parameter Configuration System

- 📋 8 parameter types: text, number, slider, select, switch, textarea, JSON, code
- 🎯 Node-type-specific configuration panels
- 🔄 Parameter grouping, dependency display, conditional rendering
- ⚡ Real-time parameter validation and intelligent suggestions

### 8. Agent Framework

- 🧠 **ReAct Mode**: Reasoning + action intelligent decision loop
- 🔄 **Workflow Agent**: Encapsulate workflows as agents
- 🛠️ **Skill Agent**: Skill-based task execution
- 📊 **MetaRunner**: Multi-agent collaborative orchestration

### 9. Skill System

- 📦 Skill creation, import, and export
- 🧪 Skill testing and debugging panel
- 🔄 Skill version management
- 📤 Skill marketplace and sharing

### 10. RAG Knowledge Base

- 📁 Document upload and chunking
- 🔍 Vector retrieval and re-ranking
- 📊 Knowledge base management and statistics
- 🔗 Multi-modal embedding support

---

## 🎨 User Experience Enhancements

### Advanced User Features

- ⌨️ **Command Palette**: Support shortcut key to open command search panel
- ⚡ **Quick Actions**: One-click access to frequently used functions
- 🎯 **Intelligent Suggestions**: Context-based operation suggestions
- 🔄 **Theme Switching**: Support for light/dark themes
- 🌐 **Multi-Language Support**: Chinese/English interface switching

### High-Risk Operation Security Mechanisms

All high-risk operations require strict manual confirmation to ensure data security and integrity:

| Operation Type | Security Mechanism | Confirmation Method |
|----------------|-------------------|---------------------|
| 🗑️ Resource Deletion | Secondary confirmation dialog | Manual deletion confirmation |
| 🔄 Version Rollback | Impact scope preview | Confirm rollback scope |
| 🔑 Permission Change | Permission change log | Operation approval process |
| 📤 Data Export | Data scope confirmation | Confirm export content |
| 🚀 Deployment Operation | Deployment preview | Confirm deployment configuration |

---

## 🏗️ Functional Architecture Analysis

### Architecture Design Principles

1. **Layered Architecture**: Frontend Presentation → API Gateway → Business Logic → Data Access
2. **Modular Design**: Each functional module is independently developed and deployed
3. **Loose Coupling**: Modules communicate through API interfaces, reducing dependencies
4. **Extensibility**: Support for plug-in based extension of new features

### Core Module Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Presentation                  │
│  WorkflowEditor | AgentManager | SkillCenter | Settings    │
├─────────────────────────────────────────────────────────────┤
│                      API Gateway                            │
│  Router | Middleware | Authentication | RateLimit          │
├─────────────────────────────────────────────────────────────┤
│                      Business Logic                         │
│  AgentService | WorkflowService | SkillService | RagService │
│  AuthService | UserService | GroupService                   │
├─────────────────────────────────────────────────────────────┤
│                      Data Access                            │
│  SQLAlchemy ORM | MySQL | Milvus Vector DB                 │
├─────────────────────────────────────────────────────────────┤
│                      AI Services                            │
│  LLM Providers | Embedding | Reranker | Tool Execution     │
└─────────────────────────────────────────────────────────────┘
```

### Competitive Advantages

- **Security Sandbox**: Multi-layer isolation architecture ensures execution safety
- **Visual Orchestration**: Intuitive workflow design experience
- **Dynamic Configuration**: Flexible parameter configuration system
- **Enterprise-Grade Features**: Complete permission management and collaboration capabilities
- **High Performance**: Asynchronous processing and caching strategies improve response speed

---

## 🛠️ Technology Stack

### Backend Technology
| Technology | Version | Purpose |
|------------|---------|---------|
| FastAPI | 0.100+ | High-performance API framework |
| SQLAlchemy | 2.0+ | ORM database operations |
| MySQL | 8.0+ | Relational database |
| Alembic | 1.12+ | Database migration |
| JWT | - | Identity authentication |
| Fernet | - | Sensitive information encryption |

### Frontend Technology
| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18+ | UI framework |
| TypeScript | 5+ | Type safety |
| Tailwind CSS | 3+ | Styling framework |
| Vite | 5+ | Build tool |
| Zustand | 4+ | State management |

### AI Services
| Service | Description |
|---------|-------------|
| VolcEngine Ark | LLM and embedding models |
| GiteeAI | Re-ranking models |
| DeepSeek | Chat models |
| Milvus | Vector database |

---

## 📦 Installation Guide

### Environment Requirements
- Python 3.9+
- Node.js 18+
- MySQL 8.0+

### Backend Installation

```bash
# Clone repository
git clone https://github.com/CCCT173/CognitiveTopology_AgentFlow.git
cd CognitiveTopology

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env file to configure database connection and API keys

# Database migration
alembic upgrade head

# Start service
python main.py
```

### Frontend Installation

```bash
cd web

# Install dependencies
npm install

# Development mode
npm run dev

# Production build
npm run build
```

### Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
```

---

## 📖 Usage

### Quick Start

1. **Start Services**
   ```bash
   # Backend
   python main.py
   
   # Frontend
   cd web && npm run dev
   ```

2. **Access Interface**
   - Frontend: `http://localhost:5173`
   - Backend API: `http://localhost:8001/api/v1`
   - Documentation: `http://localhost:8001/docs`

3. **Login**
   - Default admin: `admin@example.com`
   - Default password: `admin123`

### Create Workflow

1. Click **Workflows** in the left menu
2. Click **New Workflow**
3. Drag nodes from the left panel to the canvas
4. Connect nodes to establish flow relationships
5. Click nodes to configure parameters
6. Click **Run** to execute the workflow

### Create Agent

1. Click **Agents** in the left menu
2. Click **New Agent**
3. Configure agent name, description, and system prompt
4. Select agent type (ReAct/Workflow/Skill)
5. Click **Save**

---

## 🎯 Key Features

### Architecture Characteristics
- 📐 **Modular Design**: Clear layered architecture for easy extension
- 🔌 **Plug-in System**: Support for custom tools and skills
- 📡 **Asynchronous Processing**: Support for long-running tasks and background execution
- 🛡️ **Sandbox Isolation**: Secure isolation for code execution

### Performance Optimization
- ⚡ **Caching Strategy**: Multi-level caching improves response speed
- 📊 **Index Optimization**: Database query performance optimization
- 🔄 **Asynchronous Tasks**: Task queue for time-consuming operations
- 📈 **Monitoring Metrics**: System monitoring integration

### Security Features
- 🔐 **Password Encryption**: Fernet symmetric encryption storage
- 🛡️ **Input Validation**: Strict parameter validation and filtering
- 🔑 **API Key Management**: Workflow API key generation and management
- 📋 **Audit Logging**: Complete operation record tracking

---

## 🤝 Contribution Guide

Contributions are welcome! Please follow these steps:

### Contribution Steps

1. **Fork Repository**
   - Click the Fork button in the top-right corner

2. **Create Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Develop Feature**
   - Write code
   - Add tests
   - Update documentation

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

5. **Push Branch**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create PR**
   - Create a Pull Request on GitHub
   - Wait for review and merge

### Code Standards

- 📝 **Python**: Follow PEP8 standards
- 📘 **TypeScript**: Follow Airbnb standards
- 📄 **Commit Messages**: Use Conventional Commits format
- 🧪 **Test Coverage**: New features require unit tests

---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

---

## 📞 Contact

- 📧 Email: 1839964900@qq.com
- 🐙 GitHub: [CCCT173/CognitiveTopology_AgentFlow](https://github.com/CCCT173/CognitiveTopology_AgentFlow)
- 📚 Documentation: [Project Documentation](https://github.com/CCCT173/CognitiveTopology_AgentFlow/wiki)

---

## 🙏 Acknowledgments

Thanks to the following open-source projects:

- [FastAPI](https://fastapi.tiangolo.com/) - High-performance API framework
- [React](https://react.dev/) - UI framework
- [Tailwind CSS](https://tailwindcss.com/) - Styling framework
- [Milvus](https://milvus.io/) - Vector database
- [Alembic](https://alembic.sqlalchemy.org/) - Database migration

---

**🌟 If you like this project, please give it a Star!**
