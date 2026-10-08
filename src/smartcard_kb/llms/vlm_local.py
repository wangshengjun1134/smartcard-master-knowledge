"""Local Qwen3-VL Model Backend"""

from typing import Any, Dict, List, Optional

from PIL import Image

from smartcard_kb.logger import logger

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

        logger.info(f"Loading local VLM model: {model_path}")
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_path, dtype="auto", device_map="auto"
        )
        self.processor = AutoProcessor.from_pretrained(model_path)
        logger.info(f"Local VLM loaded, device: {self.model.device}")

    def generate(self, image: Image.Image, messages: List[Dict[str, Any]], max_new_tokens: int = 2048) -> str:
        """Call local VLM to generate response"""
        # Print request details
        logger.debug("\n" + "="*80)
        logger.debug("📤 Local VLM Request")
        logger.debug("="*80)
        logger.debug(f"Model: {self.model.config._name_or_path}")
        logger.debug(f"Device: {self.device}")
        logger.debug(f"Max tokens: {max_new_tokens}")
        logger.debug(f"\n📋 Messages ({len(messages)} messages):")
        for i, msg in enumerate(messages, 1):
            logger.debug(f"\n  [{i}] Role: {msg['role']}")
            if isinstance(msg["content"], str):
                logger.debug(f"      Content: {msg['content'][:200]}...")
            elif isinstance(msg["content"], list):
                for part in msg["content"]:
                    if part["type"] == "image":
                        logger.debug(f"      [Image] Size: {part['image'].size}, Mode: {part['image'].mode}")
                    elif part["type"] == "text":
                        logger.debug(f"      [Text] {part['text'][:200]}...")
        logger.debug("="*80)

        # Process and generate
        inputs = self.processor.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
        ).to(self.model.device)

        with self.torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]

        content = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        # Print response details
        logger.debug("\n" + "="*80)
        logger.debug("📥 Local VLM Response")
        logger.debug("="*80)
        logger.debug(f"Input tokens: {inputs.input_ids.shape[1]}")
        logger.debug(f"Output tokens: {generated_ids_trimmed[0].shape[0]}")
        logger.debug(f"\n💬 Response Content ({len(content)} chars):")
        logger.debug(f"  {content[:500]}...")
        logger.debug("="*80 + "\n")

        return content
