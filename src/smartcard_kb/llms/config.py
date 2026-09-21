"""LLM/VLM 配置"""

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict


class VLMConfig(BaseModel):
    """VLM 配置"""

    model_config = SettingsConfigDict(env_prefix="VLM_", env_file=".env", extra="ignore")

    # 后端类型: local 或 openai
    backend_type: str = Field(default="openai", description="后端类型: local 或 openai")

    # OpenAI 兼容后端配置
    openai_api_key: str = Field(default="", description="OpenAI API Key")
    openai_base_url: str = Field(default="", description="OpenAI API 基础 URL")
    openai_model: str = Field(default="qwen-vl-max", description="OpenAI 模型名称")

    # 本地后端配置
    local_model_path: str = Field(
        default=r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct",
        description="本地模型路径"
    )

    @property
    def is_openai_backend(self) -> bool:
        return self.backend_type == "openai"

    @property
    def is_local_backend(self) -> bool:
        return self.backend_type == "local"
