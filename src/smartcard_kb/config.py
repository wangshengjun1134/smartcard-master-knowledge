"""配置模块"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用配置
    app_name: str = "SmartCard Master Knowledge Base"
    debug: bool = False

    # PostgreSQL 配置
    postgres_host: str = "localhost"
    postgres_port: int = 54321
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
    vlm_openai_api_key: str = ""
    vlm_openai_base_url: str = ""
    vlm_openai_model: str = "qwen-vl-plus"

    # Embedding 配置
    embedding_openai_api_key: str = ""
    embedding_openai_base_url: str = ""
    embedding_openai_model: str = "text-embedding-3-small"
    embedding_model: str = "D:/softdata/workspaces/ai-models/bge-m3"

    # 重排模型配置
    reranker_model: str = "D:/softdata/workspaces/ai-models/bge-reranker-v2-m3"

    # Docling 模型路径
    docling_models_path: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
