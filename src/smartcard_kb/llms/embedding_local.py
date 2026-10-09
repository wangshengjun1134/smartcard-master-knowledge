"""本地 Embedding 后端（基于 sentence-transformers）"""

from pathlib import Path
from typing import List, Optional

from smartcard_kb.logger import logger
from smartcard_kb.config import settings, MODELS_DIR

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
        # Resolve to absolute path if relative
        model_path = Path(model_name)
        if not model_path.is_absolute():
            model_path = MODELS_DIR / model_name
        self.model = SentenceTransformer(str(model_path))
        self.model_name = str(model_path)
        logger.info(f"本地 Embedding 后端初始化完成: {self.model_name}")

    def embed(self, text: str) -> List[float]:
        """调用本地模型生成向量嵌入"""
        embedding = self.model.encode(text)
        return embedding.tolist()
