"""文档处理 API 接口 - 解析、VLM 增强、分块"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from smartcard_kb.docs_compile.pdf_parser import PDFParser
from smartcard_kb.docs_compile.vlm_service import VLMService
from smartcard_kb.docs_compile.chunker import Chunker
from smartcard_kb.config import settings

router = APIRouter(prefix="/api/docs", tags=["文档处理流程"])


# ==================== Pydantic 模型 ====================


class ParseRequest(BaseModel):
    """解析请求"""
    pdf_path: str
    document_id: str
    page_range: Optional[tuple] = None
    output_dir: str = "output/pictures"
    do_ocr: bool = True


class ParseResponse(BaseModel):
    """解析响应"""
    success: bool
    message: str
    item_count: int


class VLMRequest(BaseModel):
    """VLM 增强请求"""
    document_id: str
    output_dir: str = "output/pictures"
    backend_type: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "qwen-vl-max"
    prompt: str = "请详细描述这张图片的内容，包括所有技术细节、图表数据、流程步骤等。如果是流程图或架构图，请说明各个组件之间的关系。"
    max_new_tokens: int = 512


class VLMResponse(BaseModel):
    """VLM 响应"""
    success: bool
    message: str
    processed: int
    failed: int


class ChunkRequest(BaseModel):
    """分块请求"""
    pdf_path: str
    document_id: str
    page_range: Optional[tuple] = None
    max_tokens: int = 512
    tokenizer_name: str = "BAAI/bge-m3"
    do_ocr: bool = True


class ChunkResponse(BaseModel):
    """分块响应"""
    success: bool
    message: str
    chunk_count: int


# ==================== API 接口 ====================


@router.post("/process/parse", response_model=ParseResponse)
def parse_document(request: ParseRequest):
    """
    解析 PDF 文档并保存 Items

    - **pdf_path**: PDF 文件路径
    - **document_id**: 文档 ID
    - **page_range**: 页码范围 (start, end)，1-based（可选）
    - **output_dir**: 图片保存目录
    - **do_ocr**: 是否启用 OCR
    """
    try:
        parser = PDFParser(do_ocr=request.do_ocr)
        result = parser.parse_pdf(
            pdf_path=request.pdf_path,
            document_id=request.document_id,
            page_range=request.page_range,
            output_dir=request.output_dir,
        )
        return ParseResponse(
            success=True,
            message="PDF 解析完成",
            item_count=len(result.get("items", [])),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/process/vlm", response_model=VLMResponse)
def generate_vlm_descriptions(request: VLMRequest):
    """
    为文档的图片 Items 生成 VLM 描述

    - **document_id**: 文档 ID
    - **output_dir**: 图片保存目录
    - **backend_type**: VLM 后端类型（openai / local）
    - **api_key**: VLM API Key
    - **base_url**: VLM API 基础 URL
    - **model**: VLM 模型名称
    - **prompt**: VLM 提示词
    - **max_new_tokens**: 最大生成 token 数
    """
    try:
        vlm_config = {
            "backend_type": request.backend_type,
            "openai_api_key": request.api_key or settings.vlm_openai_api_key,
            "openai_base_url": request.base_url or settings.vlm_openai_base_url,
            "openai_model": request.model or settings.vlm_openai_model,
        }
        
        service = VLMService(vlm_config=vlm_config)
        result = service.generate_vlm_descriptions(
            document_id=request.document_id,
            output_dir=request.output_dir,
            prompt=request.prompt,
            max_new_tokens=request.max_new_tokens,
        )
        
        return VLMResponse(
            success=True,
            message="VLM 描述生成完成",
            processed=result["processed"],
            failed=result["failed"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VLM 生成失败: {str(e)}")


@router.post("/process/chunk", response_model=ChunkResponse)
def chunk_document(request: ChunkRequest):
    """
    对文档进行语义分块（自动注入 VLM 描述）

    - **pdf_path**: PDF 文件路径
    - **document_id**: 文档 ID
    - **page_range**: 页码范围 (start, end)，1-based（可选）
    - **max_tokens**: 分块最大 token 数
    - **tokenizer_name**: tokenizer 名称
    - **do_ocr**: 是否启用 OCR
    """
    try:
        chunker = Chunker(
            do_ocr=request.do_ocr,
            max_tokens=request.max_tokens,
            tokenizer_name=request.tokenizer_name,
        )
        result = chunker.generate_chunks(
            pdf_path=request.pdf_path,
            document_id=request.document_id,
            page_range=request.page_range,
        )
        
        return ChunkResponse(
            success=True,
            message="文档分块完成",
            chunk_count=len(result.get("chunks", [])),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分块失败: {str(e)}")
