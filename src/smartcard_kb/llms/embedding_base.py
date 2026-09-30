"""Embedding 后端抽象基类"""

from abc import ABC, abstractmethod
from typing import List


class EmbeddingBackend(ABC):
    """Embedding 后端抽象基类"""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        生成文本的向量嵌入
        
        :param text: 输入文本
        :return: 向量嵌入列表
        """
        pass
