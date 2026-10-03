"""VLM 服务模块 - 负责为图片 Item 生成 VLM 描述"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from PIL import Image

from .database import query_document_items, get_connection
from ..llms.vlm_base import VLMBackend
from ..llms.vlm_openai import OpenAICompatibleBackend
from ..llms.vlm_local import LocalQwenVLMBackend


class VLMService:
    """负责为图片 Item 生成 VLM 描述"""

    def __init__(self, vlm_backend: VLMBackend):
        """
        初始化 VLM 服务

        :param vlm_backend: VLM 后端实例（必需）
        """
        self.vlm_backend = vlm_backend

    @staticmethod
    def create_backend(backend_type: str, **kwargs) -> VLMBackend:
        """
        创建 VLM 后端

        :param backend_type: 后端类型 (openai/local)
        :param kwargs: 后端配置参数
        :return: VLM 后端实例
        """
        if backend_type == "openai":
            return OpenAICompatibleBackend(
                api_key=kwargs["api_key"],
                base_url=kwargs["base_url"],
                model=kwargs["model"],
            )
        elif backend_type == "local":
            return LocalQwenVLMBackend(
                model_path=kwargs["model_path"],
            )
        else:
            raise ValueError(f"不支持的 VLM 后端类型: {backend_type}")

    def generate_vlm_descriptions(
        self,
        document_id: str,
        output_dir: str,
        prompt: str = "Please describe this image in detail, including all technical details, chart data, process steps, etc. If it is a flowchart or architecture diagram, please explain the relationships between the components. Respond in English.",
        max_new_tokens: int = 512,
    ) -> Dict[str, Any]:
        """
        为指定文档的所有图片 Item 生成 VLM 描述

        :param document_id: 文档 ID
        :param output_dir: 图片保存目录
        :param prompt: VLM 提示词
        :param max_new_tokens: 最大生成 token 数
        :return: 处理结果统计
        """
        items = query_document_items(document_id=document_id, label="picture")

        processed_count = 0
        failed_items = []

        for item in items:
            item_id = item.get("id")
            metadata = item.get("metadata") or {}

            # 跳过已经生成过描述的
            if metadata.get("vlm_description"):
                processed_count += 1
                continue

            # 获取图片路径
            content = item.get("content") or {}
            image_path_str = content.get("image_path") or item.get("text")
            if not image_path_str:
                print(f"Warning: Item {item_id} 没有图片路径，跳过")
                failed_items.append(item_id)
                continue

            # 使用完整路径（数据库已包含 document_id 子目录）
            image_path = Path(image_path_str)
            if not image_path.is_absolute():
                # 如果是相对路径，基于项目根目录解析
                project_root = Path(__file__).resolve().parent.parent.parent.parent
                image_path = project_root / image_path
            
            if not image_path.exists():
                print(f"Warning: 图片不存在 {image_path}，跳过")
                failed_items.append(item_id)
                continue

            try:
                image = Image.open(image_path).convert("RGB")
                vlm_desc = self._generate_vlm_description(image, prompt, max_new_tokens)

                if vlm_desc:
                    self._update_item_vlm_description(item_id, vlm_desc)
                    processed_count += 1
                else:
                    failed_items.append(item_id)
            except Exception as e:
                print(f"Error: Item {item_id} VLM 生成失败: {e}")
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
    ) -> Optional[str]:
        """调用 VLM 生成描述"""
        messages = [
            {"role": "system", "content": "You are a professional technical document analysis assistant, skilled at describing and explaining technical charts, flowcharts, architecture diagrams, etc. Always respond in English."},
            {"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]},
        ]
        try:
            return self.vlm_backend.generate(image=image, messages=messages, max_new_tokens=max_new_tokens).strip()
        except Exception as e:
            print(f"Warning: VLM 生成失败: {e}")
            return None

    def _update_item_vlm_description(self, item_id: str, vlm_description: str) -> None:
        """更新 item 的 vlm_description"""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE doc_items
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{vlm_description}',
                %s::jsonb
            ),
            updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (json.dumps(vlm_description), item_id))
        conn.commit()
        cursor.close()
        conn.close()
