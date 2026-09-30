"""本地 Embedding 后端（基于 sentence-transformers）"""

from typing import List

from .embedding_base import EmbeddingBackend


class LocalEmbeddingBackend(EmbeddingBackend):
    """本地 Embedding 后端"""

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        初始化本地 Embedding 后端
        
        :param model_name: 模型名称
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("使用本地 Embedding 后端需要安装 sentence-transformers: pip install sentence-transformers")

        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        print(f"本地 Embedding 后端初始化完成: {model_name}")

    def embed(self, text: str) -> List[float]:
        """调用本地模型生成向量嵌入"""
        embedding = self.model.encode(text)
        return embedding.tolist()
