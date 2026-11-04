"""配置模块"""

import os
from pathlib import Path

from pydantic_settings import BaseSettings


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 模型目录（与项目平级，不在项目内部）
MODELS_DIR = PROJECT_ROOT.parent / "models"


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    app_name: str = "SmartCard Master Knowledge Base"
    debug: bool = False

    # PostgreSQL 配置
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "123456"
    postgres_db: str = "smartcard_master_knowledge"

    # Qdrant 配置
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # OpenAI 配置
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4"

    # VLM 配置
    vlm_backend_type: str = "openai"
    vlm_openai_api_key: str = ""
    vlm_openai_base_url: str = ""
    vlm_openai_model: str = "qwen-vl-plus"
    vlm_local_model_path: str = str(MODELS_DIR / "Qwen3-VL-8B-Instruct")

    # Embedding 配置
    embedding_openai_api_key: str = ""
    embedding_openai_base_url: str = ""
    embedding_openai_model: str = "text-embedding-3-small"
    embedding_model: str = str(MODELS_DIR / "bge-m3")

    # 重排模型配置
    reranker_model: str = str(MODELS_DIR / "bge-reranker-v2-m3")

    # Docling 模型路径
    docling_models_path: str = str(MODELS_DIR / "docling-models")

    # MinIO 对象存储配置
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "admin123"
    minio_bucket: str = "specs"
    minio_pictures_bucket: str = "specs-pictures"
    minio_secure: bool = False

    # 本地缓存目录（MinIO 文件首次读取时缓存到此目录）
    specs_cache_dir: str = str(PROJECT_ROOT / "specs")

    class Config:
        env_file = ".env"


settings = Settings()
