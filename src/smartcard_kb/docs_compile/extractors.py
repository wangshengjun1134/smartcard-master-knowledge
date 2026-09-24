"""提取器模块 - 统一的 DocItem 提取器接口和各类具体提取器"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from docling.datamodel.base_models import DocItemLabel


@dataclass
class NormalizedItem:
    """标准化的提取结果"""
    id: str
    label: str
    text: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_rag_enabled: bool = True


class DocItemExtractor(ABC):
    """DocItem 提取器基类"""

    @abstractmethod
    def extract(self, item: Any, context: Dict[str, Any]) -> NormalizedItem:
        """
        提取并规范化 DocItem

        :param item: Docling 的 DocItem 对象
        :param context: 上下文信息，如 document_id, page_id, heading_path 等
        :return: 标准化的 NormalizedItem
        """
        pass


class TextExtractor(DocItemExtractor):
    """文本类型提取器"""

    def extract(self, item: Any, context: Dict[str, Any]) -> NormalizedItem:
        text = item.text if hasattr(item, 'text') else None

        return NormalizedItem(
            id=context.get("item_id", ""),
            label=DocItemLabel.TEXT.value,
            text=text,
            metadata={
                "level": context.get("level"),
                "heading_path": context.get("heading_path", []),
            },
            is_rag_enabled=True,
        )


class TitleExtractor(DocItemExtractor):
    """标题类型提取器"""

    def extract(self, item: Any, context: Dict[str, Any]) -> NormalizedItem:
        text = item.text if hasattr(item, 'text') else None
        level = context.get("level", 1)

        return NormalizedItem(
            id=context.get("item_id", ""),
            label=DocItemLabel.SECTION_HEADER.value,
            text=text,
            metadata={
                "level": level,
                "heading_path": context.get("heading_path", []),
            },
            is_rag_enabled=True,
        )


class TableExtractor(DocItemExtractor):
    """表格类型提取器"""

    def extract(self, item: Any, context: Dict[str, Any]) -> NormalizedItem:
        text = None
        content = None

        try:
            text = item.export_to_markdown()
        except Exception:
            pass

        return NormalizedItem(
            id=context.get("item_id", ""),
            label=DocItemLabel.TABLE.value,
            text=text,
            content=content,
            metadata={
                "level": context.get("level"),
                "heading_path": context.get("heading_path", []),
            },
            is_rag_enabled=True,
        )


class PictureExtractor(DocItemExtractor):
    """图片类型提取器"""

    def extract(self, item: Any, context: Dict[str, Any]) -> NormalizedItem:
        text = None
        content = None
        caption = None

        # 获取 caption
        try:
            doc = context.get("doc")
            if doc and item.captions:
                caption = item.caption_text(doc)
        except Exception:
            pass

        # 保存图片
        try:
            doc = context.get("doc")
            output_dir = context.get("output_dir", "output/pictures")
            picture_count = context.get("picture_count", 0)

            if doc:
                image = item.get_image(doc)
                if image is not None:
                    from pathlib import Path
                    picture_count += 1
                    image_path = Path(output_dir) / f"picture_{picture_count:04d}.png"
                    image.save(str(image_path))
                    text = str(image_path)
                    content = {"image_path": str(image_path)}
        except Exception:
            pass

        metadata = {
            "level": context.get("level"),
            "heading_path": context.get("heading_path", []),
        }
        if caption:
            metadata["caption"] = caption

        return NormalizedItem(
            id=context.get("item_id", ""),
            label=DocItemLabel.PICTURE.value,
            text=text,
            content=content,
            metadata=metadata,
            is_rag_enabled=False,  # 图片默认不启用 RAG
        )


class FormulaExtractor(DocItemExtractor):
    """公式类型提取器"""

    def extract(self, item: Any, context: Dict[str, Any]) -> NormalizedItem:
        text = item.text if hasattr(item, 'text') else None

        return NormalizedItem(
            id=context.get("item_id", ""),
            label=DocItemLabel.FORMULA.value,
            text=text,
            metadata={
                "level": context.get("level"),
                "heading_path": context.get("heading_path", []),
            },
            is_rag_enabled=True,
        )


class DocumentIndexExtractor(DocItemExtractor):
    """文档索引类型提取器"""

    def extract(self, item: Any, context: Dict[str, Any]) -> NormalizedItem:
        text = None

        try:
            text = item.export_to_markdown()
        except Exception:
            pass

        return NormalizedItem(
            id=context.get("item_id", ""),
            label=DocItemLabel.DOCUMENT_INDEX.value,
            text=text,
            metadata={
                "level": context.get("level"),
                "heading_path": context.get("heading_path", []),
            },
            is_rag_enabled=True,
        )


class ListItemExtractor(DocItemExtractor):
    """列表项类型提取器"""

    def extract(self, item: Any, context: Dict[str, Any]) -> NormalizedItem:
        text = item.text if hasattr(item, 'text') else None

        return NormalizedItem(
            id=context.get("item_id", ""),
            label=DocItemLabel.LIST_ITEM.value,
            text=text,
            metadata={
                "level": context.get("level"),
                "heading_path": context.get("heading_path", []),
            },
            is_rag_enabled=True,
        )


# 提取器注册表
extractors = {
    DocItemLabel.TEXT: TextExtractor(),
    DocItemLabel.SECTION_HEADER: TitleExtractor(),
    DocItemLabel.TABLE: TableExtractor(),
    DocItemLabel.PICTURE: PictureExtractor(),
    DocItemLabel.FORMULA: FormulaExtractor(),
    DocItemLabel.DOCUMENT_INDEX: DocumentIndexExtractor(),
    DocItemLabel.LIST_ITEM: ListItemExtractor(),
}


def get_extractor(label: DocItemLabel) -> Optional[DocItemExtractor]:
    """
    根据 DocItemLabel 获取对应的提取器

    :param label: DocItemLabel 类型
    :return: 对应的提取器，如果没有则返回 None
    """
    return extractors.get(label)


def extract_item(item: Any, context: Dict[str, Any]) -> Optional[NormalizedItem]:
    """
    使用对应的提取器处理 DocItem

    :param item: Docling 的 DocItem 对象
    :param context: 上下文信息
    :return: 标准化的 NormalizedItem，如果没有对应的提取器则返回 None
    """
    label = item.label
    extractor = get_extractor(label)

    if extractor is None:
        return None

    return extractor.extract(item, context)
