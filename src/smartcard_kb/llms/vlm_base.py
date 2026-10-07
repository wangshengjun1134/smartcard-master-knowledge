"""VLM Backend Abstract Base Class"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from PIL import Image


class VLMBackend(ABC):
    """VLM Backend Abstract Base Class"""

    @abstractmethod
    def generate(
        self,
        image: Image.Image,
        messages: List[Dict[str, Any]],
        max_new_tokens: int = 2048
    ) -> str:
        """
        Call VLM to generate response
        :param image: PIL Image object
        :param messages: Message list (OpenAI format)
        :param max_new_tokens: Maximum number of tokens to generate
        :return: Generated text
        """
        pass
