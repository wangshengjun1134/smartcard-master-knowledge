"""文档处理 API 接口 - 解析、VLM 增强、分块、Embedding（异步）"""

import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from smartcard_kb.docs_compile.pdf_parser import PDFParser
from smartcard_kb.docs_compile.vlm_service import VLMService
from smartcard_kb.docs_compile.embedding_service import EmbeddingService
from smartcard_kb.docs_compile.chunker import Chunker
from smartcard_kb.docs_compile.database import update_document_info, get_document_stats
from smartcard_kb.config import settings

router = APIRouter(prefix="/api/docs", tags=["文档处理流程"])


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


class VLMRequest(BaseModel):
    """VLM 增强请求"""
    document_id: str
    output_dir: str = "output/pictures"
    backend_type: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    prompt: str = "请详细描述这张图片的内容，包括所有技术细节、图表数据、流程步骤等。如果是流程图或架构图，请说明各个组件之间的关系。"
    max_new_tokens: int = 512


class VLMResponse(BaseModel):
    """VLM 响应"""
    success: bool
    message: str


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

        parser = PDFParser(do_ocr=do_ocr)
        result = parser.parse_pdf(
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


async def _async_vlm(
    document_id: str,
    output_dir: str,
    backend_type: str,
    api_key: Optional[str],
    base_url: Optional[str],
    model: Optional[str],
    prompt: str,
    max_new_tokens: int,
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

        # 创建后端并初始化服务
        backend = VLMService.create_backend(
            backend_type=backend_type,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=resolved_model,
        )
        service = VLMService(vlm_backend=backend)
        result = service.generate_vlm_descriptions(
            document_id=document_id,
            output_dir=output_dir,
            prompt=prompt,
            max_new_tokens=max_new_tokens,
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

        chunker = Chunker(
            do_ocr=do_ocr,
            max_tokens=max_tokens,
            tokenizer_name=tokenizer_name,
        )
        result = chunker.generate_chunks(
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

        # 创建后端并初始化服务
        backend = EmbeddingService.create_backend(
            backend_type=backend_type,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            model=resolved_model,
            model_name=resolved_model_name,
        )
        service = EmbeddingService(embedding_backend=backend)
        result = service.generate_embeddings(document_id=document_id)

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
    """
    if not request.api_key and not settings.vlm_openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="VLM API Key 未配置。请设置环境变量 VLM_OPENAI_API_KEY 或在请求中传入 api_key。"
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
    )
    return VLMResponse(
        success=True,
        message="VLM 增强任务已提交，正在后台处理",
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
