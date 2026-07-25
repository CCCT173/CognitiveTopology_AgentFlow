"""
应用配置: 通过 pydantic-settings 从环境变量/.env加载, 统一集中管理
"""
import os
import secrets
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录 = 本文件向上 3 级 (app/core/config.py -> ../../..)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _ensure_jwt_secret() -> str:
    """
    如果 .env 里 JWT_SECRET 还是默认占位值, 自动生成一个随机 secret 并**更新** .env。
    - 用替换而非追加，避免脏行
    - 不会覆盖已有非默认值
    - 启动时打印一次性警告提示备份
    """
    env_path = PROJECT_ROOT / ".env"
    placeholder = "change-me-in-prod-please-use-a-long-random-string-at-least-32-chars"

    try:
        content = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    except OSError:
        return placeholder

    import re
    m = re.search(r'^JWT_SECRET=(.*)$', content, re.MULTILINE)
    if m:
        val = m.group(1).strip().strip('"').strip("'")
        if val and val != placeholder:
            return val
        # 占位符 → 替换
        new_secret = secrets.token_urlsafe(48)
        new_content = re.sub(
            r'^JWT_SECRET=.*$',
            f'JWT_SECRET={new_secret}',
            content,
            count=1,
            flags=re.MULTILINE,
        )
        env_path.write_text(new_content, encoding="utf-8")
    else:
        # 没有 JWT_SECRET 行 → 追加
        new_secret = secrets.token_urlsafe(48)
        with env_path.open("a", encoding="utf-8") as f:
            f.write(
                "\n# Auto-generated on first start. PLEASE BACK UP THIS VALUE.\n"
                f"JWT_SECRET={new_secret}\n"
            )

    import sys
    print(
        "\n"
        "=" * 70 + "\n"
        "  ⚠️  已自动生成新的 JWT_SECRET 并写入 .env\n"
        f"  secret: {new_secret[:12]}...{new_secret[-8:]}\n"
        "  请备份 .env 文件。丢失后所有已签发的 token 将失效。\n"
        "=" * 70 + "\n",
        file=sys.stderr,
    )
    return new_secret


class Settings(BaseSettings):
    # ---------- 应用 ----------
    APP_NAME: str = "agentflow"
    APP_VERSION: str = "0.2.0"
    APP_ENV: str = "dev"              # dev / test / prod
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8001

    # ---------- 鉴权 ----------
    API_TOKEN: Optional[str] = None   # Bearer Token (管理端简单Token, 未启用JWT时备用)
    JWT_SECRET: str = _ensure_jwt_secret()
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 15         # access token 短有效期 15 分钟
    JWT_REFRESH_EXPIRE_DAYS: int = 7     # refresh token 7 天

    # ---------- 数据库 ----------
    # 默认 SQLite (开箱即用,无需外部数据库); MySQL 示例:
    #   mysql+pymysql://user:pwd@host:port/dbname?charset=utf8mb4
    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'app.db'}"

    # ---------- LLM (通过 .env 配置,不要在代码里写真实 key) ----------
    # 当前使用的 chat 提供方: ark(默认) / giteeai / deepseek
    LLM_PROVIDER: str = "ark"
    # GiteeAI 模力方舟 (OpenAI 兼容)
    GITEEAI_API_KEY: Optional[str] = None
    GITEEAI_BASE_URL: str = "https://ai.gitee.com/v1"
    GITEEAI_CHAT_MODEL: str = "deepseek-v3"
    # ARK 火山方舟 Agent Plan
    ARK_API_KEY: Optional[str] = None
    ARK_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/plan/v3"
    ARK_CHAT_MODEL: str = "doubao-seed-evolving"
    # ARK 多模态 embedding (文字/图片/视频)。模型名填控制台创建的 endpoint id,
    # 例: doubao-embedding-vision-xxx / doubao-embedding-large-text-240915
    ARK_EMBEDDING_MODEL: str = "doubao-embedding-vision"
    # DeepSeek 直连
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ---------- Embedding / Rerank ----------
    # provider: ark(多模态) / giteeai(Qwen3) / fake(离线兜底)
    EMBEDDING_PROVIDER: str = "ark"
    EMBEDDING_MODEL_NAME: str = ""      # provider=giteeai 时用
    RERANKER_PROVIDER: str = "giteeai"  # giteeai(Qwen3-Reranker-4B) / bm25(离线兜底)
    RERANKER_MODEL_NAME: str = "Qwen/Qwen3-Reranker-4B"
    EMBEDDING_DIM: int = 2048           # ARK doubao-embedding-vision 返回 2048 维

    # ---------- 向量库 ----------
    # milvus_lite: 单文件本地库,数据存项目 data/milvus.db (推荐Demo/本地原型)
    # milvus:      连接独立 Milvus 服务(MILVUS_HOST/PORT)
    VECTOR_STORE: str = "milvus_lite"
    MILVUS_DB_PATH: str = "data/milvus.db"      # milvus_lite 数据文件路径(项目内)
    MILVUS_HOST: str = "127.0.0.1"
    MILVUS_PORT: int = 19530

    # ---------- 文件上传 ----------
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 50

    # ---------- LLM 参数配置 ----------
    # 系统提示词: 全局默认的系统消息
    LLM_SYSTEM_PROMPT: str = "You are a helpful AI assistant. Please answer questions accurately and concisely."
    # 最大上下文长度: 模型能处理的最大上下文 token 数
    LLM_MAX_CONTEXT_LENGTH: int = 8192
    # 最大输出令牌数: 模型单次响应的最大 token 数
    LLM_MAX_OUTPUT_TOKENS: int = 2048
    # 思考推理等级: 0-5, 0=关闭思考, 5=深度思考
    LLM_THINKING_LEVEL: int = 2
    # 是否多模态输入
    LLM_IS_MULTIMODAL_INPUT: bool = False
    # 是否嵌入模型
    LLM_IS_EMBEDDING_MODEL: bool = False
    # 温度系数: 0.0-1.0, 控制输出随机性
    LLM_TEMPERATURE: float = 0.7
    # 顶部P值: 0.0-1.0, 控制输出多样性
    LLM_TOP_P: float = 0.9
    # 频率惩罚: -2.0-2.0, 减少重复内容
    LLM_FREQUENCY_PENALTY: float = 0.0
    # 存在惩罚: -2.0-2.0, 鼓励新主题
    LLM_PRESENCE_PENALTY: float = 0.0
    # 响应超时时间(秒)
    LLM_RESPONSE_TIMEOUT: int = 60
    # API 调用重试次数
    LLM_API_RETRY_COUNT: int = 2

    # ---------- 安全 ----------
    # CORS 允许的 origin,逗号分隔; 默认只放行本地前端开发端口
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8001"
    # 登录限流: 同 IP/账号 10 分钟内失败 N 次锁定
    LOGIN_RATE_LIMIT_MAX: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SEC: int = 600
    PASSWORD_MIN_LEN: int = 6
    # 数据库连接密码加密密钥 (Fernet 格式, 44 字符 base64)
    DB_CONNECTION_ENCRYPT_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def upload_dir_abs(self) -> Path:
        """uploads 目录绝对路径,自动创建"""
        p = PROJECT_ROOT / self.UPLOAD_DIR if not os.path.isabs(self.UPLOAD_DIR) else Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def milvus_db_abs(self) -> str:
        """milvus_lite 数据路径,相对路径转成绝对路径避免 cwd 问题"""
        if os.path.isabs(self.MILVUS_DB_PATH):
            return self.MILVUS_DB_PATH
        return str(PROJECT_ROOT / self.MILVUS_DB_PATH)

    # ---------- LLM 参数验证 ----------
    @field_validator("LLM_TEMPERATURE")
    def validate_temperature(cls, v):
        """验证温度系数: 0.0-1.0"""
        if not (0.0 <= v <= 1.0):
            raise ValueError("LLM_TEMPERATURE 必须在 0.0-1.0 之间")
        return v

    @field_validator("LLM_TOP_P")
    def validate_top_p(cls, v):
        """验证顶部P值: 0.0-1.0"""
        if not (0.0 <= v <= 1.0):
            raise ValueError("LLM_TOP_P 必须在 0.0-1.0 之间")
        return v

    @field_validator("LLM_FREQUENCY_PENALTY")
    def validate_frequency_penalty(cls, v):
        """验证频率惩罚: -2.0-2.0"""
        if not (-2.0 <= v <= 2.0):
            raise ValueError("LLM_FREQUENCY_PENALTY 必须在 -2.0-2.0 之间")
        return v

    @field_validator("LLM_PRESENCE_PENALTY")
    def validate_presence_penalty(cls, v):
        """验证存在惩罚: -2.0-2.0"""
        if not (-2.0 <= v <= 2.0):
            raise ValueError("LLM_PRESENCE_PENALTY 必须在 -2.0-2.0 之间")
        return v

    @field_validator("LLM_THINKING_LEVEL")
    def validate_thinking_level(cls, v):
        """验证思考推理等级: 0-5"""
        if not (0 <= v <= 5):
            raise ValueError("LLM_THINKING_LEVEL 必须在 0-5 之间")
        return v

    @field_validator("LLM_API_RETRY_COUNT")
    def validate_retry_count(cls, v):
        """验证重试次数: 0-10"""
        if not (0 <= v <= 10):
            raise ValueError("LLM_API_RETRY_COUNT 必须在 0-10 之间")
        return v

    @field_validator("LLM_RESPONSE_TIMEOUT")
    def validate_timeout(cls, v):
        """验证超时时间: 1-600秒"""
        if not (1 <= v <= 600):
            raise ValueError("LLM_RESPONSE_TIMEOUT 必须在 1-600 秒之间")
        return v


settings = Settings()
