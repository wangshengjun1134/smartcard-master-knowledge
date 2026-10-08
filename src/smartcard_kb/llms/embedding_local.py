"""本地 Embedding 后端（基于 sentence-transformers）"""

from typing import List, Optional

from smartcard_kb.logger import logger
from smartcard_kb.config import settings

from .embedding_base import EmbeddingBackend


class LocalEmbeddingBackend(EmbeddingBackend):
    """本地 Embedding 后端"""

    def __init__(self, model_name: Optional[str] = None):
        """
        初始化本地 Embedding 后端

        :param model_name: 模型路径或 HuggingFace 模型 ID，默认使用 settings.embedding_model
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("使用本地 Embedding 后端需要安装 sentence-transformers: pip install sentence-transformers")

        model_name = model_name or str(settings.embedding_model)
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        logger.info(f"本地 Embedding 后端初始化完成: {model_name}")

    def embed(self, text: str) -> List[float]:
        """调用本地模型生成向量嵌入"""
        embedding = self.model.encode(text)
        return embedding.tolist()
