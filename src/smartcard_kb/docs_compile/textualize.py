"""文本化模块 - 将 document_item 转换为可用于 RAG 的文本格式"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path

from PIL import Image

from .database import query_items_needing_textualization, update_item_textualization


class Textualizer(ABC):
    """文本化器基类"""

    @abstractmethod
    def textualize(self, item: Dict[str, Any]) -> str:
        """
        将 item 转换为文本

        :param item: document_item 记录字典
        :return: 文本化后的内容
        """
        pass


class TextTextualizer(Textualizer):
    """文本类型文本化器 - 直接返回 text 字段"""

    def textualize(self, item: Dict[str, Any]) -> str:
        text = item.get("text", "")
        if not text:
            return ""

        # 添加标题路径信息（如果有）
        metadata = item.get("metadata", {})
        heading_path = metadata.get("heading_path", [])
        if heading_path:
            path_str = " > ".join(heading_path)
            return f"[{path_str}] {text}"

        return text


class TableTextualizer(Textualizer):
    """表格类型文本化器 - 返回 Markdown 格式"""

    def textualize(self, item: Dict[str, Any]) -> str:
        text = item.get("text", "")
        if not text:
            return ""

        # 表格已经是 Markdown 格式，添加上下文信息
        metadata = item.get("metadata", {})
        heading_path = metadata.get("heading_path", [])

        result = []
        if heading_path:
            result.append(f"表格位置: {' > '.join(heading_path)}")
        result.append(text)

        return "\n".join(result)


class PictureTextualizer(Textualizer):
    """图片类型文本化器 - 调用 VLM 生成描述"""

    def __init__(self, vlm_backend=None, prompt: str = None):
        """
        初始化图片文本化器

        :param vlm_backend: VLM 后端实例（OpenAICompatibleBackend 或 LocalVLMBackend）
        :param prompt: 图片描述提示词
        """
        self.vlm_backend = vlm_backend
        self.prompt = prompt or "请详细描述这张图片的内容，包括所有可见的文本、图表、流程图等关键信息。"

    def textualize(self, item: Dict[str, Any]) -> str:
        """使用 VLM 生成图片描述"""
        if not self.vlm_backend:
            # 如果没有 VLM 后端，返回占位符
            return self._get_placeholder(item)

        # 获取图片路径
        content = item.get("content", {})
        image_path = content.get("image_path") if content else None

        if not image_path or not Path(image_path).exists():
            return "[图片不可用]"

        try:
            # 加载图片
            image = Image.open(image_path).convert("RGB")

            # 构建消息
            messages = [
                {"role": "system", "content": "你是一个专业的文档分析助手，擅长描述和理解文档中的图片内容。"},
                {"role": "user", "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": self.prompt}
                ]}
            ]

            # 调用 VLM
            description = self.vlm_backend.generate(
                image=image,
                messages=messages,
                max_new_tokens=1024
            )

            return description

        except Exception as e:
            return f"[图片描述生成失败: {str(e)}]"

    def _get_placeholder(self, item: Dict[str, Any]) -> str:
        """获取占位符文本"""
        metadata = item.get("metadata", {})
        caption = metadata.get("caption", "")

        if caption:
            return f"[图片] {caption}"
        return "[图片]"


class FormulaTextualizer(Textualizer):
    """公式类型文本化器 - 返回 LaTeX/文本格式"""

    def textualize(self, item: Dict[str, Any]) -> str:
        text = item.get("text", "")
        if not text:
            return ""

        return f"[公式] {text}"


class ListTextualizer(Textualizer):
    """列表项类型文本化器 - 返回 Markdown/文本格式"""

    def textualize(self, item: Dict[str, Any]) -> str:
        text = item.get("text", "")
        if not text:
            return ""

        # 添加列表项标记
        return f"- {text}"


class ReferenceTextualizer(Textualizer):
    """引用/索引类型文本化器 - 返回文本格式"""

    def textualize(self, item: Dict[str, Any]) -> str:
        text = item.get("text", "")
        if not text:
            return ""

        return text


class SectionHeaderTextualizer(Textualizer):
    """标题类型文本化器 - 返回带层级的标题文本"""

    def textualize(self, item: Dict[str, Any]) -> str:
        text = item.get("text", "")
        if not text:
            return ""

        metadata = item.get("metadata", {})
        level = metadata.get("level", 1)

        # 使用 # 标记标题层级
        prefix = "#" * level
        return f"{prefix} {text}"


class DocumentIndexTextualizer(Textualizer):
    """文档索引类型文本化器 - 返回 Markdown 格式"""

    def textualize(self, item: Dict[str, Any]) -> str:
        text = item.get("text", "")
        if not text:
            return ""

        return f"[文档索引]\n{text}"


# 文本化器注册表
textualizers = {
    "text": TextTextualizer(),
    "section_header": SectionHeaderTextualizer(),
    "table": TableTextualizer(),
    "picture": None,  # 需要初始化时传入 VLM 后端
    "formula": FormulaTextualizer(),
    "list_item": ListTextualizer(),
    "document_index": DocumentIndexTextualizer(),
}


def get_textualizer(label: str, vlm_backend=None) -> Optional[Textualizer]:
    """
    根据 label 获取对应的文本化器

    :param label: DocItemLabel 类型
    :param vlm_backend: VLM 后端实例（用于图片类型）
    :return: 对应的文本化器，如果没有则返回 None
    """
    textualizer = textualizers.get(label)

    if textualizer is None and label == "picture":
        # 动态创建图片文本化器
        textualizer = PictureTextualizer(vlm_backend=vlm_backend)

    return textualizer


def textualize_item(item: Dict[str, Any], vlm_backend=None) -> Optional[str]:
    """
    文本化单个 item

    :param item: document_item 记录字典
    :param vlm_backend: VLM 后端实例
    :return: 文本化后的内容，如果没有对应的文本化器则返回 None
    """
    label = item.get("label", "")
    textualizer = get_textualizer(label, vlm_backend)

    if textualizer is None:
        return None

    return textualizer.textualize(item)


def textualize_all_items(
    document_id: Optional[str] = None,
    label: Optional[str] = None,
    vlm_backend=None,
    batch_size: int = 50,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    文本化所有待处理的 item

    :param document_id: 文档 ID（可选，None 表示处理所有文档）
    :param label: 类型（可选，None 表示处理所有类型）
    :param vlm_backend: VLM 后端实例
    :param batch_size: 每批处理的 item 数量
    :param dry_run: 是否只查询不更新（用于测试）
    :return: 统计信息 {"total": 总数, "success": 成功数, "failed": 失败数}
    """
    stats = {"total": 0, "success": 0, "failed": 0}

    # 先查询所有待处理的 item，避免无限循环
    all_items = query_items_needing_textualization(
        document_id=document_id,
        label=label,
        limit=10000  # 设置一个较大的上限
    )

    if not all_items:
        print("✅ 没有待文本化的记录")
        return stats

    stats["total"] = len(all_items)
    print(f"\n📊 共找到 {len(all_items)} 条待文本化的记录")

    # 按类型分组统计
    type_stats = {}
    for item in all_items:
        item_label = item.get("label", "unknown")
        type_stats[item_label] = type_stats.get(item_label, 0) + 1

    print("\n📋 待文本化记录类型分布:")
    for lbl, count in sorted(type_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {lbl}: {count}")

    print("\n" + "=" * 60)
    print("🔄 开始文本化处理:")
    print("=" * 60)

    for i, item in enumerate(all_items, 1):
        item_id = item["id"]
        item_label = item.get("label", "")

        try:
            # 文本化
            result = textualize_item(item, vlm_backend)

            if result is not None:
                if not dry_run:
                    # 更新数据库
                    update_item_textualization(item_id, result)
                stats["success"] += 1
                if i % 10 == 0 or i <= 5:  # 每 10 条打印一次，或前 5 条
                    print(f"✅ [{i}/{len(all_items)}] [{item_label}] {item_id[:8]}... - {len(result)} chars")
            else:
                stats["failed"] += 1
                print(f"⚠️  [{i}/{len(all_items)}] [{item_label}] {item_id[:8]}... - 无对应的文本化器")

        except Exception as e:
            stats["failed"] += 1
            print(f"❌ [{i}/{len(all_items)}] [{item_label}] {item_id[:8]}... - Error: {str(e)}")

    return stats


def create_vlm_backend(
    backend_type: str = "openai",
    api_key: str = None,
    base_url: str = None,
    model: str = "qwen-vl-max",
    model_path: str = None
):
    """
    创建 VLM 后端实例

    :param backend_type: 后端类型 ("openai" 或 "local")
    :param api_key: API Key（openai 类型需要）
    :param base_url: API 基础 URL（openai 类型需要）
    :param model: 模型名称
    :param model_path: 本地模型路径（local 类型需要）
    :return: VLM 后端实例
    """
    if backend_type == "openai":
        from smartcard_kb.llms.openai import OpenAICompatibleBackend
        return OpenAICompatibleBackend(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
    elif backend_type == "local":
        from smartcard_kb.llms.local import LocalVLMBackend
        return LocalVLMBackend(model_path=model_path)
    else:
        raise ValueError(f"不支持的后端类型: {backend_type}")
