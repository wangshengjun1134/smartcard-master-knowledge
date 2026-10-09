"""VLM Service Module - Generates VLM descriptions for image items"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image

from smartcard_kb.logger import logger
from smartcard_kb.config import settings

from .database import query_document_items, get_connection
from ..llms.vlm_base import VLMBackend
from ..llms.vlm_openai import OpenAICompatibleBackend
from ..llms.vlm_local import LocalQwenVLMBackend
from ..prompts.vlm_prompts import build_system_prompt, USER_PROMPT


class VLMService:
    """Service for generating VLM descriptions for image items"""

    def __init__(self, vlm_backend: VLMBackend):
        """
        Initialize VLM service

        :param vlm_backend: VLM backend instance (required)
        """
        self.vlm_backend = vlm_backend

    @staticmethod
    def create_backend(backend_type: str, **kwargs) -> VLMBackend:
        """
        Create VLM backend

        :param backend_type: Backend type (openai/local)
        :param kwargs: Backend configuration parameters
        :return: VLM backend instance
        """
        if backend_type == "openai":
            return OpenAICompatibleBackend(
                api_key=kwargs["api_key"],
                base_url=kwargs["base_url"],
                model=kwargs["model"],
            )
        elif backend_type == "local":
            model_path = kwargs.get("model_path") or str(settings.vlm_local_model_path)
            return LocalQwenVLMBackend(
                model_path=model_path,
            )
        else:
            raise ValueError(f"Unsupported VLM backend type: {backend_type}")

    def generate_vlm_descriptions(
        self,
        document_id: str,
        output_dir: str,
        prompt: str = "Please describe this image in detail, including all technical details, chart data, process steps, etc. If it is a flowchart or architecture diagram, please explain the relationships between the components. Respond in English.",
        max_new_tokens: int = 2048,
        language: str = "en",
        detail_level: str = "detailed",
    ) -> Dict[str, Any]:
        """
        为指定文档的所有图片 Item 生成 VLM 描述

        :param document_id: 文档 ID
        :param output_dir: 图片保存目录
        :param prompt: VLM 提示词
        :param max_new_tokens: 最大生成 token 数
        :param language: 输出语言 (en/zh/ja)，默认英文
        :param detail_level: 描述详细程度 (brief/detailed/comprehensive)
        :return: 处理结果统计
        """
        items = query_document_items(document_id=document_id, label="picture")

        processed_count = 0
        failed_items = []

        for item in items:
            item_id = item.get("id")
            metadata = item.get("metadata") or {}

            # Skip items that already have VLM descriptions (stored in text field)
            if item.get("text"):
                processed_count += 1
                continue

            # Get image path from metadata
            image_path_str = metadata.get("image_path")
            if not image_path_str:
                logger.warning(f"Warning: Item {item_id} has no image_path in metadata, skipping")
                failed_items.append(item_id)
                continue

            # Use full path (database already includes document_id subdirectory)
            image_path = Path(image_path_str)
            if not image_path.is_absolute():
                # If relative path, resolve based on project root
                project_root = Path(__file__).resolve().parent.parent.parent.parent
                image_path = project_root / image_path

            if not image_path.exists():
                logger.warning(f"Warning: Image not found {image_path}, skipping")
                failed_items.append(item_id)
                continue

            try:
                image = Image.open(image_path).convert("RGB")
                logger.info(f"\n🖼️  Processing image for Item {item_id}: {image_path}")
                vlm_desc = self._generate_vlm_description(
                    image, prompt, max_new_tokens, language, detail_level
                )

                if vlm_desc:
                    self._update_item_vlm_description(item_id, vlm_desc)
                    processed_count += 1
                    logger.info(f"✅ Successfully generated VLM description for Item {item_id} ({len(vlm_desc)} chars)")
                else:
                    logger.error(f"❌ Failed to generate VLM description for Item {item_id}")
                    failed_items.append(item_id)
            except Exception as e:
                logger.error(f"❌ Error processing Item {item_id}: {e}")
                failed_items.append(item_id)

        return {
            "document_id": document_id,
            "processed": processed_count,
            "failed": len(failed_items),
            "failed_item_ids": failed_items,
        }

    def _generate_vlm_description(
        self,
        image: Image.Image,
        prompt: str,
        max_new_tokens: int,
        language: str = "en",
        detail_level: str = "detailed",
    ) -> Optional[str]:
        """Call VLM to generate description"""
        system_prompt = build_system_prompt(language)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": USER_PROMPT}]},
        ]
        try:
            return self.vlm_backend.generate(image=image, messages=messages, max_new_tokens=max_new_tokens).strip()
        except Exception as e:
            logger.warning(f"Warning: VLM generation failed: {e}")
            return None

    def _update_item_vlm_description(self, item_id: str, vlm_description: str) -> None:
        """Update item's text field with VLM description"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE doc_items
            SET text = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (vlm_description, item_id))
        conn.commit()
        cursor.close()
        conn.close()
