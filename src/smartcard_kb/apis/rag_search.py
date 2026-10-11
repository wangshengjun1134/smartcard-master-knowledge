"""RAG 检索 API（v2）

端点：POST /api/v1/rag/search
设计文档：docs/search-api-v2-design.md
"""

from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from smartcard_kb.logger import logger
from smartcard_kb.docs_compile.rag_search_service import RAGSearchService
# 复用现有单例中的 Embedding / Reranker 模型，避免重复加载
from .search import _get_search_service

router = APIRouter(prefix="/api/v1/rag", tags=["RAG 检索"])


_rag_service: Optional[RAGSearchService] = None


def _get_rag_service() -> RAGSearchService:
    """获取 RAGSearchService 单例（复用 search 模块已加载的模型）"""
    global _rag_service
    if _rag_service is None:
        base = _get_search_service()
        _rag_service = RAGSearchService(
            embedding_backend=base.embedding_backend,
            reranker_backend=base.reranker_backend,
        )
    return _rag_service


# ==================== 请求模型 ====================


class Scope(BaseModel):
    """检索范围"""
    series_id: List[str] = Field(default_factory=list)
    document_id: List[str] = Field(default_factory=list)
    revision: List[str] = Field(default_factory=list)
    version_policy: str = "all"  # all / latest / exact / selected


class Retrieval(BaseModel):
    """检索策略"""
    retrieval_type: str = "hybrid"  # vector / keyword / hybrid
    top_k: int = 50
    rerank_enabled: bool = True
    rerank_top_k: int = 10
    similarity_threshold: Optional[float] = None
    search_profile: str = "default"


class Filters(BaseModel):
    """内容过滤"""
    page_id: List[str] = Field(default_factory=list)
    heading_path: Optional[str] = None
    label: List[str] = Field(default_factory=list)  # 预留，v1 不支持
    language: Optional[str] = None


class Options(BaseModel):
    """返回选项"""
    include_content: bool = True
    include_metadata: bool = True
    include_citations: bool = True


class RAGSearchRequest(BaseModel):
    """RAG 检索请求"""
    query: str
    scope: Scope = Field(default_factory=Scope)
    retrieval: Retrieval = Field(default_factory=Retrieval)
    filters: Filters = Field(default_factory=Filters)
    options: Options = Field(default_factory=Options)


class RAGSearchResponse(BaseModel):
    """RAG 检索响应"""
    query: str
    total: int
    reranked: bool
    profile: str
    results: List[Dict[str, Any]]


# ==================== API 接口 ====================


@router.post("/search", response_model=RAGSearchResponse)
def rag_search(request: RAGSearchRequest):
    """
    RAG 检索（v2）

    - **query**: 检索问题
    - **scope**: 范围（series_id / document_id / revision / version_policy）
    - **retrieval**: 策略（retrieval_type / top_k / rerank_* / similarity_threshold / search_profile）
    - **filters**: 过滤（page_id / heading_path / label[预留] / language）
    - **options**: 返回裁剪（include_content / include_metadata / include_citations）
    """
    try:
        service = _get_rag_service()
        result = service.search(
            query=request.query,
            scope=request.scope.model_dump(),
            retrieval=request.retrieval.model_dump(),
            filters=request.filters.model_dump(),
            options=request.options.model_dump(),
        )
        logger.info(
            f"RAG search completed: query={request.query!r}, "
            f"total={result['total']}, reranked={result['reranked']}"
        )
        return RAGSearchResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")
