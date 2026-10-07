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

    def generate(self, image: Image.Image, messages: List[Dict[str, Any]], max_new_tokens: int = 2048) -> str:
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

        # Print request details
        print("\n" + "="*80)
        print("📤 VLM API Request")
        print("="*80)
        print(f"Model: {self.model}")
        print(f"Max tokens: {max_new_tokens}")
        print(f"Temperature: 0.1")
        print(f"\n📋 Messages ({len(api_messages)} messages):")
        for i, msg in enumerate(api_messages, 1):
            print(f"\n  [{i}] Role: {msg['role']}")
            if isinstance(msg["content"], str):
                print(f"      Content: {msg['content'][:200]}...")
            elif isinstance(msg["content"], list):
                for part in msg["content"]:
                    if part["type"] == "image_url":
                        print(f"      [Image] URL: {part['image_url']['url'][:100]}... (detail: {part['image_url']['detail']})")
                    elif part["type"] == "text":
                        print(f"      [Text] {part['text'][:200]}...")
        print("="*80)

        # Call API
        response = self.client.chat.completions.create(
            model=self.model, messages=api_messages, max_tokens=max_new_tokens, temperature=0.1
        )

        # Print response details
        print("\n" + "="*80)
        print("📥 VLM API Response")
        print("="*80)
        print(f"Response ID: {response.id}")
        print(f"Model: {response.model}")
        print(f"Created: {response.created}")
        if hasattr(response, 'usage') and response.usage:
            print(f"\n📊 Token Usage:")
            print(f"  Prompt tokens: {response.usage.prompt_tokens}")
            print(f"  Completion tokens: {response.usage.completion_tokens}")
            print(f"  Total tokens: {response.usage.total_tokens}")
        
        content = response.choices[0].message.content
        print(f"\n💬 Response Content ({len(content)} chars):")
        print(f"  {content[:500]}...")
        print("="*80 + "\n")

        return content
