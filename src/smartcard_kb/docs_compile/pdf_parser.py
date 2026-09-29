"""PDF 解析模块 - 基于 Docling 的 PDF 结构化内容提取并保存到数据库"""

import uuid
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, HeadingHierarchyOptions
from docling.datamodel.base_models import InputFormat, DocItemLabel
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer
from PIL import Image

from .database import init_database, insert_document_items, insert_chunks
from ..llms.base import VLMBackend
from ..llms.openai import OpenAICompatibleBackend
from ..llms.local import LocalQwenVLMBackend


class PDFParser:
    """基于 Docling 的 PDF 解析器"""

    def __init__(
        self,
        do_ocr: bool = True,
        max_tokens: int = 512,
        tokenizer_name: str = "BAAI/bge-m3",
        vlm_backend: Optional[VLMBackend] = None,
        vlm_config: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化解析器

        :param do_ocr: 是否启用 OCR（默认启用）
        :param max_tokens: 分块最大 token 数
        :param tokenizer_name: tokenizer 名称（与 embedding 模型保持一致）
        :param vlm_backend: VLM 后端实例（如果提供，则忽略 vlm_config）
        :param vlm_config: VLM 配置字典，支持以下键：
            - backend_type: "openai"（默认）或 "local"
            - openai_api_key: OpenAI API Key
            - openai_base_url: OpenAI API 基础 URL
            - openai_model: 模型名称（默认 "qwen-vl-max"）
            - local_model_path: 本地模型路径
        """
        self.pipeline_options = PdfPipelineOptions()

        # OCR
        self.pipeline_options.do_ocr = do_ocr

        # 标题层级识别
        self.pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(
            enabled=True,
            use_bookmarks=True,
            use_style=True,
            max_level=5,
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

        # HybridChunker
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.chunker = HybridChunker(
            tokenizer=HuggingFaceTokenizer(
                tokenizer=tokenizer,
                max_tokens=max_tokens,
            ),
            merge_peers=True,  # 合并同一标题下的相邻小项
        )

        # VLM 后端初始化
        self.vlm_backend = vlm_backend
        if self.vlm_backend is None and vlm_config is not None:
            self.vlm_backend = self._create_vlm_backend(vlm_config)

    def _create_vlm_backend(self, config: Dict[str, Any]) -> VLMBackend:
        """
        根据配置创建 VLM 后端

        :param config: VLM 配置字典
        :return: VLM 后端实例
        """
        backend_type = config.get("backend_type", "openai")

        if backend_type == "openai":
            return OpenAICompatibleBackend(
                api_key=config.get("openai_api_key", ""),
                base_url=config.get("openai_base_url", ""),
                model=config.get("openai_model", "qwen-vl-max"),
            )
        elif backend_type == "local":
            return LocalQwenVLMBackend(
                model_path=config.get("local_model_path", ""),
            )
        else:
            raise ValueError(f"不支持的 VLM 后端类型: {backend_type}")

    def parse_pdf(
        self,
        pdf_path: str,
        document_id: str,
        page_range: Optional[tuple] = None,
        output_dir: str = "output/pictures"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        解析 PDF 文件并将所有 item 和 chunk 保存到数据库

        :param pdf_path: PDF 文件路径
        :param document_id: 文档 ID
        :param page_range: 页码范围 (start, end)，1-based
        :param output_dir: 图片保存目录
        :return: 包含 items 和 chunks 的字典
        """
        # 确保输出目录存在
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        init_database()

        # 动态构建参数，避免 page_range=None 时触发 docling 校验报错
        kwargs = {}
        if page_range is not None:
            kwargs["page_range"] = page_range

        # 转换 PDF（只调用一次）
        t0 = time.time()
        result = self.converter.convert(pdf_path, **kwargs)
        t1 = time.time()

        # 第一层：逐项提取
        items = self._extract_all_items(result.document, document_id, output_dir)
        insert_document_items(items)
        t2 = time.time()

        # 第二层：语义分块
        chunks = self._extract_chunks(result.document, document_id, items)
        insert_chunks(chunks)
        t3 = time.time()

        print(f"convert: {t1-t0:.2f}s, items: {t2-t1:.2f}s, chunks: {t3-t2:.2f}s")

        return {"items": items, "chunks": chunks}

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

                        # 使用 VLM 生成图片描述
                        if self.vlm_backend is not None:
                            try:
                                vlm_description = self._generate_vlm_description(
                                    image, item, doc
                                )
                                if vlm_description:
                                    metadata["vlm_description"] = vlm_description
                            except Exception as e:
                                print(f"Warning: VLM 描述生成失败: {e}")
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
                "self_ref": item.self_ref,  # 新增：用于与 chunks 关联
            }

            items.append(item_dict)

        return items

    def _generate_vlm_description(
        self,
        image: Image.Image,
        item,
        doc,
        prompt: str = "请详细描述这张图片的内容，包括所有技术细节、图表数据、流程步骤等。如果是流程图或架构图，请说明各个组件之间的关系。",
        max_new_tokens: int = 512,
    ) -> Optional[str]:
        """
        使用 VLM 生成图片描述

        :param image: PIL Image 对象
        :param item: Docling PictureItem
        :param doc: DoclingDocument
        :param prompt: 提示词
        :param max_new_tokens: 最大生成 token 数
        :return: 图片描述文本
        """
        if self.vlm_backend is None:
            return None

        # 构建消息（OpenAI 格式）
        messages = [
            {
                "role": "system",
                "content": "你是一个专业的技术文档分析助手，擅长描述和解释技术图表、流程图、架构图等内容。",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            },
        ]

        try:
            description = self.vlm_backend.generate(
                image=image,
                messages=messages,
                max_new_tokens=max_new_tokens,
            )
            return description.strip()
        except Exception as e:
            print(f"Warning: VLM 生成失败: {e}")
            return None

    def _extract_chunks(
        self,
        doc,
        document_id: str,
        items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        使用 HybridChunker 对文档进行语义分块

        :param doc: Docling 转换后的文档对象
        :param document_id: 文档 ID
        :param items: 已提取的 item 列表
        :return: chunk 列表
        """
        # self_ref → item_id 映射
        ref_to_id = {
            it["self_ref"]: it["id"]
            for it in items
            if it.get("self_ref")
        }

        chunks = []
        for idx, chunk in enumerate(self.chunker.chunk(doc)):
            if not chunk.text.strip():
                continue

            chunk_id = str(uuid.uuid4())

            # 提取标题信息
            headings = list(chunk.meta.headings or [])
            heading_path = " > ".join(headings)

            # 提取关联的 doc_items
            doc_items = list(chunk.meta.doc_items or [])
            linked_refs = [di.self_ref for di in doc_items if hasattr(di, "self_ref")]
            linked_item_ids = [ref_to_id[r] for r in linked_refs if r in ref_to_id]

            # 提取页码信息
            page_nos = set()
            for di in doc_items:
                prov = getattr(di, "prov", None) or []
                for p in prov:
                    if getattr(p, "page_no", None) is not None:
                        page_nos.add(p.page_no)

            # 计算 token 数
            try:
                # HuggingFaceTokenizer 内部有 tokenizer 属性
                tokenizer_obj = self.chunker.tokenizer.tokenizer
                encoded = tokenizer_obj.encode(chunk.text)
                token_count = len(encoded)
            except Exception as e:
                print(f"Warning: Failed to compute token count: {e}")
                token_count = None

            chunks.append({
                "id": chunk_id,
                "document_id": document_id,
                "chunk_index": idx,
                "text": chunk.text,
                "headings": headings,
                "heading_path": heading_path,
                "linked_item_ids": linked_item_ids,
                "page_nos": sorted(page_nos),
                "token_count": token_count,
                "is_rag_enabled": True,
            })

        return chunks
