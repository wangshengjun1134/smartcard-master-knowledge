"""VLM 后端抽象基类"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from PIL import Image


class VLMBackend(ABC):
    """VLM 后端抽象基类"""

    @abstractmethod
    def generate(
        self,
        image: Image.Image,
        messages: List[Dict[str, Any]],
        max_new_tokens: int = 512
    ) -> str:
        """
        调用 VLM 生成回复
        :param image: PIL Image 对象
        :param messages: 消息列表（OpenAI 格式）
        :param max_new_tokens: 最大生成 token 数
        :return: 生成的文本
        """
        pass
