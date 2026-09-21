"""
LLM/VLM 后端模块

支持多种后端：
- local: 本地模型（Qwen3-VL）
- openai: OpenAI 兼容 API（DashScope 等）
"""

from .base import VLMBackend
from .local import LocalQwenVLMBackend
from .openai import OpenAICompatibleBackend

__all__ = [
    "VLMBackend",
    "LocalQwenVLMBackend",
    "OpenAICompatibleBackend",
]
