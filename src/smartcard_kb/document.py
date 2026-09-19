"""文档处理模块 - 基于 Docling 的 PDF 结构化内容提取"""

from pathlib import Path
from typing import List, Dict, Any, Optional

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, HeadingHierarchyOptions
from docling.datamodel.base_models import InputFormat, DocItemLabel


class DoclingPDFProcessor:
    """基于 Docling 的 PDF 结构化内容提取器"""

    def __init__(self, do_ocr: bool = True):
        """
        初始化处理器
        :param do_ocr: 是否启用 OCR（默认启用）
        """
        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = do_ocr
        self.pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(enabled=True)

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=self.pipeline_options)
            }
        )

    def extract_structured_content(self, doc) -> List[Dict[str, Any]]:
        """
        从 Docling 文档对象中提取结构化内容
        :param doc: Docling 转换后的文档对象
        :return: 结构化内容列表
        """
        heading_stack = []
        results = []

        for item, level in doc.iterate_items():
            # -------------------------
            # Heading
            # -------------------------
            if item.label == DocItemLabel.SECTION_HEADER:
                heading_stack = heading_stack[:level - 1]
                heading_stack.append(item.text.strip())
                continue

            # -------------------------
            # Text
            # -------------------------
            if item.label == DocItemLabel.TEXT:
                item_type = "text"
                text = item.text

            # -------------------------
            # Table
            # -------------------------
            elif item.label == DocItemLabel.TABLE:
                item_type = "table"
                text = item.export_to_markdown()

            else:
                continue

            # -------------------------
            # Provenance
            # -------------------------
            prov = item.prov[0] if item.prov else None

            results.append({
                "type": item_type,
                "text": text,
                "heading_path": heading_stack.copy(),
                "page": prov.page_no if prov else None,
                "bbox": {
                    "l": prov.bbox.l,
                    "t": prov.bbox.t,
                    "r": prov.bbox.r,
                    "b": prov.bbox.b,
                } if prov and prov.bbox else None,
            })

        return results

    def process_pdf(self, pdf_path: str, page_range: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        处理 PDF 文件并返回结构化内容
        :param pdf_path: PDF 文件路径
        :param page_range: 页码范围 (start, end)，1-based
        :return: 结构化内容列表
        """
        result = self.converter.convert(pdf_path, page_range=page_range)
        return self.extract_structured_content(result.document)
