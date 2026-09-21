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

    def extract_structured_content(self, doc, output_dir: str = "output/pictures") -> List[Dict[str, Any]]:
        """
        从 Docling 文档对象中提取结构化内容
        :param doc: Docling 转换后的文档对象
        :param output_dir: 图片保存目录
        :return: 结构化内容列表
        """
        heading_stack = []
        results = []
        picture_count = 0

        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)

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
                caption = None

            # List item
            elif item.label == DocItemLabel.LIST_ITEM:
                item_type = "text"
                text = item.text
                caption = None

            # -------------------------
            # Table
            # -------------------------
            elif item.label == DocItemLabel.TABLE:
                item_type = "table"
                text = item.export_to_markdown()
                caption = None

            # -------------------------
            # Index
            # -------------------------
            elif item.label == DocItemLabel.DOCUMENT_INDEX:
                item_type = "document_index"
                text = item.export_to_markdown()
                caption = None

            # -------------------------
            # Picture
            # -------------------------
            elif item.label == DocItemLabel.PICTURE:
                item_type = "picture"
                text = None
                # 获取 caption（注意是复数 captions）
                caption = item.caption_text(doc) if item.captions else None

                # 保存图片
                image = item.get_image(doc)
                if image is not None:
                    picture_count += 1
                    image_path = Path(output_dir) / f"picture_{picture_count:04d}.png"
                    image.save(str(image_path))
                    text = str(image_path)  # 用图片路径替换 text

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
                "caption": caption,
                "bbox": {
                    "l": prov.bbox.l,
                    "t": prov.bbox.t,
                    "r": prov.bbox.r,
                    "b": prov.bbox.b,
                } if prov and prov.bbox else None,
            })

        return results

    def process_pdf(self, pdf_path: str, page_range: Optional[tuple] = None, output_dir: str = "output/pictures") -> List[Dict[str, Any]]:
        """
        处理 PDF 文件并返回结构化内容
        :param pdf_path: PDF 文件路径
        :param page_range: 页码范围 (start, end)，1-based
        :param output_dir: 图片保存目录
        :return: 结构化内容列表
        """
        # 动态构建参数，避免 page_range=None 时触发 docling 校验报错
        kwargs = {}
        if page_range is not None:
            kwargs["page_range"] = page_range

        result = self.converter.convert(pdf_path, **kwargs)
        return self.extract_structured_content(result.document, output_dir)
