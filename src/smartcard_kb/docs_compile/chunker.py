"""Chunking 模块 - 负责将文档分块并注入 VLM 描述"""

import uuid
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, HeadingHierarchyOptions
from docling.datamodel.base_models import InputFormat, DocItemLabel
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer

from smartcard_kb.logger import logger
from smartcard_kb.config import settings

from .database import init_database, query_document_items, insert_chunks
from .serializers import CustomChunkingSerializerProvider


class Chunker:
    """负责文档分块，支持 VLM 描述注入"""

    def __init__(
        self,
        do_ocr: bool = True,
        max_tokens: int = 512,
        tokenizer_name: Optional[str] = None,
    ):
        """
        初始化分块器

        :param do_ocr: 是否启用 OCR
        :param max_tokens: 分块最大 token 数
        :param tokenizer_name: tokenizer 路径或 HuggingFace 模型 ID，默认使用本地 embedding_model 路径
        """
        self.do_ocr = do_ocr
        self.max_tokens = max_tokens
        self.tokenizer_name = tokenizer_name or str(settings.embedding_model)

        self.pipeline_options = PdfPipelineOptions()
        self.pipeline_options.do_ocr = do_ocr
        self.pipeline_options.heading_hierarchy_options = HeadingHierarchyOptions(
            enabled=True,
            use_bookmarks=True,
            use_style=True,
            max_level=5,
        )
        self.pipeline_options.generate_picture_images = False  # Chunking 不需要生成图片
        self.pipeline_options.images_scale = 2.0

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=self.pipeline_options
                ),
                InputFormat.DOCX: WordFormatOption(),
            }
        )

        # HybridChunker - 使用自定义 serializer provider
        tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.chunker = HybridChunker(
            tokenizer=HuggingFaceTokenizer(
                tokenizer=tokenizer,
                max_tokens=max_tokens,
            ),
            merge_peers=True,
            serializer_provider=CustomChunkingSerializerProvider(),
        )

    def generate_chunks(
        self,
        pdf_path: str,
        document_id: str,
        page_range: Optional[tuple] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        生成文档分块，并注入 VLM 描述

        :param pdf_path: PDF 文件路径
        :param document_id: 文档 ID
        :param page_range: 页码范围 (start, end)，1-based
        :return: 包含 chunks 的字典
        """
        init_database()

        # 1. 重新解析 PDF 获取 DoclingDocument
        t0 = time.time()
        kwargs = {}
        if page_range is not None:
            kwargs["page_range"] = page_range
        
        result = self.converter.convert(pdf_path, **kwargs)
        t1 = time.time()

        # 2. 从 DB 加载所有 items（用于关联）和 VLM 描述
        all_items = query_document_items(document_id=document_id)
        picture_items = [item for item in all_items if item.get("label") == "picture"]
        vlm_map = self._build_vlm_map(picture_items)

        # 3. 设置全局 VLM 映射（供 Serializer 读取）
        from .serializers import VLMPictureSerializer
        VLMPictureSerializer.vlm_map = vlm_map
        t2 = time.time()

        # 4. 执行分块
        chunks = self._extract_chunks(result.document, document_id, all_items)
        insert_chunks(chunks)
        t3 = time.time()

        logger.debug(f"convert: {t1-t0:.2f}s, inject: {t2-t1:.2f}s, chunks: {t3-t2:.2f}s")

        return {"chunks": chunks}

    def _build_vlm_map(self, picture_items: List[Dict[str, Any]]) -> Dict[str, str]:
        """构建 self_ref -> vlm_description 映射"""
        vlm_map = {}
        for item in picture_items:
            metadata = item.get("metadata") or {}
            self_ref = item.get("self_ref")
            vlm_desc = metadata.get("vlm_description")

            if self_ref and vlm_desc:
                vlm_map[self_ref] = vlm_desc

        return vlm_map

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
        :param items: 已提取的 item 列表（用于关联）
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
                tokenizer_obj = self.chunker.tokenizer.tokenizer
                encoded = tokenizer_obj.encode(chunk.text)
                token_count = len(encoded)
            except Exception as e:
                logger.warning(f"Warning: Failed to compute token count: {e}")
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
                "chunk_token_limit": self.max_tokens,
                "tokenizer": self.tokenizer_name,
            })

        return chunks
