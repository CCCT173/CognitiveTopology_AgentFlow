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

The platform provides four-level security isolation mechanisms (L0-L3) with differentiated isolation strategies based on execution risk levels to ensure code execution safety and reliability.

**Sandbox Level Definition**:

| Sandbox Level | Isolation Capability | Use Case | Execution Restrictions | Risk Level |
|--------------|---------------------|----------|----------------------|------------|
| **L0 - Host Access** | Direct host access | File operations, system command execution | Whitelist directories, sensitive file blocking, HITL confirmation | High/Critical |
| **L1 - Basic Sandbox** | AST static check + subprocess isolation | Simple script execution, data processing, Skill execution | Filesystem forbidden, network forbidden, whitelist standard libraries | Low |
| **L2 - Platform Tools** | API-level operations | Workflow operations, Agent management, Skill management | RBAC permission control, operation audit logs | Medium |
| **L3 - Advanced Sandbox** | Dedicated venv + workspace isolation | Complex code execution, data science computing, third-party dependencies | Full network access, temporary filesystem, resource limits | Medium/High |

**Level Details**:

**L0 - Host Access**:
- Allows direct access to host filesystem and shell command execution
- Only whitelist directories allowed (`~/.agentflow` + current project directory)
- Sensitive files automatically blocked (`.env`, `.ssh`, `.pem`, `.key`, etc.)
- High-risk operations (write, delete, shell commands) require user confirmation (HITL mechanism)
- Included tools: `host_read`, `host_write`, `host_edit`, `host_delete`, `host_move`, `host_list_dir`, `host_info`, `host_shell`

**L1 - Basic Sandbox**:
- AST static check: blocks dangerous module imports (`os`, `sys`, `subprocess`, etc.) and dangerous operations (`eval`, `exec`, `open`, etc.)
- Subprocess isolation: code runs in independent Python process, auto-terminates on timeout (default 5 seconds)
- Whitelist standard libraries: only 24 safe modules allowed (`math`, `re`, `json`, `datetime`, etc.)
- Suitable for Skill code execution and simple data processing

**L2 - Platform Tools**:
- Operations through platform APIs, constrained by RBAC role permissions
- Supports workflow create/edit/run, Agent management, Skill management, knowledge base management
- Role permission matrix: super_admin (all permissions), admin (management permissions), user (own resource permissions)
- Complete operation audit logs, supporting operation traceability

**L3 - Advanced Sandbox**:
- Dedicated venv environment: pre-installed data science packages (numpy, pandas, etc.)
- Workspace isolation: each session has independent workspace directory (`~/.agentflow/ws/{session_id}/`)
- Workspace API: built-in file operation API with path traversal checks
- Full network access: supports HTTP requests (via `ws.fetch`)
- Resource limits: CPU (60 seconds), memory (2GB), process count (100-200), timeout (60 seconds)

**Security Features**:

- **Process Isolation**: L1/L3 each execution task runs in an independent process space, resources are automatically cleaned up after process termination
- **Timeout Protection**: L1 default timeout 5 seconds, L3 default timeout 60 seconds, processes are automatically terminated on timeout
- **Resource Limits**: CPU, memory, and process count quota control (L3)
- **Path Security**: L0/L3 includes path traversal checks, access to files outside whitelist/workspace directory is prohibited
- **Dangerous Operation Interception**: Blocking system command execution and sensitive file access
- **HITL Confirmation**: L0 high-risk operations require manual user confirmation
- **Execution Audit**: Complete execution logs and operation records

**Security Boundaries**:

| Boundary Type | L0 Host | L1 Basic | L2 Platform | L3 Advanced |
|--------------|---------|----------|-------------|-------------|
| Filesystem | Whitelist dirs | Forbidden | API level | Workspace only |
| Network Access | Full | Forbidden | API level | HTTP/HTTPS allowed |
| System Commands | Allowed (with confirmation) | Forbidden | Forbidden | Direct execution forbidden |
| Standard Libraries | Full access | Whitelist (24) | - | Full access |
| Third-Party Packages | Forbidden | Forbidden | - | Pre-installed + dynamic installation |
| Permission Control | HITL confirmation | Static check | RBAC roles | Workspace API |

**Core APIs**:

**L0 Host Tools**:
- `host_read(path)`: Read host file (read-only, no confirmation needed)
- `host_write(path, content)`: Write host file (high-risk, needs confirmation)
- `host_edit(path, old_str, new_str)`: Edit file content (high-risk, needs confirmation)
- `host_delete(path)`: Delete file/empty directory (critical, needs confirmation)
- `host_list_dir(path)`: List directory contents (read-only, no confirmation needed)
- `host_shell(command)`: Execute shell command (confirmation depends on command type)

**L3 Workspace API**:
- `ws.read(path)`: Read file content
- `ws.write(path, content)`: Write file content
- `ws.list_dir(path)`: List directory contents
- `ws.exists(path)`: Check if file exists
- `ws.fetch(url)`: Send HTTP request
- `ws.install_pkg(name)`: Install pip package

---

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
