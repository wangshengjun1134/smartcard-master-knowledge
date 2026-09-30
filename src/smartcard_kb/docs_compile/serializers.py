"""自定义 Docling Serializer - 支持 VLM 描述注入"""

from typing import Any
from docling_core.transforms.serializer.base import (
    BasePictureSerializer,
    SerializationResult,
)
from docling_core.transforms.serializer.markdown import MarkdownDocSerializer
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.types.doc import PictureItem, DoclingDocument


class VLMPictureSerializer(BasePictureSerializer):
    """
    自定义 Picture Serializer，输出 VLM 描述而非空占位符
    
    优先级：
    1. item.vlm_description (直接属性，由注入器设置)
    2. item.metadata.get("vlm_description") (metadata 属性)
    3. 回退到默认行为（空占位符）
    """
    
    def serialize(
        self,
        *,
        item: PictureItem,
        doc_serializer: MarkdownDocSerializer,
        doc: DoclingDocument,
        **kwargs: Any,
    ) -> SerializationResult:
        """
        序列化 PictureItem，输出 VLM 描述
        
        :param item: PictureItem 实例
        :param doc_serializer: 文档序列化器
        :param doc: DoclingDocument 实例
        :return: SerializationResult
        """
        res_parts: list[SerializationResult] = []
        
        # 1. 序列化 caption（保留原有行为）
        cap_res = doc_serializer.serialize_captions(item=item, **kwargs)
        if cap_res.text:
            res_parts.append(cap_res)
        
        # 2. 获取 VLM 描述
        vlm_description = self._get_vlm_description(item)
        
        if vlm_description:
            # 3. 使用 VLM 描述替代空占位符
            vlm_text = f"\n\n[VLM Image Description]:\n{vlm_description}\n"
            vlm_res = SerializationResult(text=vlm_text, spans=[])
            res_parts.append(vlm_res)
        else:
            # 4. 回退：检查是否有图片 URI
            if hasattr(item, 'image') and item.image and item.image.uri:
                uri_res = SerializationResult(
                    text=f"\n\n[Image: {item.image.uri}]\n",
                    spans=[]
                )
                res_parts.append(uri_res)
        
        # 5. 合并结果
        if res_parts:
            combined_text = "\n".join([r.text for r in res_parts if r.text])
            return SerializationResult(text=combined_text, spans=[])
        else:
            return SerializationResult(text="", spans=[])
    
    def _get_vlm_description(self, item: PictureItem) -> str | None:
        """
        获取 VLM 描述，按优先级查找
        
        :param item: PictureItem
        :return: VLM 描述字符串或 None
        """
        # 优先级 1: 直接属性
        if hasattr(item, 'vlm_description') and item.vlm_description:
            return item.vlm_description
        
        # 优先级 2: metadata 字典
        if hasattr(item, 'metadata') and item.metadata:
            return item.metadata.get('vlm_description')
        
        return None


class CustomChunkingDocSerializer(ChunkingDocSerializer):
    """
    自定义 ChunkingDocSerializer，替换 picture_serializer
    """
    picture_serializer: BasePictureSerializer = VLMPictureSerializer()


class CustomChunkingSerializerProvider(ChunkingSerializerProvider):
    """
    自定义 SerializerProvider，返回 CustomChunkingDocSerializer
    """
    
    def get_serializer(self, doc: DoclingDocument) -> CustomChunkingDocSerializer:
        """
        获取自定义序列化器
        
        :param doc: DoclingDocument
        :return: CustomChunkingDocSerializer 实例
        """
        return CustomChunkingDocSerializer(doc=doc)
