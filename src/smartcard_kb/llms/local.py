"""本地 Qwen3-VL 模型后端"""

from typing import Any, Dict, List, Optional

from PIL import Image

from .base import VLMBackend


class LocalQwenVLMBackend(VLMBackend):
    """本地 Qwen3-VL 模型后端"""

    def __init__(self, model_path: str, device: Optional[str] = None):
        """
        初始化本地 VLM
        :param model_path: 本地模型路径
        :param device: 运行设备（cuda/cpu）
        """
        try:
            import torch
            from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
        except ImportError:
            raise ImportError("使用本地 VLM 需要安装 transformers 和 torch: pip install transformers torch")

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.torch = torch

        print(f"正在加载本地 VLM 模型：{model_path}")
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_path, dtype="auto", device_map="auto"
        )
        self.processor = AutoProcessor.from_pretrained(model_path)
        print(f"本地 VLM 加载完成，设备：{self.model.device}")

    def generate(self, image: Image.Image, messages: List[Dict[str, Any]], max_new_tokens: int = 512) -> str:
        """调用本地 VLM 生成回复"""
        inputs = self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
        ).to(self.model.device)

        with self.torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        return self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
