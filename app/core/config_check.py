"""启动时配置校验, fail-fast"""
import os
from app.core.config import settings
from app.core.logger import logger


def validate_config():
    errors = []

    # 必须有至少一个 chat key
    if settings.LLM_PROVIDER == "giteeai" and not settings.GITEEAI_API_KEY:
        errors.append("LLM_PROVIDER=giteeai 但 GITEEAI_API_KEY 为空")
    if settings.LLM_PROVIDER == "ark" and not settings.ARK_API_KEY:
        errors.append("LLM_PROVIDER=ark 但 ARK_API_KEY 为空")

    if settings.EMBEDDING_PROVIDER == "giteeai" and not settings.GITEEAI_API_KEY:
        errors.append("EMBEDDING_PROVIDER=giteeai 但 GITEEAI_API_KEY 为空")
    if settings.EMBEDDING_PROVIDER == "ark" and not settings.ARK_API_KEY:
        errors.append("EMBEDDING_PROVIDER=ark 但 ARK_API_KEY 为空")

    if settings.JWT_SECRET and ("change-me" in settings.JWT_SECRET and settings.APP_ENV == "prod"):
        errors.append("生产环境必须修改 JWT_SECRET")

    if settings.EMBEDDING_DIM <= 0:
        errors.append(f"EMBEDDING_DIM 非法: {settings.EMBEDDING_DIM}")

    # 目录可写
    upload_dir = str(settings.upload_dir_abs)
    if not os.access(upload_dir, os.W_OK):
        errors.append(f"上传目录不可写: {upload_dir}")
    milvus_dir = os.path.dirname(settings.milvus_db_abs)
    os.makedirs(milvus_dir, exist_ok=True)
    if not os.access(milvus_dir, os.W_OK):
        errors.append(f"Milvus 数据目录不可写: {milvus_dir}")

    if errors:
        for e in errors:
            logger.error(f"[CONFIG] {e}")
        raise SystemExit("配置校验失败,请检查 .env:\n  - " + "\n  - ".join(errors))
    logger.info(f"[CONFIG] 校验通过 provider={settings.LLM_PROVIDER}/{settings.EMBEDDING_PROVIDER} dim={settings.EMBEDDING_DIM}")
