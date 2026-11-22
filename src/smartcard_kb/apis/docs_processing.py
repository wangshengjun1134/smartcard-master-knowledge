"""文档处理 API 接口 - 解析、VLM 增强、分块、Embedding（异步）"""

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field

from smartcard_kb.logger import logger
from smartcard_kb.docs_compile.pdf_parser import PDFParser
from smartcard_kb.docs_compile.vlm_service import VLMService
from smartcard_kb.storage import resolve_file
from smartcard_kb.docs_compile.embedding_service import EmbeddingService
from smartcard_kb.docs_compile.chunker import Chunker
from smartcard_kb.docs_compile.database import update_document_info, get_document_stats, query_documents_by_status, query_document_info
from smartcard_kb.config import settings

router = APIRouter(prefix="/api/docs", tags=["文档处理流程"])

# 全局锁：防止并发执行 parse-all / vlm-all
_parse_all_lock = asyncio.Lock()
_vlm_all_lock = asyncio.Lock()
_chunk_all_lock = asyncio.Lock()
_embedding_all_lock = asyncio.Lock()


# ==================== Pydantic 模型 ====================


class ParseRequest(BaseModel):
    """解析请求（支持 PDF 和 DOCX）"""
    pdf_path: str  # 文件路径（支持 .pdf 和 .docx）
    document_id: str
    page_range: Optional[tuple] = None
    output_dir: str = "output/pictures"
    do_ocr: bool = True


class ParseResponse(BaseModel):
    """解析响应"""
    success: bool
    message: str


class ParseAllRequest(BaseModel):
    """批量解析请求"""
    parallel_count: int = 1  # 并行数量，默认1
    output_dir: str = "output/pictures"
    do_ocr: bool = True


class ParseAllResponse(BaseModel):
    """批量解析响应"""
    success: bool
    message: str
    total: int  # 总文档数
    parallel_count: int  # 并行数量


class VLMRequest(BaseModel):
    """VLM 增强请求"""
    document_id: str
    output_dir: str = "output/pictures"
    backend_type: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    prompt: str = "Please describe this image in detail, including all technical details, chart data, process steps, etc. If it is a flowchart or architecture diagram, please explain the relationships between the components. Respond in English."
    max_new_tokens: int = 2048
    language: str = "en"
    detail_level: str = "detailed"


class VLMResponse(BaseModel):
    """VLM 响应"""
    success: bool
    message: str


class VlmAllRequest(BaseModel):
    """批量 VLM 增强请求"""
    parallel_count: int = 1  # 并行数量，默认1
    output_dir: str = "output/pictures"
    backend_type: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    prompt: str = "Please describe this image in detail, including all technical details, chart data, process steps, etc. If it is a flowchart or architecture diagram, please explain the relationships between the components. Respond in English."
    max_new_tokens: int = 2048
    language: str = "en"
    detail_level: str = "detailed"


class VlmAllResponse(BaseModel):
    """批量 VLM 增强响应"""
    success: bool
    message: str
    total: int  # 总文档数
    parallel_count: int  # 并行数量


class ChunkRequest(BaseModel):
    """分块请求（支持 PDF 和 DOCX）"""
    pdf_path: str  # 文件路径（支持 .pdf 和 .docx）
    document_id: str
    page_range: Optional[tuple] = None
    token_limits: Optional[List[int]] = None  # 默认 [256, 512, 1024]
    tokenizer_name: str = Field(default_factory=lambda: str(settings.embedding_model))
    do_ocr: bool = True


class ChunkResponse(BaseModel):
    """分块响应"""
    success: bool
    message: str


class ChunkAllRequest(BaseModel):
    """批量分块请求"""
    parallel_count: int = 1
    token_limits: Optional[List[int]] = None  # 默认 [256, 512, 1024]
    tokenizer_name: str = Field(default_factory=lambda: str(settings.embedding_model))
    do_ocr: bool = True


class ChunkAllResponse(BaseModel):
    """批量分块响应"""
    success: bool
    message: str
    total: int
    parallel_count: int


class EmbeddingRequest(BaseModel):
    """Embedding 请求"""
    document_id: str
    backend_type: str = "local"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    model_name: Optional[str] = None


class EmbeddingResponse(BaseModel):
    """Embedding 响应"""
    success: bool
    message: str


class EmbeddingAllRequest(BaseModel):
    """批量嵌入请求"""
    parallel_count: int = 1
    backend_type: str = "local"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    model_name: Optional[str] = None


class EmbeddingAllResponse(BaseModel):
    """批量嵌入响应"""
    success: bool
    message: str
    total: int
    parallel_count: int


# ==================== 后台任务函数 ====================


async def _async_parse(
    pdf_path: str,
    document_id: str,
    page_range: Optional[tuple],
    output_dir: str,
    do_ocr: bool,
):
    """异步解析 PDF"""
    try:
        # 保存原始 object_key 用于图片上传路径
        doc_file_path = pdf_path
        # 从 MinIO 解析到本地缓存路径
        pdf_path = resolve_file(pdf_path)

        update_document_info({
            "id": document_id,
            "processing_status": "parsing",
            "processing_started_at": "NOW()",
        })

        # 使用线程池执行同步阻塞操作，避免阻塞事件循环
        parser = PDFParser(do_ocr=do_ocr)
        result = await asyncio.to_thread(
            parser.parse_pdf,
            pdf_path=pdf_path,
            document_id=document_id,
            page_range=page_range,
            output_dir=output_dir,
            doc_file_path=doc_file_path,
        )

        # 更新统计信息
        stats = get_document_stats(document_id)
        type_counts = {
            "item_count": len(result.get("items", [])),
            "text_count": stats.get("text", 0),
            "title_count": stats.get("section_header", 0),
            "table_count": stats.get("table", 0),
            "picture_count": stats.get("picture", 0),
            "formula_count": stats.get("formula", 0),
        }
        update_document_info({
            "id": document_id,
            "processing_status": "parsed",
            **type_counts,
        })
    except Exception as e:
        logger.error(f"Error: Parse failed for {document_id}: {e}")
        update_document_info({
            "id": document_id,
            "processing_status": "parse_failed",
            "processing_error": str(e),
        })


async def _async_parse_all(
    docs: list,
    parallel_count: int,
    output_dir: str,
    do_ocr: bool,
):
    """
    异步批量解析所有 uploaded 状态的文档

    :param docs: 文档列表（从 doc_info 表查询）
    :param parallel_count: 并行数量
    :param output_dir: 图片保存目录
    :param do_ocr: 是否启用 OCR
    """
    async with _parse_all_lock:
        semaphore = asyncio.Semaphore(parallel_count)

        async def _parse_single_doc(doc):
            """解析单个文档"""
            async with semaphore:
                document_id = doc["id"]
                pdf_path = doc.get("file_path")

                if not pdf_path:
                    logger.error(f"Error: file_path not found for document {document_id}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "parse_failed",
                        "processing_error": "file_path not found",
                    })
                    return

                logger.info(f"Starting parse for document {document_id}: {doc.get('file_name', 'unknown')}")
                t0 = time.time()

                try:
                    # 保存原始 object_key 用于图片上传路径
                    doc_file_path = pdf_path
                    # 从 MinIO 解析到本地缓存路径
                    pdf_path = resolve_file(pdf_path)

                    update_document_info({
                        "id": document_id,
                        "processing_status": "parsing",
                        "processing_started_at": "NOW()",
                    })

                    # 使用线程池执行同步阻塞操作
                    parser = PDFParser(do_ocr=do_ocr)
                    result = await asyncio.to_thread(
                        parser.parse_pdf,
                        pdf_path=pdf_path,
                        document_id=document_id,
                        page_range=None,
                        output_dir=output_dir,
                        doc_file_path=doc_file_path,
                    )

                    # 更新统计信息
                    stats = get_document_stats(document_id)
                    type_counts = {
                        "item_count": len(result.get("items", [])),
                        "text_count": stats.get("text", 0),
                        "title_count": stats.get("section_header", 0),
                        "table_count": stats.get("table", 0),
                        "picture_count": stats.get("picture", 0),
                        "formula_count": stats.get("formula", 0),
                    }
                    update_document_info({
                        "id": document_id,
                        "processing_status": "parsed",
                        **type_counts,
                    })
                    logger.info(f"Parse completed for document {document_id} in {time.time() - t0:.2f}s")

                except Exception as e:
                    logger.error(f"Error: Parse failed for document {document_id} in {time.time() - t0:.2f}s: {e}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "parse_failed",
                        "processing_error": str(e),
                    })

        # 并发执行所有文档解析
        tasks = [_parse_single_doc(doc) for doc in docs]
        await asyncio.gather(*tasks)
        logger.info(f"Batch parse completed: {len(docs)} documents processed")


async def _async_vlm(
    document_id: str,
    output_dir: str,
    backend_type: str,
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
    prompt: str,
    max_new_tokens: int,
    language: str = "en",
    detail_level: str = "detailed",
):
    """异步生成 VLM 描述"""
    try:
        update_document_info({
            "id": document_id,
            "processing_status": "vlm_processing",
        })

        # 从参数或环境变量获取配置
        resolved_api_key = api_key or settings.vlm_openai_api_key
        resolved_base_url = base_url or settings.vlm_openai_base_url
        resolved_model = model or settings.vlm_openai_model

        if not resolved_api_key:
            raise ValueError("VLM API Key 未配置")

        # 使用线程池执行同步阻塞操作，避免阻塞事件循环
        backend = VLMService.create_backend(
            backend_type=backend_type,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=resolved_model,
        )
        service = VLMService(vlm_backend=backend)
        result = await asyncio.to_thread(
            service.generate_vlm_descriptions,
            document_id=document_id,
            output_dir=output_dir,
            prompt=prompt,
            max_new_tokens=max_new_tokens,
            language=language,
            detail_level=detail_level,
        )

        update_document_info({
            "id": document_id,
            "processing_status": "vlm_completed",
        })
        logger.info(f"VLM completed for {document_id}: {result}")
    except Exception as e:
        logger.error(f"Error: VLM failed for {document_id}: {e}")
        update_document_info({
            "id": document_id,
            "processing_status": "vlm_failed",
            "processing_error": str(e),
        })


async def _async_vlm_all(
    docs: list,
    parallel_count: int,
    output_dir: str,
    backend_type: str,
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
    prompt: str,
    max_new_tokens: int,
    language: str,
    detail_level: str,
):
    """
    异步批量 VLM 增强所有已解析的文档

    :param docs: 文档列表
    :param parallel_count: 并行数量
    :param output_dir: 图片保存目录
    :param backend_type: VLM 后端类型
    :param api_key: VLM API Key
    :param base_url: VLM API 基础 URL
    :param model: VLM 模型名称
    :param prompt: VLM 提示词
    :param max_new_tokens: 最大生成 token 数
    :param language: 输出语言
    :param detail_level: 描述详细程度
    """
    async with _vlm_all_lock:
        semaphore = asyncio.Semaphore(parallel_count)

        # 从参数或环境变量获取配置
        resolved_api_key = api_key or settings.vlm_openai_api_key
        resolved_base_url = base_url or settings.vlm_openai_base_url
        resolved_model = model or settings.vlm_openai_model

        if not resolved_api_key:
            logger.error("Error: VLM API Key not configured")
            return

        backend = VLMService.create_backend(
            backend_type=backend_type,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=resolved_model,
        )

        async def _vlm_single_doc(doc):
            """VLM 增强单个文档"""
            async with semaphore:
                document_id = doc["id"]

                logger.info(f"Starting VLM for document {document_id}: {doc.get('file_name', 'unknown')}")
                t0 = time.time()

                try:
                    update_document_info({
                        "id": document_id,
                        "processing_status": "vlm_processing",
                    })

                    service = VLMService(vlm_backend=backend)
                    result = await asyncio.to_thread(
                        service.generate_vlm_descriptions,
                        document_id=document_id,
                        output_dir=output_dir,
                        prompt=prompt,
                        max_new_tokens=max_new_tokens,
                        language=language,
                        detail_level=detail_level,
                    )

                    update_document_info({
                        "id": document_id,
                        "processing_status": "vlm_completed",
                    })
                    logger.info(f"VLM completed for document {document_id} in {time.time() - t0:.2f}s: {result}")

                except Exception as e:
                    logger.error(f"Error: VLM failed for document {document_id} in {time.time() - t0:.2f}s: {e}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "vlm_failed",
                        "processing_error": str(e),
                    })

        # 并发执行所有文档 VLM 增强
        tasks = [_vlm_single_doc(doc) for doc in docs]
        await asyncio.gather(*tasks)
        logger.info(f"Batch VLM completed: {len(docs)} documents processed")


async def _async_chunk(
    pdf_path: str,
    document_id: str,
    page_range: Optional[tuple],
    token_limits: Optional[List[int]],
    tokenizer_name: str,
    do_ocr: bool,
):
    """异步分块"""
    try:
        # 从 MinIO 解析到本地缓存路径
        pdf_path = resolve_file(pdf_path)

        update_document_info({
            "id": document_id,
            "processing_status": "chunking",
        })

        # 使用线程池执行同步阻塞操作，避免阻塞事件循环
        chunker = Chunker(
            do_ocr=do_ocr,
            token_limits=token_limits,
            tokenizer_name=tokenizer_name,
        )
        result = await asyncio.to_thread(
            chunker.generate_chunks,
            pdf_path=pdf_path,
            document_id=document_id,
            page_range=page_range,
        )

        update_document_info({
            "id": document_id,
            "processing_status": "chunked",
        })
        logger.info(f"Chunking completed for {document_id}: {len(result.get('chunks', []))} chunks")
    except Exception as e:
        logger.error(f"Error: Chunking failed for {document_id}: {e}")
        update_document_info({
            "id": document_id,
            "processing_status": "chunk_failed",
            "processing_error": str(e),
        })


async def _async_chunk_all(
    docs: list,
    parallel_count: int,
    token_limits: Optional[List[int]],
    tokenizer_name: str,
    do_ocr: bool,
):
    """
    异步批量分块所有 vlm_completed 状态的文档

    :param docs: 文档列表
    :param parallel_count: 并行数量
    :param token_limits: token 限制列表，默认 [256, 512, 1024]
    :param tokenizer_name: tokenizer 名称
    :param do_ocr: 是否启用 OCR
    """
    async with _chunk_all_lock:
        semaphore = asyncio.Semaphore(parallel_count)

        async def _chunk_single_doc(doc):
            """分块单个文档"""
            async with semaphore:
                document_id = doc["id"]
                pdf_path = doc.get("file_path")

                if not pdf_path:
                    logger.error(f"Error: file_path not found for document {document_id}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "chunk_failed",
                        "processing_error": "file_path not found",
                    })
                    return

                logger.info(f"Starting chunk for document {document_id}: {doc.get('file_name', 'unknown')}")
                t0 = time.time()

                try:
                    # 从 MinIO 解析到本地缓存路径
                    pdf_path = resolve_file(pdf_path)

                    update_document_info({
                        "id": document_id,
                        "processing_status": "chunking",
                    })

                    chunker = Chunker(
                        do_ocr=do_ocr,
                        token_limits=token_limits,
                        tokenizer_name=tokenizer_name,
                    )
                    result = await asyncio.to_thread(
                        chunker.generate_chunks,
                        pdf_path=pdf_path,
                        document_id=document_id,
                        page_range=None,
                    )

                    update_document_info({
                        "id": document_id,
                        "processing_status": "chunked",
                    })
                    logger.info(f"Chunk completed for document {document_id} in {time.time() - t0:.2f}s: {len(result.get('chunks', []))} chunks")

                except Exception as e:
                    logger.error(f"Error: Chunk failed for document {document_id} in {time.time() - t0:.2f}s: {e}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "chunk_failed",
                        "processing_error": str(e),
                    })

        # 并发执行所有文档分块
        tasks = [_chunk_single_doc(doc) for doc in docs]
        await asyncio.gather(*tasks)
        logger.info(f"Batch chunk completed: {len(docs)} documents processed")


async def _async_embedding(
    document_id: str,
    backend_type: str,
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
    model_name: Optional[str],
):
    """异步生成 Embedding"""
    try:
        update_document_info({
            "id": document_id,
            "processing_status": "embedding",
        })

        # 从参数或环境变量获取配置
        resolved_api_key = api_key or settings.embedding_openai_api_key
        resolved_base_url = base_url or settings.embedding_openai_base_url
        resolved_model = model or settings.embedding_openai_model
        resolved_model_name = model_name or settings.embedding_model

        if backend_type == "openai" and not resolved_api_key:
            raise ValueError("Embedding API Key 未配置")

        # 使用线程池执行同步阻塞操作，避免阻塞事件循环
        backend = EmbeddingService.create_backend(
            backend_type=backend_type,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=resolved_model,
            model_name=resolved_model_name,
        )
        service = EmbeddingService(embedding_backend=backend)
        result = await asyncio.to_thread(
            service.generate_embeddings,
            document_id=document_id,
        )

        update_document_info({
            "id": document_id,
            "processing_status": "embedded",
        })
        logger.info(f"Embedding completed for {document_id}: {result}")
    except Exception as e:
        logger.error(f"Error: Embedding failed for {document_id}: {e}")
        update_document_info({
            "id": document_id,
            "processing_status": "embedding_failed",
            "processing_error": str(e),
        })


async def _async_embedding_all(
    docs: list,
    parallel_count: int,
    backend_type: str,
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
    model_name: Optional[str],
):
    """
    异步批量嵌入所有 chunked 状态的文档

    :param docs: 文档列表
    :param parallel_count: 并行数量
    :param backend_type: Embedding 后端类型
    :param api_key: Embedding API Key
    :param base_url: Embedding API 基础 URL
    :param model: Embedding 模型名称
    :param model_name: 本地模型名称
    """
    async with _embedding_all_lock:
        semaphore = asyncio.Semaphore(parallel_count)

        async def _embedding_single_doc(doc):
            """嵌入单个文档"""
            async with semaphore:
                document_id = doc["id"]

                logger.info(f"Starting embedding for document {document_id}: {doc.get('file_name', 'unknown')}")
                t0 = time.time()

                try:
                    update_document_info({
                        "id": document_id,
                        "processing_status": "embedding",
                    })

                    # 从参数或环境变量获取配置
                    resolved_api_key = api_key or settings.embedding_openai_api_key
                    resolved_base_url = base_url or settings.embedding_openai_base_url
                    resolved_model = model or settings.embedding_openai_model
                    resolved_model_name = model_name or settings.embedding_model

                    if backend_type == "openai" and not resolved_api_key:
                        raise ValueError("Embedding API Key 未配置")

                    backend = EmbeddingService.create_backend(
                        backend_type=backend_type,
                        api_key=resolved_api_key,
                        base_url=resolved_base_url,
                        model=resolved_model,
                        model_name=resolved_model_name,
                    )
                    service = EmbeddingService(embedding_backend=backend)
                    result = await asyncio.to_thread(
                        service.generate_embeddings,
                        document_id=document_id,
                    )

                    update_document_info({
                        "id": document_id,
                        "processing_status": "embedded",
                    })
                    logger.info(f"Embedding completed for document {document_id} in {time.time() - t0:.2f}s: {result}")

                except Exception as e:
                    logger.error(f"Error: Embedding failed for document {document_id} in {time.time() - t0:.2f}s: {e}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "embedding_failed",
                        "processing_error": str(e),
                    })

        # 并发执行所有文档嵌入
        tasks = [_embedding_single_doc(doc) for doc in docs]
        await asyncio.gather(*tasks)
        logger.info(f"Batch embedding completed: {len(docs)} documents processed")


# ==================== API 接口 ====================


@router.post("/process/parse", response_model=ParseResponse)
async def parse_document(request: ParseRequest, background_tasks: BackgroundTasks):
    """
    异步解析 PDF/DOCX 文档并保存 Items

    - **pdf_path**: 文件路径（支持 .pdf 和 .docx）
    - **document_id**: 文档 ID
    - **page_range**: 页码范围 (start, end)，1-based（可选，仅对 PDF 有效）
    - **output_dir**: 图片保存目录
    - **do_ocr**: 是否启用 OCR（仅对 PDF 有效）
    """
    background_tasks.add_task(
        _async_parse,
        request.pdf_path,
        request.document_id,
        request.page_range,
        request.output_dir,
        request.do_ocr,
    )
    return ParseResponse(
        success=True,
        message="文档解析任务已提交，正在后台处理",
    )


@router.post("/process/parse-all", response_model=ParseAllResponse)
async def parse_all_documents(request: ParseAllRequest, background_tasks: BackgroundTasks):
    """
    异步批量解析所有 uploaded 状态的文档

    - **parallel_count**: 并行数量（默认1）
    - **output_dir**: 图片保存目录
    - **do_ocr**: 是否启用 OCR
    """
    # 使用全局锁防止并发执行 parse-all
    if _parse_all_lock.locked():
        return ParseAllResponse(
            success=False,
            message="已有批量解析任务正在执行，请稍后再试",
            total=0,
            parallel_count=request.parallel_count,
        )

    # 查询所有 uploaded 状态的文档
    docs = query_documents_by_status(processing_status="uploaded")

    if not docs:
        return ParseAllResponse(
            success=True,
            message="没有需要解析的文档",
            total=0,
            parallel_count=request.parallel_count,
        )

    background_tasks.add_task(
        _async_parse_all,
        docs,
        request.parallel_count,
        request.output_dir,
        request.do_ocr,
    )

    return ParseAllResponse(
        success=True,
        message=f"已提交 {len(docs)} 个文档的解析任务，并行数: {request.parallel_count}",
        total=len(docs),
        parallel_count=request.parallel_count,
    )


@router.post("/process/vlm", response_model=VLMResponse)
async def generate_vlm_descriptions(request: VLMRequest, background_tasks: BackgroundTasks):
    """
    异步为文档的图片 Items 生成 VLM 描述

    - **document_id**: 文档 ID
    - **output_dir**: 图片保存目录
    - **backend_type**: VLM 后端类型（openai / local）
    - **api_key**: VLM API Key
    - **base_url**: VLM API 基础 URL
    - **model**: VLM 模型名称
    - **prompt**: VLM 提示词
    - **max_new_tokens**: 最大生成 token 数
    - **language**: 输出语言（en/zh/ja），默认英文
    - **detail_level**: 描述详细程度（brief/detailed/comprehensive）
    """
    if not request.api_key and not settings.vlm_openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="VLM API Key 未配置。请设置环境变量 VLM_OPENAI_API_KEY 或在请求中传入 api_key。"
        )

    # Validate document status - only allow VLM for parsed documents
    doc_list = query_document_info(request.document_id)
    if not doc_list:
        raise HTTPException(status_code=404, detail=f"文档 {request.document_id} 不存在")
    doc_info = doc_list[0]
    if doc_info.get("processing_status") != "parsed":
        raise HTTPException(
            status_code=400,
            detail=f"文档状态为 {doc_info.get('processing_status')}，只有已解析状态的文档才能进行 VLM 增强"
        )

    background_tasks.add_task(
        _async_vlm,
        request.document_id,
        request.output_dir,
        request.backend_type,
        request.api_key,
        request.base_url,
        request.model,
        request.prompt,
        request.max_new_tokens,
        request.language,
        request.detail_level,
    )
    return VLMResponse(
        success=True,
        message="VLM 增强任务已提交，正在后台处理",
    )


@router.post("/process/vlm-all", response_model=VlmAllResponse)
async def vlm_all_documents(request: VlmAllRequest, background_tasks: BackgroundTasks):
    """
    异步批量 VLM 增强所有已解析的文档

    - **parallel_count**: 并行数量（默认1）
    - **output_dir**: 图片保存目录
    - **backend_type**: VLM 后端类型（openai / local）
    - **api_key**: VLM API Key
    - **base_url**: VLM API 基础 URL
    - **model**: VLM 模型名称
    - **prompt**: VLM 提示词
    - **max_new_tokens**: 最大生成 token 数
    - **language**: 输出语言（en/zh/ja），默认英文
    - **detail_level**: 描述详细程度（brief/detailed/comprehensive）
    """
    # Use global lock to prevent concurrent execution of vlm-all
    if _vlm_all_lock.locked():
        return VlmAllResponse(
            success=False,
            message="已有批量 VLM 增强任务正在执行，请稍后再试",
            total=0,
            parallel_count=request.parallel_count,
        )

    # Query all parsed documents that need VLM processing
    docs = query_documents_by_status(processing_status="parsed")

    if not docs:
        return VlmAllResponse(
            success=True,
            message="没有需要 VLM 增强的文档（状态为已解析）",
            total=0,
            parallel_count=request.parallel_count,
        )

    background_tasks.add_task(
        _async_vlm_all,
        docs,
        request.parallel_count,
        request.output_dir,
        request.backend_type,
        request.api_key,
        request.base_url,
        request.model,
        request.prompt,
        request.max_new_tokens,
        request.language,
        request.detail_level,
    )

    return VlmAllResponse(
        success=True,
        message=f"已提交 {len(docs)} 个文档的 VLM 增强任务，并行数: {request.parallel_count}",
        total=len(docs),
        parallel_count=request.parallel_count,
    )


@router.post("/process/chunk", response_model=ChunkResponse)
async def chunk_document(request: ChunkRequest, background_tasks: BackgroundTasks):
    """
    异步对文档进行语义分块（自动注入 VLM 描述）

    - **pdf_path**: 文件路径（支持 .pdf 和 .docx）
    - **document_id**: 文档 ID
    - **page_range**: 页码范围 (start, end)，1-based（可选，仅对 PDF 有效）
    - **token_limits**: token 限制列表，默认 [256, 512, 1024]
    - **tokenizer_name**: tokenizer 名称
    - **do_ocr**: 是否启用 OCR（仅对 PDF 有效）
    """
    background_tasks.add_task(
        _async_chunk,
        request.pdf_path,
        request.document_id,
        request.page_range,
        request.token_limits,
        request.tokenizer_name,
        request.do_ocr,
    )
    return ChunkResponse(
        success=True,
        message="文档分块任务已提交，正在后台处理",
    )


@router.post("/process/chunk-all", response_model=ChunkAllResponse)
async def chunk_all_documents(request: ChunkAllRequest, background_tasks: BackgroundTasks):
    """
    异步批量分块所有 vlm_completed 状态的文档

    - **parallel_count**: 并行数量（默认1）
    - **token_limits**: token 限制列表，默认 [256, 512, 1024]
    - **tokenizer_name**: tokenizer 名称
    - **do_ocr**: 是否启用 OCR
    """
    # Use global lock to prevent concurrent execution of chunk-all
    if _chunk_all_lock.locked():
        return ChunkAllResponse(
            success=False,
            message="已有批量分块任务正在执行，请稍后再试",
            total=0,
            parallel_count=request.parallel_count,
        )

    # Query all vlm_completed documents that need chunking
    docs = query_documents_by_status(processing_status="vlm_completed")

    if not docs:
        return ChunkAllResponse(
            success=True,
            message="没有需要分块的文档（状态为VLM已完成）",
            total=0,
            parallel_count=request.parallel_count,
        )

    background_tasks.add_task(
        _async_chunk_all,
        docs,
        request.parallel_count,
        request.token_limits,
        request.tokenizer_name,
        request.do_ocr,
    )

    return ChunkAllResponse(
        success=True,
        message=f"已提交 {len(docs)} 个文档的分块任务，并行数: {request.parallel_count}",
        total=len(docs),
        parallel_count=request.parallel_count,
    )


@router.post("/process/embedding", response_model=EmbeddingResponse)
async def generate_embeddings(request: EmbeddingRequest, background_tasks: BackgroundTasks):
    """
    异步为文档的 Chunks 生成向量嵌入

    - **document_id**: 文档 ID
    - **backend_type**: Embedding 后端类型（openai / local）
    - **api_key**: Embedding API Key
    - **base_url**: Embedding API 基础 URL
    - **model**: Embedding 模型名称（OpenAI 后端）
    - **model_name**: 本地模型名称（local 后端）
    """
    if not request.api_key and not settings.embedding_openai_api_key and request.backend_type == "openai":
        raise HTTPException(
            status_code=400,
            detail="Embedding API Key 未配置。请设置环境变量 EMBEDDING_OPENAI_API_KEY 或在请求中传入 api_key。"
        )

    background_tasks.add_task(
        _async_embedding,
        request.document_id,
        request.backend_type,
        request.api_key,
        request.base_url,
        request.model,
        request.model_name,
    )
    return EmbeddingResponse(
        success=True,
        message="Embedding 生成任务已提交，正在后台处理",
    )


@router.post("/process/embedding-all", response_model=EmbeddingAllResponse)
async def embedding_all_documents(request: EmbeddingAllRequest, background_tasks: BackgroundTasks):
    """
    异步批量嵌入所有 chunked 状态的文档

    - **parallel_count**: 并行数量（默认1）
    - **backend_type**: Embedding 后端类型（openai / local）
    - **api_key**: Embedding API Key
    - **base_url**: Embedding API 基础 URL
    - **model**: Embedding 模型名称（OpenAI 后端）
    - **model_name**: 本地模型名称（local 后端）
    """
    # Use global lock to prevent concurrent execution of embedding-all
    if _embedding_all_lock.locked():
        return EmbeddingAllResponse(
            success=False,
            message="已有批量嵌入任务正在执行，请稍后再试",
            total=0,
            parallel_count=request.parallel_count,
        )

    # Query all chunked documents that need embedding
    docs = query_documents_by_status(processing_status="chunked")

    if not docs:
        return EmbeddingAllResponse(
            success=True,
            message="没有需要嵌入的文档（状态为已分块）",
            total=0,
            parallel_count=request.parallel_count,
        )

    background_tasks.add_task(
        _async_embedding_all,
        docs,
        request.parallel_count,
        request.backend_type,
        request.api_key,
        request.base_url,
        request.model,
        request.model_name,
    )

    return EmbeddingAllResponse(
        success=True,
        message=f"已提交 {len(docs)} 个文档的嵌入任务，并行数: {request.parallel_count}",
        total=len(docs),
        parallel_count=request.parallel_count,
    )


@router.get("/{document_id}/file")
async def get_document_file(document_id: str, image_path: Optional[str] = None):
    """
    获取文档文件（支持本地路径和 URL）

    - **document_id**: 文档 ID
    - **image_path**: 图片路径（从 metadata.image_path 传入，用于直接查看图片）
    """
    docs = query_document_info(document_id=document_id)
    if not docs:
        raise HTTPException(status_code=404, detail="文档不存在")

    doc = docs[0]

    # If image_path is provided, serve that specific image
    if image_path:
        # 从 MinIO specs-pictures 桶解析到本地缓存路径
        from smartcard_kb.storage import resolve_image
        try:
            resolved_path_str = resolve_image(image_path)
            resolved_path = Path(resolved_path_str)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"图片解析失败: {image_path}: {e}")

        if not resolved_path.exists():
            raise HTTPException(status_code=404, detail=f"图片不存在: {resolved_path}")

        ext = resolved_path.suffix.lower()
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
        }
        media_type = media_type_map.get(ext, 'application/octet-stream')

        file_name = resolved_path.name
        return FileResponse(
            path=str(resolved_path),
            filename=file_name,
            media_type=media_type,
            headers={"Content-Disposition": f'inline; filename="{file_name}"'},
        )

    # Otherwise, serve the main document file
    file_path = doc.get("file_path")
    if not file_path:
        raise HTTPException(status_code=404, detail="文档路径未配置")

    # If it's a URL, redirect to it
    if file_path.startswith(("http://", "https://")):
        return RedirectResponse(url=file_path, status_code=302)

    # Local file path
    resolved_path = Path(file_path)
    if not resolved_path.is_absolute():
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        resolved_path = project_root / resolved_path

    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {resolved_path}")

    file_name = doc.get("file_name", resolved_path.name)

    # Determine media type based on file extension for inline browser display
    ext = resolved_path.suffix.lower()
    media_type_map = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.bmp': 'image/bmp',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
        '.json': 'application/json',
        '.xml': 'application/xml',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    }
    media_type = media_type_map.get(ext, 'application/octet-stream')

    return FileResponse(
        path=str(resolved_path),
        filename=file_name,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{file_name}"'},
    )


# ==================== TOC 提取 ====================


class ExtractTocRequest(BaseModel):
    """TOC 提取请求"""
    document_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_pages: int = 5


class ExtractTocResponse(BaseModel):
    """TOC 提取响应"""
    success: bool
    message: str
    toc: Optional[list] = None
    toc_count: int = 0


@router.post("/extract-toc", response_model=ExtractTocResponse)
async def extract_toc(request: ExtractTocRequest):
    """
    使用 LLM 从 PDF 前 N 页提取目录结构（TOC）

    - **document_id**: 文档 ID
    - **api_key**: LLM API Key（可选，默认从环境变量读取）
    - **base_url**: LLM API URL（可选）
    - **model**: LLM 模型名（可选）
    - **max_pages**: 提取的最大页数（默认 5）
    """
    import sys
    import json as json_module
    from pathlib import Path as PathLib

    # 添加 tests 目录到 path（toc_extractor_llm 在 tests/ 下）
    project_root = Path(__file__).parent.parent.parent.parent
    tests_dir = str(project_root / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)

    from toc_extractor_llm import extract_toc_from_pdf

    try:
        # 查询文档信息获取 PDF 路径
        docs = query_document_info(document_id=request.document_id)
        if not docs:
            raise HTTPException(status_code=404, detail=f"文档 {request.document_id} 不存在")

        doc = docs[0]
        pdf_path = doc.get("file_path", "")
        if not pdf_path:
            raise HTTPException(status_code=404, detail=f"PDF 文件路径为空")
        pdf_path = resolve_file(pdf_path)
        if not Path(pdf_path).exists():
            raise HTTPException(status_code=404, detail=f"PDF 文件不存在: {pdf_path}")

        # LLM 参数
        api_key = request.api_key or settings.openai_api_key
        base_url = request.base_url or settings.openai_base_url
        model = request.model or settings.openai_model

        if not api_key or not base_url:
            raise HTTPException(
                status_code=400,
                detail="未配置 LLM API。请提供 api_key 和 base_url，或在环境变量中设置 OPENAI_API_KEY 和 OPENAI_BASE_URL"
            )

        logger.info(f"Extracting TOC for document {request.document_id} from {pdf_path}")

        # 调用 LLM 提取 TOC
        toc = await asyncio.to_thread(
            extract_toc_from_pdf,
            pdf_path=pdf_path,
            api_url=base_url,
            api_key=api_key,
            model=model,
            max_pages=request.max_pages,
        )

        # 保存 TOC 到文档输出目录
        output_dir = Path("output") / "toc" / request.document_id
        output_dir.mkdir(parents=True, exist_ok=True)
        toc_path = output_dir / "toc.json"
        with open(toc_path, "w", encoding="utf-8") as f:
            json_module.dump(toc, f, ensure_ascii=False, indent=2)

        logger.info(f"TOC extracted: {len(toc)} entries, saved to {toc_path}")

        return ExtractTocResponse(
            success=True,
            message=f"成功提取 {len(toc)} 个目录条目",
            toc=toc,
            toc_count=len(toc),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TOC extraction failed for {request.document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"TOC 提取失败: {str(e)}")


class ExtractTocAllRequest(BaseModel):
    """批量 TOC 提取请求"""
    parallel_count: int = 1
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_pages: int = 5


class ExtractTocAllResponse(BaseModel):
    """批量 TOC 提取响应"""
    success: bool
    message: str
    total: int
    parallel_count: int


@router.post("/extract-toc-all", response_model=ExtractTocAllResponse)
async def extract_toc_all(request: ExtractTocAllRequest):
    """
    批量提取所有已解析文档的 TOC

    - **parallel_count**: 并行数量（默认 1）
    - **api_key**: LLM API Key（可选）
    - **base_url**: LLM API URL（可选）
    - **model**: LLM 模型名（可选）
    - **max_pages**: 提取的最大页数（默认 5）
    """
    import sys
    import json as json_module
    from pathlib import Path as PathLib

    project_root = Path(__file__).parent.parent.parent.parent
    tests_dir = str(project_root / "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)

    from toc_extractor_llm import extract_toc_from_pdf

    try:
        # 查询所有已解析的文档
        docs = query_documents_by_status(processing_status="parsed")
        if not docs:
            return ExtractTocAllResponse(
                success=True,
                message="没有已解析的文档",
                total=0,
                parallel_count=request.parallel_count,
            )

        api_key = request.api_key or settings.openai_api_key
        base_url = request.base_url or settings.openai_base_url
        model = request.model or settings.openai_model

        if not api_key or not base_url:
            raise HTTPException(
                status_code=400,
                detail="未配置 LLM API。请提供 api_key 和 base_url，或在环境变量中设置"
            )

        semaphore = asyncio.Semaphore(request.parallel_count)
        success_count = 0
        fail_count = 0

        async def extract_one(doc):
            nonlocal success_count, fail_count
            async with semaphore:
                doc_id = doc["id"]
                pdf_path = doc.get("file_path", "")
                if not pdf_path:
                    logger.error(f"Error: file_path not found for document {doc_id}")
                    return
                pdf_path = resolve_file(pdf_path)
                if not Path(pdf_path).exists():
                    logger.warning(f"Skip {doc_id}: PDF not found")
                    fail_count += 1
                    return

                try:
                    t0 = time.time()
                    toc = await asyncio.to_thread(
                        extract_toc_from_pdf,
                        pdf_path=pdf_path,
                        api_url=base_url,
                        api_key=api_key,
                        model=model,
                        max_pages=request.max_pages,
                    )

                    # 保存 TOC
                    output_dir = Path("output") / "toc" / doc_id
                    output_dir.mkdir(parents=True, exist_ok=True)
                    with open(output_dir / "toc.json", "w", encoding="utf-8") as f:
                        json_module.dump(toc, f, ensure_ascii=False, indent=2)

                    elapsed = time.time() - t0
                    logger.info(f"TOC extracted for {doc_id}: {len(toc)} entries in {elapsed:.1f}s")
                    success_count += 1
                except Exception as e:
                    logger.error(f"TOC extraction failed for {doc_id}: {e}")
                    fail_count += 1

        tasks = [extract_one(doc) for doc in docs]
        await asyncio.gather(*tasks)

        return ExtractTocAllResponse(
            success=True,
            message=f"完成: {success_count} 成功, {fail_count} 失败",
            total=len(docs),
            parallel_count=request.parallel_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch TOC extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"批量 TOC 提取失败: {str(e)}")

# ==================== Doc TOC 端点 ====================

class DocTocRequest(BaseModel):
    """Doc TOC 请求 — 基于 doc_items + PDF 目录 + LLM 推理生成准确目录树"""
    document_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_pages: int = 10  # 从 PDF 提取前 N 页用于目录文本
    max_items: int = 500  # 最多送入 LLM 的标题数


class DocTocResponse(BaseModel):
    """Doc TOC 响应"""
    success: bool
    message: str
    toc_count: int = 0


@router.post("/doc-toc", response_model=DocTocResponse)
async def doc_toc(request: DocTocRequest):
    """
    对单个文档执行 Doc TOC（基于 doc_items + PDF 目录 + LLM 推理）

    - **document_id**: 文档 ID
    - **api_key**: LLM API Key（可选）
    - **base_url**: LLM API URL（可选）
    - **model**: LLM 模型名（可选）
    - **max_pages**: 从 PDF 提取前 N 页用于目录文本（默认 10）
    - **max_items**: 最多送入 LLM 的标题数（默认 500）
    """
    import sys
    import psycopg2
    import psycopg2.extras
    from pathlib import Path as PathLib

    try:
        # 查询文档信息
        docs = query_document_info(document_id=request.document_id)
        if not docs:
            raise HTTPException(status_code=404, detail=f"文档 {request.document_id} 不存在")

        doc = docs[0]
        pdf_path = doc.get("file_path", "")
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF 文件路径为空")
        pdf_path = resolve_file(pdf_path)
        if not PathLib(pdf_path).exists():
            raise HTTPException(status_code=404, detail=f"PDF 文件不存在: {pdf_path}")

        # LLM 参数
        api_key = request.api_key or settings.openai_api_key
        base_url = request.base_url or settings.openai_base_url
        model = request.model or settings.openai_model

        if not api_key or not base_url:
            raise HTTPException(
                status_code=400,
                detail="未配置 LLM API。请提供 api_key 和 base_url，或在环境变量中设置"
            )

        logger.info(f"Doc TOC for document {request.document_id} from {pdf_path}")

        # 查询 doc_items 中的 section_header
        from smartcard_kb.docs_compile.database import get_connection
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT order_index, text, page_id, metadata
            FROM doc_items
            WHERE document_id = %s AND label = 'section_header'
            ORDER BY order_index
            """,
            (request.document_id,),
        )
        doc_items = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        # 注意：这里不关闭 conn，后续还需要查询所有 doc_items

        if not doc_items:
            conn.close()  # 提前返回时关闭连接
            return DocTocResponse(
                success=False,
                message="该文档没有 section_header 类型的 doc_items，请先执行解析",
                toc_count=0,
            )

        logger.info(f"Found {len(doc_items)} section_headers for {request.document_id}")

        # 添加 tests 目录到 path
        project_root = PathLib(__file__).parent.parent.parent.parent
        tests_dir = str(project_root / "tests")
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)

        from toc_refiner_llm import refine_toc_with_llm
        from smartcard_kb.docs_compile.database import insert_doc_tocs

        # 调用 LLM 推理生成目录树
        entries = await asyncio.to_thread(
            refine_toc_with_llm,
            pdf_path=pdf_path,
            doc_items=doc_items,
            api_url=base_url,
            api_key=api_key,
            model=model,
            max_pages=request.max_pages,
            max_items=request.max_items,
        )

        if not entries:
            conn.close()  # 提前返回时关闭连接
            return DocTocResponse(
                success=False,
                message="LLM 未返回任何目录条目",
                toc_count=0,
            )

        # 查询所有 doc_items 用于计算 end_page/end_item_index
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT order_index, page_id
            FROM doc_items
            WHERE document_id = %s
            ORDER BY order_index
            """,
            (request.document_id,),
        )
        all_items = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        conn.close()  # 现在才关闭连接

        # 构建 order_index -> (page_id, order_index) 的映射，便于快速查找
        items_by_order = {item["order_index"]: item for item in all_items}
        all_order_indices = sorted(items_by_order.keys())

        # 构建 doc_tocs 记录（计算 start/end_page, start/end_item_index, parent_id）
        tocs = []
        for i, entry in enumerate(entries):
            item_index = entry.get("item_index", 0)
            page = entry.get("page", 1)

            # 找下一个同级或更高级标题的 item_index
            next_item_index = None
            for j in range(i + 1, len(entries)):
                next_entry = entries[j]
                if next_entry.get("level", 1) <= entry.get("level", 1):
                    next_item_index = next_entry.get("item_index", 0)
                    break

            # 通过 doc_items 计算 end_page 和 end_item_index
            # 范围：[item_index, next_item_index - 1]
            end_page = None
            end_item_index = None

            if next_item_index is not None:
                # 找到范围内最后一个 order_index <= next_item_index - 1 的 item
                # 即找到 < next_item_index 的最大 order_index
                candidate_orders = [o for o in all_order_indices if o < next_item_index and o >= item_index]
                if candidate_orders:
                    last_order = max(candidate_orders)
                    last_item = items_by_order[last_order]
                    end_page = last_item["page_id"]
                    end_item_index = last_order
            else:
                # 最后一个章节，找文档末尾的 item
                candidate_orders = [o for o in all_order_indices if o >= item_index]
                if candidate_orders:
                    last_order = max(candidate_orders)
                    last_item = items_by_order[last_order]
                    end_page = last_item["page_id"]
                    end_item_index = last_order

            tocs.append({
                "title": entry.get("title", ""),
                "level": entry.get("level", 1),
                "start_page": page,
                "end_page": end_page,
                "start_item_index": item_index,
                "end_item_index": end_item_index,
                "parent_id": None,  # 后续构建父子关系
            })

        # 构建 parent_id 关系
        stack = []  # (level, id) 栈，用于追踪父节点
        for i, toc in enumerate(tocs):
            level = toc["level"]
            # 弹出栈中 level >= 当前 level 的节点
            while stack and stack[-1][0] >= level:
                stack.pop()
            # 栈顶就是父节点
            if stack:
                toc["parent_id"] = stack[-1][1]
            # 将当前节点压入栈（id 暂时用索引，后续插入后更新）
            stack.append((level, i))

        # 插入数据库
        inserted = insert_doc_tocs(request.document_id, tocs)

        return DocTocResponse(
            success=True,
            message=f"成功生成 {inserted} 条目录记录",
            toc_count=inserted,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Doc TOC failed for {request.document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Doc TOC 失败: {str(e)}")


class DocTocAllRequest(BaseModel):
    """批量 Doc TOC 请求"""
    parallel_count: int = 1
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_pages: int = 10
    max_items: int = 500


class DocTocAllResponse(BaseModel):
    """批量 Doc TOC 响应"""
    success: bool
    message: str
    total: int
    parallel_count: int


@router.post("/doc-toc-all", response_model=DocTocAllResponse)
async def doc_toc_all(request: DocTocAllRequest):
    """
    批量执行 Doc TOC

    - **parallel_count**: 并行数量（默认 1）
    - **api_key**: LLM API Key（可选）
    - **base_url**: LLM API URL（可选）
    - **model**: LLM 模型名（可选）
    - **max_pages**: 从 PDF 提取前 N 页（默认 10）
    - **max_items**: 最多送入 LLM 的标题数（默认 500）
    """
    import sys
    import psycopg2
    import psycopg2.extras
    from pathlib import Path as PathLib

    try:
        # 查询已解析的文档（有 section_header）
        docs = query_documents_by_status(status="parsed")
        if not docs:
            return DocTocAllResponse(
                success=True,
                message="没有已解析的文档",
                total=0,
                parallel_count=request.parallel_count,
            )

        logger.info(f"Batch Doc TOC: {len(docs)} documents, parallel={request.parallel_count}")

        sem = asyncio.Semaphore(request.parallel_count)
        success_count = 0
        fail_count = 0

        async def toc_one(doc):
            nonlocal success_count, fail_count
            async with sem:
                doc_id = doc["id"]
                t0 = time.time()
                try:
                    # 检查是否已生成目录（doc_tocs 表中已有该文档数据）
                    from smartcard_kb.docs_compile.database import get_connection
                    conn = get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(*) FROM doc_tocs WHERE document_id = %s",
                        (doc_id,),
                    )
                    toc_count = cursor.fetchone()[0]
                    cursor.close()
                    conn.close()

                    if toc_count > 0:
                        logger.info(f"Doc TOC skip {doc_id}: already has {toc_count} toc records")
                        success_count += 1
                        return

                    pdf_path = doc.get("file_path", "")
                    if not pdf_path:
                        logger.warning(f"Doc TOC skip {doc_id}: no file_path")
                        fail_count += 1
                        return
                    pdf_path = resolve_file(pdf_path)
                    if not PathLib(pdf_path).exists():
                        logger.warning(f"Doc TOC skip {doc_id}: file not found")
                        fail_count += 1
                        return

                    # 查询 doc_items
                    conn = get_connection()
                    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    cursor.execute(
                        """
                        SELECT order_index, text, page_id, metadata
                        FROM doc_items
                        WHERE document_id = %s AND label = 'section_header'
                        ORDER BY order_index
                        """,
                        (doc_id,),
                    )
                    doc_items = [dict(row) for row in cursor.fetchall()]
                    cursor.close()
                    # 注意：这里不关闭 conn，后续还需要查询所有 doc_items

                    if not doc_items:
                        conn.close()  # 提前返回时关闭连接
                        logger.warning(f"Doc TOC skip {doc_id}: no section_headers")
                        fail_count += 1
                        return

                    # 添加 tests 目录到 path
                    project_root = PathLib(__file__).parent.parent.parent.parent
                    tests_dir = str(project_root / "tests")
                    if tests_dir not in sys.path:
                        sys.path.insert(0, tests_dir)

                    from toc_refiner_llm import refine_toc_with_llm
                    from smartcard_kb.docs_compile.database import insert_doc_tocs

                    api_key = request.api_key or settings.openai_api_key
                    base_url = request.base_url or settings.openai_base_url
                    model = request.model or settings.openai_model

                    if not api_key or not base_url:
                        logger.error(f"Doc TOC skip {doc_id}: no LLM config")
                        fail_count += 1
                        return

                    # 调用 LLM 推理
                    entries = await asyncio.to_thread(
                        refine_toc_with_llm,
                        pdf_path=pdf_path,
                        doc_items=doc_items,
                        api_url=base_url,
                        api_key=api_key,
                        model=model,
                        max_pages=request.max_pages,
                        max_items=request.max_items,
                    )

                    if not entries:
                        logger.warning(f"Doc TOC skip {doc_id}: LLM returned empty")
                        fail_count += 1
                        return

                    # 查询所有 doc_items 用于计算 end_page/end_item_index
                    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    cursor.execute(
                        """
                        SELECT order_index, page_id
                        FROM doc_items
                        WHERE document_id = %s
                        ORDER BY order_index
                        """,
                        (doc_id,),
                    )
                    all_items = [dict(row) for row in cursor.fetchall()]
                    cursor.close()
                    conn.close()  # 现在才关闭连接

                    # 构建 order_index -> (page_id, order_index) 的映射
                    items_by_order = {item["order_index"]: item for item in all_items}
                    all_order_indices = sorted(items_by_order.keys())

                    # 构建 doc_tocs 记录
                    tocs = []
                    for i, entry in enumerate(entries):
                        item_index = entry.get("item_index", 0)
                        page = entry.get("page", 1)

                        # 找下一个同级或更高级标题的 item_index
                        next_item_index = None
                        for j in range(i + 1, len(entries)):
                            if entries[j].get("level", 1) <= entry.get("level", 1):
                                next_item_index = entries[j].get("item_index", 0)
                                break

                        # 通过 doc_items 计算 end_page 和 end_item_index
                        end_page = None
                        end_item_index = None

                        if next_item_index is not None:
                            # 找到范围内最后一个 order_index < next_item_index 的 item
                            candidate_orders = [o for o in all_order_indices if o < next_item_index and o >= item_index]
                            if candidate_orders:
                                last_order = max(candidate_orders)
                                last_item = items_by_order[last_order]
                                end_page = last_item["page_id"]
                                end_item_index = last_order
                        else:
                            # 最后一个章节，找文档末尾的 item
                            candidate_orders = [o for o in all_order_indices if o >= item_index]
                            if candidate_orders:
                                last_order = max(candidate_orders)
                                last_item = items_by_order[last_order]
                                end_page = last_item["page_id"]
                                end_item_index = last_order

                        tocs.append({
                            "title": entry.get("title", ""),
                            "level": entry.get("level", 1),
                            "start_page": page,
                            "end_page": end_page,
                            "start_item_index": item_index,
                            "end_item_index": end_item_index,
                            "parent_id": None,
                        })

                    # 构建 parent_id
                    stack = []
                    for i, toc in enumerate(tocs):
                        level = toc["level"]
                        while stack and stack[-1][0] >= level:
                            stack.pop()
                        if stack:
                            toc["parent_id"] = stack[-1][1]
                        stack.append((level, i))

                    # 插入数据库
                    inserted = insert_doc_tocs(doc_id, tocs)

                    elapsed = time.time() - t0
                    logger.info(f"Doc TOC {doc_id}: {inserted} entries in {elapsed:.1f}s")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Doc TOC failed for {doc_id}: {e}")
                    fail_count += 1

        tasks = [toc_one(doc) for doc in docs]
        await asyncio.gather(*tasks)

        return DocTocAllResponse(
            success=True,
            message=f"完成: {success_count} 成功, {fail_count} 失败",
            total=len(docs),
            parallel_count=request.parallel_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch Doc TOC failed: {e}")
        raise HTTPException(status_code=500, detail=f"批量 Doc TOC 失败: {str(e)}")


# ==================== Doc Summary（分层概要提取） ====================


class DocSummaryRequest(BaseModel):
    """单文档概要提取请求"""
    document_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class DocSummaryResponse(BaseModel):
    """单文档概要提取响应"""
    success: bool
    message: str
    processed_count: int = 0


@router.post("/doc-summary", response_model=DocSummaryResponse)
async def doc_summary(request: DocSummaryRequest):
    """
    对单个文档执行分层概要提取

    - **document_id**: 文档 ID
    - **api_key**: LLM API Key（可选）
    - **base_url**: LLM API URL（可选）
    - **model**: LLM 模型名（可选）
    """
    import sys
    import psycopg2
    import psycopg2.extras
    from pathlib import Path as PathLib

    try:
        # 查询文档信息
        docs = query_document_info(document_id=request.document_id)
        if not docs:
            raise HTTPException(status_code=404, detail=f"文档 {request.document_id} 不存在")

        doc = docs[0]
        # 获取文档语言，默认为 en
        doc_language = doc.get("language") or "en"

        # LLM 参数
        api_key = request.api_key or settings.openai_api_key
        base_url = request.base_url or settings.openai_base_url
        model = request.model or settings.openai_model

        if not api_key or not base_url:
            raise HTTPException(
                status_code=400,
                detail="未配置 LLM API。请提供 api_key 和 base_url，或在环境变量中设置"
            )

        logger.info(f"Doc Summary for document {request.document_id}, language={doc_language}")

        # 查询 doc_tocs
        from smartcard_kb.docs_compile.database import get_connection, query_doc_tocs, update_doc_toc_summaries
        tocs = query_doc_tocs(request.document_id)
        if not tocs:
            return DocSummaryResponse(
                success=False,
                message="该文档没有目录结构，请先执行「生成目录」",
                processed_count=0,
            )

        # 添加 tests 目录到 path
        project_root = PathLib(__file__).parent.parent.parent.parent
        tests_dir = str(project_root / "tests")
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)

        from summary_extractor_llm import extract_summary_with_llm

        # 构建 id -> toc 映射和父子关系
        toc_map = {toc["id"]: toc for toc in tocs}
        children_map = {}  # parent_id -> [child_tocs]
        for toc in tocs:
            parent_id = toc.get("parent_id")
            if parent_id:
                if parent_id not in children_map:
                    children_map[parent_id] = []
                children_map[parent_id].append(toc)

        # 查询所有 doc_items 用于获取章节内容
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            """
            SELECT order_index, text, label, page_id
            FROM doc_items
            WHERE document_id = %s
            ORDER BY order_index
            """,
            (request.document_id,),
        )
        all_items = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        # 构建 order_index -> item 映射
        items_by_order = {item["order_index"]: item for item in all_items}
        all_order_indices = sorted(items_by_order.keys())

        # 按层级分组（从大到小，即从最底层开始）
        levels = sorted(set(toc["level"] for toc in tocs), reverse=True)
        processed_count = 0

        for level in levels:
            level_tocs = [toc for toc in tocs if toc["level"] == level]
            logger.info(f"Processing level {level}: {len(level_tocs)} nodes")

            for toc in level_tocs:
                toc_id = toc["id"]
                title = toc["title"]
                start_item_index = toc.get("start_item_index", 0)
                end_item_index = toc.get("end_item_index")

                # 获取该章节范围内的 items 内容
                content_parts = []
                for order in all_order_indices:
                    if order < start_item_index:
                        continue
                    if end_item_index is not None and order > end_item_index:
                        break
                    item = items_by_order[order]
                    text = item.get("text", "").strip()
                    label = item.get("label", "")
                    if text:
                        content_parts.append(f"[{label}] {text}")
                content = "\n".join(content_parts)

                # 获取子节点概要（如果有）
                children_summaries = []
                if toc_id in children_map:
                    for child in children_map[toc_id]:
                        child_summary = child.get("summary_512") or child.get("summary_256") or ""
                        if child_summary:
                            children_summaries.append({
                                "title": child["title"],
                                "summary": child_summary,
                            })

                # 调用 LLM 提取概要
                try:
                    summaries = await asyncio.to_thread(
                        extract_summary_with_llm,
                        title=title,
                        level=level,
                        content=content,
                        children_summaries=children_summaries if children_summaries else None,
                        api_url=base_url,
                        api_key=api_key,
                        model=model,
                        language=doc_language,
                    )
                    # 更新数据库
                    update_doc_toc_summaries(
                        toc_id=toc_id,
                        summary_256=summaries.get("summary_256"),
                        summary_512=summaries.get("summary_512"),
                        summary_1024=summaries.get("summary_1024"),
                    )
                    processed_count += 1
                    # 更新 toc_map 中的概要，供父节点使用
                    toc_map[toc_id].update(summaries)
                except Exception as e:
                    logger.error(f"Summary extraction failed for toc {toc_id} '{title}': {e}")

        return DocSummaryResponse(
            success=True,
            message=f"成功处理 {processed_count} 个章节",
            processed_count=processed_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Doc Summary failed for {request.document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"概要提取失败: {str(e)}")


class DocSummaryAllRequest(BaseModel):
    """批量概要提取请求"""
    parallel_count: int = 1
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class DocSummaryAllResponse(BaseModel):
    """批量概要提取响应"""
    success: bool
    message: str
    total: int
    parallel_count: int


@router.post("/doc-summary-all", response_model=DocSummaryAllResponse)
async def doc_summary_all(request: DocSummaryAllRequest):
    """
    批量执行概要提取

    - **parallel_count**: 并行数量（默认 1）
    - **api_key**: LLM API Key（可选）
    - **base_url**: LLM API URL（可选）
    - **model**: LLM 模型名（可选）
    """
    import sys
    import psycopg2
    import psycopg2.extras

    try:
        # 查询所有有 doc_tocs 的文档
        from smartcard_kb.docs_compile.database import get_connection
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute("""
            SELECT DISTINCT document_id FROM doc_tocs
        """)
        doc_ids = [row["document_id"] for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        if not doc_ids:
            return DocSummaryAllResponse(
                success=True,
                message="没有已生成目录的文档",
                total=0,
                parallel_count=request.parallel_count,
            )

        # 查询这些文档的详情
        docs = []
        for doc_id in doc_ids:
            doc_list = query_document_info(document_id=doc_id)
            if doc_list:
                docs.append(doc_list[0])

        logger.info(f"Batch Doc Summary: {len(docs)} documents, parallel={request.parallel_count}")

        sem = asyncio.Semaphore(request.parallel_count)
        success_count = 0
        fail_count = 0

        async def summary_one(doc):
            nonlocal success_count, fail_count
            async with sem:
                doc_id = doc["id"]
                t0 = time.time()
                try:
                    # 检查是否所有 toc 记录都已填充概要
                    from smartcard_kb.docs_compile.database import get_connection
                    conn = get_connection()
                    cursor = conn.cursor()
                    # 查询总记录数和已填充概要的记录数
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as total,
                            COUNT(CASE WHEN summary_256 IS NOT NULL AND summary_512 IS NOT NULL AND summary_1024 IS NOT NULL THEN 1 END) as completed
                        FROM doc_tocs 
                        WHERE document_id = %s
                    """, (doc_id,))
                    result = cursor.fetchone()
                    total = result[0]
                    completed = result[1]
                    cursor.close()
                    conn.close()

                    if total > 0 and total == completed:
                        logger.info(f"Doc Summary skip {doc_id}: all {total} toc records already have summaries")
                        success_count += 1
                        return

                    # 构造单文档请求
                    single_request = DocSummaryRequest(
                        document_id=doc_id,
                        api_key=request.api_key,
                        base_url=request.base_url,
                        model=request.model,
                    )
                    result = await doc_summary(single_request)
                    elapsed = time.time() - t0
                    logger.info(f"Doc Summary {doc_id}: {result.processed_count} nodes in {elapsed:.1f}s")
                    if result.success:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    logger.error(f"Doc Summary failed for {doc_id}: {e}")
                    fail_count += 1

        tasks = [summary_one(doc) for doc in docs]
        await asyncio.gather(*tasks)

        return DocSummaryAllResponse(
            success=True,
            message=f"完成: {success_count} 成功, {fail_count} 失败",
            total=len(docs),
            parallel_count=request.parallel_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch Doc Summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"批量概要提取失败: {str(e)}")
