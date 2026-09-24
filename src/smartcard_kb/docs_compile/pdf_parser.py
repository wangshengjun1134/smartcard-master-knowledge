"""PDF 解析模块 - 基于 Docling 的 PDF 结构化内容提取并保存到数据库"""

import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, HeadingHierarchyOptions
from docling.datamodel.base_models import InputFormat, DocItemLabel

from .database import init_database, insert_document_items


class PDFParser:
    """基于 Docling 的 PDF 解析器"""

    def __init__(self, do_ocr: bool = True):
        """
        初始化解析器

        :param do_ocr: 是否启用 OCR（默认启用）
        """
        self.pipeline_options = PdfPipelineOptions()

        # OCR
        self.pipeline_options.do_ocr = do_ocr

        # 标题层级识别
        self.pipeline_options.heading_hierarchy_options = (
            HeadingHierarchyOptions(enabled=True)
        )

        # 生成 PictureItem 对应的图片
        self.pipeline_options.generate_picture_images = True

        # 图片缩放倍数
        self.pipeline_options.images_scale = 2.0

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self.pipeline_options
                )
            }
        )

    def parse_pdf(
        self,
        pdf_path: str,
        document_id: str,
        page_range: Optional[tuple] = None,
        output_dir: str = "output/pictures"
    ) -> List[Dict[str, Any]]:
        """
        解析 PDF 文件并将所有 item 保存到数据库

        :param pdf_path: PDF 文件路径
        :param document_id: 文档 ID
        :param page_range: 页码范围 (start, end)，1-based
        :param output_dir: 图片保存目录
        :return: 解析后的 item 列表
        """
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        init_database()

        # 动态构建参数，避免 page_range=None 时触发 docling 校验报错
        kwargs = {}
        if page_range is not None:
            kwargs["page_range"] = page_range

        # 转换 PDF
        result = self.converter.convert(pdf_path, **kwargs)

        # 提取并保存所有 item
        items = self._extract_all_items(result.document, document_id, output_dir)
        insert_document_items(items)

        return items

    def _extract_all_items(
        self,
        doc,
        document_id: str,
        output_dir: str
    ) -> List[Dict[str, Any]]:
        """
        从 Docling 文档对象中提取所有 item（不区分类型）

        :param doc: Docling 转换后的文档对象
        :param document_id: 文档 ID
        :param output_dir: 图片保存目录
        :return: item 列表
        """
        items = []
        order_index = 0
        picture_count = 0

        for item, level in doc.iterate_items():
            order_index += 1

            # 生成唯一 ID
            item_id = str(uuid.uuid4())

            # 获取页面信息
            prov = item.prov[0] if item.prov else None
            page_id = f"{document_id}_page_{prov.page_no}" if prov else f"{document_id}_page_unknown"

            # 获取边界框
            bbox = None
            if prov and prov.bbox:
                bbox = {
                    "l": prov.bbox.l,
                    "t": prov.bbox.t,
                    "r": prov.bbox.r,
                    "b": prov.bbox.b,
                }

            # 处理不同类型的 item
            label = item.label.value if hasattr(item.label, 'value') else str(item.label)
            text = None
            content = None
            metadata = {}

            # 尝试获取原始文本
            try:
                text = item.text if hasattr(item, 'text') else None
            except Exception:
                pass

            # 特殊处理图片类型
            if item.label == DocItemLabel.PICTURE:
                # 保存图片
                try:
                    image = item.get_image(doc)
                    if image is not None:
                        picture_count += 1
                        image_path = Path(output_dir) / f"picture_{picture_count:04d}.png"
                        image.save(str(image_path))
                        text = str(image_path)
                        content = {"image_path": str(image_path)}
                except Exception:
                    pass

                # 获取 caption
                try:
                    caption = item.caption_text(doc) if item.captions else None
                    if caption:
                        metadata["caption"] = caption
                except Exception:
                    pass

            # 特殊处理表格类型
            elif item.label == DocItemLabel.TABLE:
                try:
                    text = item.export_to_markdown()
                except Exception:
                    pass

            # 特殊处理文档索引类型
            elif item.label == DocItemLabel.DOCUMENT_INDEX:
                try:
                    text = item.export_to_markdown()
                except Exception:
                    pass

            # 添加层级信息到 metadata
            metadata["level"] = level

            # 保存原始数据（在所有类型处理后，确保 text 是最终值）
            raw_json = {
                "label": label,
                "text": text,
                "level": level,
            }

            # 构建 item 字典
            item_dict = {
                "id": item_id,
                "document_id": document_id,
                "page_id": page_id,
                "parent_id": None,  # 后续可通过层级关系建立
                "label": label,
                "text": text,
                "order_index": order_index,
                "bbox": bbox,
                "metadata": metadata,
                "content": content,
                "is_rag_enabled": True,  # 默认启用 RAG
                "raw_json": raw_json,
            }

            items.append(item_dict)

        return items
