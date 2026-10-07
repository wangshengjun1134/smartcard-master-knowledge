"""文档处理 API 接口 - 解析、VLM 增强、分块、Embedding（异步）"""

import asyncio
import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from smartcard_kb.docs_compile.pdf_parser import PDFParser
from smartcard_kb.docs_compile.vlm_service import VLMService
from smartcard_kb.docs_compile.embedding_service import EmbeddingService
from smartcard_kb.docs_compile.chunker import Chunker
from smartcard_kb.docs_compile.database import update_document_info, get_document_stats, query_documents_by_status, query_document_info
from smartcard_kb.config import settings

router = APIRouter(prefix="/api/docs", tags=["文档处理流程"])

# 全局锁：防止并发执行 parse-all / vlm-all
_parse_all_lock = asyncio.Lock()
_vlm_all_lock = asyncio.Lock()


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
    max_tokens: int = 512
    tokenizer_name: str = "BAAI/bge-m3"
    do_ocr: bool = True


class ChunkResponse(BaseModel):
    """分块响应"""
    success: bool
    message: str


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
        print(f"Error: Parse failed for {document_id}: {e}")
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
                    print(f"Error: file_path not found for document {document_id}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "parse_failed",
                        "processing_error": "file_path not found",
                    })
                    return

                print(f"Starting parse for document {document_id}: {doc.get('file_name', 'unknown')}")

                try:
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
                    print(f"Parse completed for document {document_id}")

                except Exception as e:
                    print(f"Error: Parse failed for document {document_id}: {e}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "parse_failed",
                        "processing_error": str(e),
                    })

        # 并发执行所有文档解析
        tasks = [_parse_single_doc(doc) for doc in docs]
        await asyncio.gather(*tasks)
        print(f"Batch parse completed: {len(docs)} documents processed")


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
        print(f"VLM completed for {document_id}: {result}")
    except Exception as e:
        print(f"Error: VLM failed for {document_id}: {e}")
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
            print("Error: VLM API Key not configured")
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

                print(f"Starting VLM for document {document_id}: {doc.get('file_name', 'unknown')}")

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
                    print(f"VLM completed for document {document_id}: {result}")

                except Exception as e:
                    print(f"Error: VLM failed for document {document_id}: {e}")
                    update_document_info({
                        "id": document_id,
                        "processing_status": "vlm_failed",
                        "processing_error": str(e),
                    })

        # 并发执行所有文档 VLM 增强
        tasks = [_vlm_single_doc(doc) for doc in docs]
        await asyncio.gather(*tasks)
        print(f"Batch VLM completed: {len(docs)} documents processed")


async def _async_chunk(
    pdf_path: str,
    document_id: str,
    page_range: Optional[tuple],
    max_tokens: int,
    tokenizer_name: str,
    do_ocr: bool,
):
    """异步分块"""
    try:
        update_document_info({
            "id": document_id,
            "processing_status": "chunking",
        })

        # 使用线程池执行同步阻塞操作，避免阻塞事件循环
        chunker = Chunker(
            do_ocr=do_ocr,
            max_tokens=max_tokens,
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
        print(f"Chunking completed for {document_id}: {len(result.get('chunks', []))} chunks")
    except Exception as e:
        print(f"Error: Chunking failed for {document_id}: {e}")
        update_document_info({
            "id": document_id,
            "processing_status": "chunk_failed",
            "processing_error": str(e),
        })


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
        print(f"Embedding completed for {document_id}: {result}")
    except Exception as e:
        print(f"Error: Embedding failed for {document_id}: {e}")
        update_document_info({
            "id": document_id,
            "processing_status": "embedding_failed",
            "processing_error": str(e),
        })


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
    doc_info = query_document_info(request.document_id)
    if not doc_info:
        raise HTTPException(status_code=404, detail=f"文档 {request.document_id} 不存在")
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
    - **max_tokens**: 分块最大 token 数
    - **tokenizer_name**: tokenizer 名称
    - **do_ocr**: 是否启用 OCR（仅对 PDF 有效）
    """
    background_tasks.add_task(
        _async_chunk,
        request.pdf_path,
        request.document_id,
        request.page_range,
        request.max_tokens,
        request.tokenizer_name,
        request.do_ocr,
    )
    return ChunkResponse(
        success=True,
        message="文档分块任务已提交，正在后台处理",
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
