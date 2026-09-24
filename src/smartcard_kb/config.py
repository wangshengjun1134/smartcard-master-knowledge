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
    openai_model: str = "gpt-4"

    # 嵌入模型配置
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Docling 模型路径
    docling_models_path: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
