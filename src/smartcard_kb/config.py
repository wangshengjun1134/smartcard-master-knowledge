"""配置模块"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    app_name: str = "SmartCard Master Knowledge Base"
    debug: bool = False
    
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
