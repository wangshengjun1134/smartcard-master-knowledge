"""PDF/DOCX 解析模块 - 基于 Docling 的结构化内容提取并保存到数据库"""

import os
import uuid
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, HeadingHierarchyOptions
from docling.datamodel.base_models import InputFormat, DocItemLabel

from smartcard_kb.logger import logger

from .database import init_database, insert_document_items


class PDFParser:
    """基于 Docling 的 PDF/DOCX 解析器 - 负责提取 Items 并保存"""

    def __init__(
        self,
        do_ocr: bool = True,
    ):
        """
        初始化解析器

        :param do_ocr: 是否启用 OCR（默认启用）
        """
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = do_ocr
        self.pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(
            enabled=True,
            use_bookmarks=True,
            use_style=True,
            max_level=5,
        )
        self.pipeline_options.generate_picture_images = True
        self.pipeline_options.images_scale = 2.0

        # 使用本地模型路径（避免运行时下载）
        artifacts_path = os.environ.get("DOCLING_MODELS_PATH")
        if artifacts_path:
            self.pipeline_options.artifacts_path = artifacts_path

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self.pipeline_options
                ),
                InputFormat.DOCX: WordFormatOption(),
            }
        )

    def parse_pdf(
        self,
        pdf_path: str,
        document_id: str,
        page_range: Optional[tuple] = None,
        output_dir: str = "output/pictures"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        解析 PDF 文件并将所有 item 保存到数据库

        :param pdf_path: PDF 文件路径
        :param document_id: 文档 ID
        :param page_range: 页码范围 (start, end)，1-based
        :param output_dir: 图片保存目录
        :return: 包含 items 的字典
        """
        # 确保输出目录存在（每个文档使用独立子目录）
        document_output_dir = Path(output_dir) / document_id
        document_output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        init_database()

        # 动态构建参数，避免 page_range=None 时触发 docling 校验报错
        kwargs = {}
        if page_range is not None:
            kwargs["page_range"] = page_range

        # 转换 PDF
        t0 = time.time()
        result = self.converter.convert(pdf_path, **kwargs)
        t1 = time.time()

        # 提取 items（使用文档独立子目录）
        items = self._extract_all_items(result.document, document_id, str(document_output_dir))
        insert_document_items(items)
        t2 = time.time()

        logger.debug(f"convert: {t1-t0:.2f}s, items: {t2-t1:.2f}s")

        return {"items": items}

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
            item_id = str(uuid.uuid4())

            prov = item.prov[0] if item.prov else None
            page_id = prov.page_no if prov else None

            bbox = None
            if prov and prov.bbox:
                bbox = {"l": prov.bbox.l, "t": prov.bbox.t, "r": prov.bbox.r, "b": prov.bbox.b}

            label = item.label.value if hasattr(item.label, 'value') else str(item.label)
            text = None
            content = None
            metadata = {"level": level}

            try:
                text = item.text if hasattr(item, 'text') else None
            except Exception:
                pass

            if item.label == DocItemLabel.PICTURE:
                image_path = None
                try:
                    image = item.get_image(doc)
                    if image is not None:
                        picture_count += 1
                        image_path = str(Path(output_dir) / f"picture_{picture_count:04d}.png")
                        image.save(image_path)
                except Exception:
                    pass

                try:
                    caption = item.caption_text(doc) if item.captions else None
                    if caption:
                        metadata["caption"] = caption
                except Exception:
                    pass

                # 保存图片路径到 metadata 字段
                if image_path:
                    metadata["image_path"] = image_path

            elif item.label == DocItemLabel.TABLE:
                try:
                    text = item.export_to_markdown()
                except Exception:
                    pass

            elif item.label == DocItemLabel.DOCUMENT_INDEX:
                try:
                    text = item.export_to_markdown()
                except Exception:
                    pass

            raw_json = {"label": label, "text": text, "level": level}

            item_dict = {
                "id": item_id,
                "document_id": document_id,
                "page_id": page_id,
                "parent_id": None,
                "label": label,
                "text": text,
                "order_index": order_index,
                "bbox": bbox,
                "metadata": metadata,
                "content": content,
                "is_rag_enabled": True,
                "raw_json": raw_json,
                "self_ref": item.self_ref,
            }
            items.append(item_dict)

        return items

