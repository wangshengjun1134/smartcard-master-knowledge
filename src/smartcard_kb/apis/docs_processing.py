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
        resolved_path = Path(image_path)
        if not resolved_path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            resolved_path = project_root / resolved_path

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


# ==================== PageIndex ====================


class PageIndexRequest(BaseModel):
    """PageIndex 请求"""
    document_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_pages: int = 10


class PageIndexResponse(BaseModel):
    """PageIndex 响应"""
    success: bool
    message: str
    toc_count: int = 0


@router.post("/page-index", response_model=PageIndexResponse)
async def page_index(request: PageIndexRequest):
    """
    对单个文档执行 PageIndex（TOC 提取 + 层级构建）

    - **document_id**: 文档 ID
    - **api_key**: LLM API Key（可选，默认从环境变量读取）
    - **base_url**: LLM API URL（可选）
    - **model**: LLM 模型名（可选）
    - **max_pages**: 提取的最大页数（默认 10）
    """
    import sys
    import json as json_module
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

        # 更新状态为 indexing
        update_document_info({
            "id": request.document_id,
            "page_index_status": "indexing",
            "page_index_started_at": datetime.now().isoformat(),
            "page_index_error": None,
        })

        logger.info(f"PageIndex for document {request.document_id} from {pdf_path}")

        # 添加 tests 目录到 path
        project_root = PathLib(__file__).parent.parent.parent.parent
        tests_dir = str(project_root / "tests")
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)

        from toc_extractor_llm import extract_toc_from_pdf
        from toc_skeleton import build_skeleton_tree, detect_page_offset, assign_blocks_to_skeleton

        # Step 1: LLM 提取 TOC
        toc = await asyncio.to_thread(
            extract_toc_from_pdf,
            pdf_path=pdf_path,
            api_url=base_url,
            api_key=api_key,
            model=model,
            max_pages=request.max_pages,
        )

        if not toc:
            update_document_info({
                "id": request.document_id,
                "page_index_status": "index_failed",
                "page_index_finished_at": datetime.now().isoformat(),
                "page_index_error": "TOC extraction returned empty result",
            })
            return PageIndexResponse(
                success=False,
                message="TOC 提取失败：未找到目录结构",
                toc_count=0,
            )

        # Step 2: 保存 TOC
        output_dir = Path("output") / "toc" / request.document_id
        output_dir.mkdir(parents=True, exist_ok=True)
        toc_path = output_dir / "toc.json"
        with open(toc_path, "w", encoding="utf-8") as f:
            json_module.dump(toc, f, ensure_ascii=False, indent=2)

        # Step 3: 构建层级骨架
        skeleton = build_skeleton_tree(toc)

        # Step 4: 提取文本 blocks 并分配到骨架节点（填充 contexts）
        import fitz  # PyMuPDF
        pdf_doc = fitz.open(pdf_path)
        total_pages = len(pdf_doc)

        # 提取每页文本 blocks
        blocks = []
        for page_idx in range(total_pages):
            page = pdf_doc[page_idx]
            text_blocks = page.get_text("blocks")
            for tb in text_blocks:
                text = tb[4].strip() if len(tb) > 4 else ""
                if text:
                    blocks.append({
                        "type": "text",
                        "text": text,
                        "page_idx": page_idx,
                    })
        pdf_doc.close()

        logger.info(f"Extracted {len(blocks)} text blocks from {pdf_path}")

        # 检测页码偏移并分配 blocks 到骨架节点
        if blocks and skeleton:
            # 收集骨架节点标题，用于检测 text block 中的标题
            import re as _re

            def _flatten_titles(nodes, titles=None):
                if titles is None:
                    titles = set()
                for node in nodes:
                    t = node.get("title", "").strip().lower()
                    if t:
                        # 统一破折号/连字符，压缩空白
                        t = _re.sub(r'[\u2013\u2014\u2012\u2015\ufe58\ufe63\uff0d]', '-', t)
                        t = _re.sub(r'\s+', ' ', t)
                        titles.add(t)
                    _flatten_titles(node.get("children", []), titles)
                return titles

            skeleton_titles = _flatten_titles(skeleton)

            # 标记标题 block：text block 的文本匹配骨架节点标题 → type 改为 paragraph_title
            title_count = 0
            for block in blocks:
                text = block.get("text", "").strip().lower()
                if not text:
                    continue
                text_norm = _re.sub(r'[\u2013\u2014\u2012\u2015\ufe58\ufe63\uff0d]', '-', text)
                text_norm = _re.sub(r'\s+', ' ', text_norm)
                if text_norm in skeleton_titles:
                    block["type"] = "paragraph_title"
                    title_count += 1

            logger.info(f"Detected {title_count} title blocks from {len(blocks)} text blocks")

            page_offset = detect_page_offset(toc, blocks)
            logger.info(f"Detected page offset: {page_offset}")
            skeleton = assign_blocks_to_skeleton(skeleton, blocks, page_offset)

            # 统计 contexts 填充情况
            def count_contexts(nodes):
                total = 0
                for node in nodes:
                    total += len(node.get("contexts", []))
                    total += count_contexts(node.get("children", []))
                return total

            ctx_count = count_contexts(skeleton)
            logger.info(f"Assigned {ctx_count} contexts to skeleton nodes")

        # 保存骨架
        skeleton_path = output_dir / "skeleton.json"
        with open(skeleton_path, "w", encoding="utf-8") as f:
            json_module.dump(skeleton, f, ensure_ascii=False, indent=2)

        # 更新状态为 indexed
        update_document_info({
            "id": request.document_id,
            "page_index_status": "indexed",
            "page_index_finished_at": datetime.now().isoformat(),
            "page_index_error": None,
        })

        logger.info(f"PageIndex complete for {request.document_id}: {len(toc)} TOC entries")

        return PageIndexResponse(
            success=True,
            message=f"PageIndex 完成：提取 {len(toc)} 个目录条目",
            toc_count=len(toc),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PageIndex failed for {request.document_id}: {e}")
        update_document_info({
            "id": request.document_id,
            "page_index_status": "index_failed",
            "page_index_finished_at": datetime.now().isoformat(),
            "page_index_error": str(e),
        })
        raise HTTPException(status_code=500, detail=f"PageIndex 失败: {str(e)}")


class PageIndexAllRequest(BaseModel):
    """批量 PageIndex 请求"""
    parallel_count: int = 1
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    max_pages: int = 10


class PageIndexAllResponse(BaseModel):
    """批量 PageIndex 响应"""
    success: bool
    message: str
    total: int
    parallel_count: int


@router.post("/page-index-all", response_model=PageIndexAllResponse)
async def page_index_all(request: PageIndexAllRequest):
    """
    批量执行 PageIndex（对所有已上传文档）

    - **parallel_count**: 并行数量（默认 1）
    - **api_key**: LLM API Key（可选）
    - **base_url**: LLM API URL（可选）
    - **model**: LLM 模型名（可选）
    - **max_pages**: 提取的最大页数（默认 10）
    """
    import sys
    import json as json_module
    from pathlib import Path as PathLib

    try:
        # 查询所有已上传的文档
        docs = query_documents_by_status(processing_status="uploaded")
        if not docs:
            return PageIndexAllResponse(
                success=True,
                message="没有已上传的文档",
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

        # 添加 tests 目录到 path
        project_root = PathLib(__file__).parent.parent.parent.parent
        tests_dir = str(project_root / "tests")
        if tests_dir not in sys.path:
            sys.path.insert(0, tests_dir)

        from toc_extractor_llm import extract_toc_from_pdf
        from toc_skeleton import build_skeleton_tree

        semaphore = asyncio.Semaphore(request.parallel_count)
        success_count = 0
        fail_count = 0

        async def index_one(doc):
            nonlocal success_count, fail_count
            async with semaphore:
                doc_id = doc["id"]
                pdf_path = doc.get("file_path", "")
                if not pdf_path:
                    logger.warning(f"Skip {doc_id}: file_path empty")
                    fail_count += 1
                    return
                pdf_path = resolve_file(pdf_path)
                if not PathLib(pdf_path).exists():
                    logger.warning(f"Skip {doc_id}: PDF not found")
                    fail_count += 1
                    return

                try:
                    t0 = time.time()

                    update_document_info({
                        "id": doc_id,
                        "page_index_status": "indexing",
                        "page_index_started_at": datetime.now().isoformat(),
                    })

                    # TOC 提取
                    toc = await asyncio.to_thread(
                        extract_toc_from_pdf,
                        pdf_path=pdf_path,
                        api_url=base_url,
                        api_key=api_key,
                        model=model,
                        max_pages=request.max_pages,
                    )

                    if not toc:
                        update_document_info({
                        "id": doc_id,
                            "page_index_status": "index_failed",
                            "page_index_finished_at": datetime.now().isoformat(),
                            "page_index_error": "TOC extraction returned empty",
                        })
                        fail_count += 1
                        return

                    # 保存 TOC + 骨架
                    output_dir = Path("output") / "toc" / doc_id
                    output_dir.mkdir(parents=True, exist_ok=True)
                    with open(output_dir / "toc.json", "w", encoding="utf-8") as f:
                        json_module.dump(toc, f, ensure_ascii=False, indent=2)

                    skeleton = build_skeleton_tree(toc)
                    with open(output_dir / "skeleton.json", "w", encoding="utf-8") as f:
                        json_module.dump(skeleton, f, ensure_ascii=False, indent=2)

                    update_document_info({
                        "id": doc_id,
                        "page_index_status": "indexed",
                        "page_index_finished_at": datetime.now().isoformat(),
                    })

                    elapsed = time.time() - t0
                    logger.info(f"PageIndex for {doc_id}: {len(toc)} entries in {elapsed:.1f}s")
                    success_count += 1
                except Exception as e:
                    logger.error(f"PageIndex failed for {doc_id}: {e}")
                    update_document_info({
                        "id": doc_id,
                        "page_index_status": "index_failed",
                        "page_index_finished_at": datetime.now().isoformat(),
                        "page_index_error": str(e),
                    })
                    fail_count += 1

        tasks = [index_one(doc) for doc in docs]
        await asyncio.gather(*tasks)

        return PageIndexAllResponse(
            success=True,
            message=f"完成: {success_count} 成功, {fail_count} 失败",
            total=len(docs),
            parallel_count=request.parallel_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch PageIndex failed: {e}")
        raise HTTPException(status_code=500, detail=f"批量 PageIndex 失败: {str(e)}")


# ==================== Summary (章节摘要生成) ====================


class SummaryRequest(BaseModel):
    """单文档 Summary 请求"""
    document_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class SummaryResponse(BaseModel):
    """单文档 Summary 响应"""
    success: bool
    message: str
    summary_count: int = 0


SUMMARY_SYSTEM_PROMPT = """你是一个技术文档章节摘要生成专家。你的任务是为给定的章节文本生成简洁、信息密度高的摘要。

摘要要求：
1. 保留关键技术术语、参数、数值、单位
2. 保留重要的结构化信息（表格、列表、流程）
3. 去除冗余描述和非语义信息
4. 摘要长度控制在原文的 20%-30%
5. 使用与原文相同的语言
6. 直接输出摘要文本，不要添加"摘要："前缀或任何解释"""


@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(request: SummaryRequest):
    """
    对单个文档执行 Summary（基于 PageIndex 骨架，为每个章节生成摘要）

    - **document_id**: 文档 ID
    - **api_key**: LLM API Key（可选）
    - **base_url**: LLM API URL（可选）
    - **model**: 模型名（可选）
    """
    import json as json_module
    from pathlib import Path as PathLib

    try:
        # Query document info
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

        # Read skeleton
        output_dir = Path("output") / "toc" / request.document_id
        skeleton_path = output_dir / "skeleton.json"
        if not skeleton_path.exists():
            raise HTTPException(status_code=400, detail="请先执行 PageIndex 生成骨架")

        with open(skeleton_path, "r", encoding="utf-8") as f:
            skeleton = json_module.load(f)

        # LLM config
        api_key = request.api_key or settings.openai_api_key
        base_url = request.base_url or settings.openai_base_url
        model = request.model or settings.openai_model

        if not api_key or not base_url:
            raise HTTPException(status_code=400, detail="未配置 LLM API")

        # Extract text per chapter using PyMuPDF
        import fitz
        pdf_doc = fitz.open(pdf_path)
        total_pages = len(pdf_doc)

        # Flatten skeleton to get leaf nodes with page ranges
        def flatten_nodes(nodes, result=None):
            if result is None:
                result = []
            for node in nodes:
                result.append(node)
                if node.get("children"):
                    flatten_nodes(node["children"], result)
            return result

        all_nodes = flatten_nodes(skeleton)

        # Calculate page ranges for each node
        summaries = []
        for i, node in enumerate(all_nodes):
            start_page = node.get("page", 1)
            # End page is the next node's start page - 1, or last page
            if i + 1 < len(all_nodes):
                end_page = all_nodes[i + 1].get("page", total_pages) - 1
            else:
                end_page = total_pages

            # Clamp to valid range
            start_page = max(1, min(start_page, total_pages))
            end_page = max(start_page, min(end_page, total_pages))

            # Extract text from pages (0-indexed in PyMuPDF)
            text_parts = []
            for p in range(start_page - 1, end_page):
                page_text = pdf_doc[p].get_text("text").strip()
                if page_text:
                    text_parts.append(page_text)

            chapter_text = "\n".join(text_parts)
            if not chapter_text:
                summaries.append({
                    "number": node.get("number", ""),
                    "title": node.get("title", ""),
                    "level": node.get("level", 1),
                    "page": start_page,
                    "summary": "",
                    "error": "无文本内容",
                })
                continue

            # Truncate if too long (keep first 8000 chars)
            if len(chapter_text) > 8000:
                chapter_text = chapter_text[:8000] + "\n[... 文本已截断 ...]"

            # Call LLM for summary
            try:
                import httpx
                url = base_url.rstrip("/")
                if not url.endswith("/chat/completions"):
                    url = f"{url}/chat/completions"

                llm_payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                        {"role": "user", "content": f"请为以下章节生成摘要：\n\n章节标题：{node.get('number', '')} {node.get('title', '')}\n\n章节内容：\n{chapter_text}"},
                    ],
                    "temperature": 0.3,
                }

                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }

                with httpx.Client(timeout=120.0) as client:
                    resp = client.post(url, headers=headers, json=llm_payload)

                if resp.status_code >= 400:
                    raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:200]}")

                result = resp.json()
                summary_text = result["choices"][0]["message"]["content"].strip()

                summaries.append({
                    "number": node.get("number", ""),
                    "title": node.get("title", ""),
                    "level": node.get("level", 1),
                    "page": start_page,
                    "summary": summary_text,
                })
            except Exception as e:
                logger.error(f"Summary failed for node '{node.get('title', '')}': {e}")
                summaries.append({
                    "number": node.get("number", ""),
                    "title": node.get("title", ""),
                    "level": node.get("level", 1),
                    "page": start_page,
                    "summary": "",
                    "error": str(e),
                })

        pdf_doc.close()

        # Save summaries
        summary_path = output_dir / "summaries.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json_module.dump(summaries, f, ensure_ascii=False, indent=2)

        success_count = sum(1 for s in summaries if s.get("summary"))
        logger.info(f"Summary complete for {request.document_id}: {success_count}/{len(summaries)} chapters summarized")

        return SummaryResponse(
            success=True,
            message=f"Summary 完成：{success_count}/{len(summaries)} 个章节已生成摘要",
            summary_count=success_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Summary failed for {request.document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Summary 失败: {str(e)}")


class SummaryAllRequest(BaseModel):
    """批量 Summary 请求"""
    parallel_count: int = 1
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class SummaryAllResponse(BaseModel):
    """批量 Summary 响应"""
    success: bool
    message: str
    total: int
    parallel_count: int


@router.post("/summary-all", response_model=SummaryAllResponse)
async def summary_all(request: SummaryAllRequest):
    """
    批量执行 Summary（对所有已完成 PageIndex 的文档）

    - **parallel_count**: 并行数量（默认 1）
    - **api_key**: LLM API Key（可选）
    - **base_url**: LLM API URL（可选）
    - **model**: 模型名（可选）
    """
    import json as json_module
    from pathlib import Path as PathLib

    try:
        # Query documents with page_index_status = 'indexed'
        from smartcard_kb.docs_compile.database import get_connection
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(
            "SELECT * FROM doc_info WHERE page_index_status = 'indexed' ORDER BY created_at DESC"
        )
        docs = [dict(row) for row in cursor.fetchall()]
        cursor.close()
        conn.close()

        if not docs:
            return SummaryAllResponse(
                success=True,
                message="没有已完成 PageIndex 的文档",
                total=0,
                parallel_count=request.parallel_count,
            )

        api_key = request.api_key or settings.openai_api_key
        base_url = request.base_url or settings.openai_base_url
        model = request.model or settings.openai_model

        if not api_key or not base_url:
            raise HTTPException(status_code=400, detail="未配置 LLM API")

        semaphore = asyncio.Semaphore(request.parallel_count)
        success_count = 0
        fail_count = 0

        async def summarize_one(doc):
            nonlocal success_count, fail_count
            async with semaphore:
                doc_id = doc["id"]
                pdf_path = doc.get("file_path", "")
                if not pdf_path:
                    logger.warning(f"Skip {doc_id}: file_path empty")
                    fail_count += 1
                    return
                pdf_path = resolve_file(pdf_path)
                if not PathLib(pdf_path).exists():
                    logger.warning(f"Skip summary for {doc_id}: PDF not found")
                    fail_count += 1
                    return

                skeleton_path = Path("output") / "toc" / doc_id / "skeleton.json"
                if not skeleton_path.exists():
                    logger.warning(f"Skip summary for {doc_id}: skeleton.json not found")
                    fail_count += 1
                    return

                try:
                    t0 = time.time()

                    # Read skeleton
                    with open(skeleton_path, "r", encoding="utf-8") as f:
                        skeleton = json_module.load(f)

                    # Extract text per chapter using PyMuPDF
                    import fitz
                    pdf_doc = fitz.open(pdf_path)
                    total_pages = len(pdf_doc)

                    def flatten_nodes(nodes, result=None):
                        if result is None:
                            result = []
                        for node in nodes:
                            result.append(node)
                            if node.get("children"):
                                flatten_nodes(node["children"], result)
                        return result

                    all_nodes = flatten_nodes(skeleton)
                    summaries = []

                    for i, node in enumerate(all_nodes):
                        start_page = node.get("page", 1)
                        if i + 1 < len(all_nodes):
                            end_page = all_nodes[i + 1].get("page", total_pages) - 1
                        else:
                            end_page = total_pages

                        start_page = max(1, min(start_page, total_pages))
                        end_page = max(start_page, min(end_page, total_pages))

                        text_parts = []
                        for p in range(start_page - 1, end_page):
                            page_text = pdf_doc[p].get_text("text").strip()
                            if page_text:
                                text_parts.append(page_text)

                        chapter_text = "\n".join(text_parts)
                        if not chapter_text:
                            summaries.append({
                                "number": node.get("number", ""),
                                "title": node.get("title", ""),
                                "level": node.get("level", 1),
                                "page": start_page,
                                "summary": "",
                                "error": "无文本内容",
                            })
                            continue

                        if len(chapter_text) > 8000:
                            chapter_text = chapter_text[:8000] + "\n[... 文本已截断 ...]"

                        try:
                            import httpx
                            url = base_url.rstrip("/")
                            if not url.endswith("/chat/completions"):
                                url = f"{url}/chat/completions"

                            llm_payload = {
                                "model": model,
                                "messages": [
                                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                                    {"role": "user", "content": f"请为以下章节生成摘要：\n\n章节标题：{node.get('number', '')} {node.get('title', '')}\n\n章节内容：\n{chapter_text}"},
                                ],
                                "temperature": 0.3,
                            }

                            headers = {
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json",
                            }

                            with httpx.Client(timeout=120.0) as client:
                                resp = client.post(url, headers=headers, json=llm_payload)

                            if resp.status_code >= 400:
                                raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text[:200]}")

                            result = resp.json()
                            summary_text = result["choices"][0]["message"]["content"].strip()

                            summaries.append({
                                "number": node.get("number", ""),
                                "title": node.get("title", ""),
                                "level": node.get("level", 1),
                                "page": start_page,
                                "summary": summary_text,
                            })
                        except Exception as e:
                            logger.error(f"Summary failed for node '{node.get('title', '')}' in {doc_id}: {e}")
                            summaries.append({
                                "number": node.get("number", ""),
                                "title": node.get("title", ""),
                                "level": node.get("level", 1),
                                "page": start_page,
                                "summary": "",
                                "error": str(e),
                            })

                    pdf_doc.close()

                    # Save summaries
                    output_dir = Path("output") / "toc" / doc_id
                    output_dir.mkdir(parents=True, exist_ok=True)
                    summary_path = output_dir / "summaries.json"
                    with open(summary_path, "w", encoding="utf-8") as f:
                        json_module.dump(summaries, f, ensure_ascii=False, indent=2)

                    elapsed = time.time() - t0
                    success_chapters = sum(1 for s in summaries if s.get("summary"))
                    logger.info(f"Summary for {doc_id}: {success_chapters}/{len(summaries)} chapters in {elapsed:.1f}s")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Summary failed for {doc_id}: {e}")
                    fail_count += 1

        tasks = [summarize_one(doc) for doc in docs]
        await asyncio.gather(*tasks)

        return SummaryAllResponse(
            success=True,
            message=f"完成: {success_count} 成功, {fail_count} 失败",
            total=len(docs),
            parallel_count=request.parallel_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch Summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"批量 Summary 失败: {str(e)}")
