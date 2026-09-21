"""OpenAI 兼容 API 后端（支持 DashScope 等）"""

import base64
import io
from typing import Any, Dict, List

from PIL import Image

from .base import VLMBackend


class OpenAICompatibleBackend(VLMBackend):
    """OpenAI 兼容的 API 后端"""

    def __init__(self, api_key: str, base_url: str, model: str = "qwen-vl-max", timeout: int = 120):
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
        print(f"OpenAI 兼容后端初始化完成: {base_url}, 模型: {model}")

    def _encode_image(self, image: Image.Image) -> str:
        """将 PIL Image 编码为 base64"""
        buffer = io.BytesIO()
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.save(buffer, format="JPEG", quality=95)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def generate(self, image: Image.Image, messages: List[Dict[str, Any]], max_new_tokens: int = 512) -> str:
        """调用 OpenAI 兼容 API 生成回复"""
        image_base64 = self._encode_image(image)
        data_url = f"data:image/jpeg;base64,{image_base64}"

        # 构建 OpenAI 格式的消息
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
