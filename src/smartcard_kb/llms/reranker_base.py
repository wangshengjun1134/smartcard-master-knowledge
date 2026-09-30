"""重排后端抽象基类"""

from abc import ABC, abstractmethod
from typing import List, Tuple


class RerankerBackend(ABC):
    """重排后端抽象基类"""

    @abstractmethod
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10,
    ) -> List[Tuple[int, float]]:
        """
        对文档列表进行重排
        
        :param query: 查询文本
        :param documents: 文档列表
        :param top_k: 返回前 K 个结果
        :return: 排序后的 (原始索引, 分数) 列表
        """
        pass
