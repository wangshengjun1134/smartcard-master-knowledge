"""Local Qwen3-VL Model Backend"""

from typing import Any, Dict, List, Optional

from PIL import Image

from .vlm_base import VLMBackend


class LocalQwenVLMBackend(VLMBackend):
    """Local Qwen3-VL Model Backend"""

    def __init__(self, model_path: str, device: Optional[str] = None):
        """
        Initialize local VLM
        :param model_path: Local model path
        :param device: Running device (cuda/cpu)
        """
        try:
            import torch
            from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
        except ImportError:
            raise ImportError("Using local VLM requires transformers and torch: pip install transformers torch")

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.torch = torch

        print(f"Loading local VLM model: {model_path}")
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_path, dtype="auto", device_map="auto"
        )
        self.processor = AutoProcessor.from_pretrained(model_path)
        print(f"Local VLM loaded, device: {self.model.device}")

    def generate(self, image: Image.Image, messages: List[Dict[str, Any]], max_new_tokens: int = 512) -> str:
        """Call local VLM to generate response"""
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
