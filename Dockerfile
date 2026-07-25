# ====== AgentFlow Dockerfile ======
# 多阶段构建: 后端 Python + 前端静态文件

# ---------- Stage 1: 前端构建 ----------
FROM node:22-alpine AS frontend-builder
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com
COPY web/ ./
RUN npm run build

# ---------- Stage 2: 后端运行 ----------
FROM python:3.13-slim

LABEL maintainer="agentflow"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 安装系统依赖 (MySQL client + Milvus Lite 运行时)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端源码
COPY app/ ./app/
COPY main.py pyproject.toml alembic.ini ./
COPY scripts/ ./scripts/

# 复制前端构建产物
COPY --from=frontend-builder /app/web/dist ./web/dist
# 让 FastAPI 也能 serve 前端静态文件
COPY web/dist/index.html ./web/dist/

# 创建必要目录
RUN mkdir -p data uploads logs backups

# 暴露端口
EXPOSE 8001

# 启动命令
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
