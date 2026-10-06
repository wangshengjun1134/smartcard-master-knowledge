"""OpenAI Compatible API Backend (supports DashScope, etc.)"""

import base64
import io
from typing import Any, Dict, List

from PIL import Image

from .vlm_base import VLMBackend


class OpenAICompatibleBackend(VLMBackend):
    """OpenAI Compatible API Backend"""

    def __init__(self, api_key: str, base_url: str, model: str = "qwen-vl-max", timeout: int = 120):
        """
        Initialize OpenAI compatible backend
        :param api_key: API Key
        :param base_url: API base URL
        :param model: Model name
        :param timeout: Request timeout (seconds)
        """
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Using OpenAI compatible backend requires openai: pip install openai")

        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self.model = model
        print(f"OpenAI compatible backend initialized: {base_url}, model: {model}")

    def _encode_image(self, image: Image.Image) -> str:
        """Encode PIL Image to base64"""
        buffer = io.BytesIO()
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.save(buffer, format="JPEG", quality=95)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def generate(self, image: Image.Image, messages: List[Dict[str, Any]], max_new_tokens: int = 512) -> str:
        """Call OpenAI compatible API to generate response"""
        image_base64 = self._encode_image(image)
        data_url = f"data:image/jpeg;base64,{image_base64}"

        # Build OpenAI format messages
        api_messages = []
        for msg in messages:
            if msg["role"] == "system":
                api_messages.append({"role": "system", "content": msg["content"]})
            elif msg["role"] == "user":
                content_parts = []
                for item in msg["content"]:
                    if item["type"] == "image":
                        content_parts.append({"type": "image_url", "image_url": {"url": data_url, "detail": "high"}})
                    elif item["type"] == "text":
                        content_parts.append({"type": "text", "text": item["text"]})
                api_messages.append({"role": "user", "content": content_parts})

        response = self.client.chat.completions.create(
            model=self.model, messages=api_messages, max_tokens=max_new_tokens, temperature=0.1
        )

        return response.choices[0].message.content
