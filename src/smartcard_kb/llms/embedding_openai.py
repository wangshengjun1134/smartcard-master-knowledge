"""OpenAI 兼容 Embedding 后端"""

from typing import List

from .embedding_base import EmbeddingBackend


class OpenAIEmbeddingBackend(EmbeddingBackend):
    """OpenAI 兼容的 Embedding 后端"""

    def __init__(self, api_key: str, base_url: str, model: str = "text-embedding-3-small", timeout: int = 60):
        """
        初始化 OpenAI 兼容后端
        
        :param api_key: API Key
        :param base_url: API 基础 URL
        :param model: 模型名称
        :param timeout: 请求超时时间（秒）
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("使用 OpenAI 兼容后端需要安装 openai: pip install openai")

        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self.model = model
        print(f"OpenAI Embedding 后端初始化完成: {base_url}, 模型: {model}")

    def embed(self, text: str) -> List[float]:
        """调用 OpenAI 兼容 API 生成向量嵌入"""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding
