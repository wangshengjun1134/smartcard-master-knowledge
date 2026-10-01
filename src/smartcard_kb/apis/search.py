"""检索 API 接口"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from smartcard_kb.docs_compile.search_service import SearchService
from smartcard_kb.docs_compile.embedding_service import EmbeddingService
from smartcard_kb.llms.reranker_local import LocalRerankerBackend
from smartcard_kb.config import settings

router = APIRouter(prefix="/api", tags=["文档检索"])


# ==================== Pydantic 模型 ====================


class SearchRequest(BaseModel):
    """检索请求"""
    query: str
    document_id: Optional[str] = None
    search_type: str = "hybrid"  # vector, keyword, hybrid
    top_k: int = 20
    rerank_top_k: int = 10
    threshold: float = 0.3
    enable_rerank: bool = True


class SearchResult(BaseModel):
    """检索结果项"""
    id: str
    document_id: str
    chunk_index: int
    text: str
    score: float
    headings: list
    heading_path: str
    page_nos: list
    token_count: int
    linked_item_ids: list


class SearchResponse(BaseModel):
    """检索响应"""
    query: str
    total: int
    results: list[SearchResult]
    reranked: bool


# ==================== API 接口 ====================


@router.post("/search", response_model=SearchResponse)
def search_documents(request: SearchRequest):
    """
    检索文档

    - **query**: 查询文本
    - **document_id**: 文档 ID（可选，限定检索范围）
    - **search_type**: 检索类型 (vector/keyword/hybrid)
    - **top_k**: 初始召回数量
    - **rerank_top_k**: 重排数量
    - **threshold**: 相似度阈值
    - **enable_rerank**: 是否启用重排
    """
    try:
        # 创建 Embedding 后端（使用本地模型）
        embedding_backend = EmbeddingService.create_backend(
            backend_type="local",
            model_name=settings.embedding_model,
        )

        # 创建重排后端（可选）
        reranker_backend = None
        if request.enable_rerank:
            try:
                reranker_backend = LocalRerankerBackend(model_path=settings.reranker_model)
            except Exception as e:
                print(f"Warning: 重排模型加载失败: {e}")

        # 初始化检索服务
        service = SearchService(
            embedding_backend=embedding_backend,
            reranker_backend=reranker_backend,
        )

        result = service.search(
            query=request.query,
            document_id=request.document_id,
            search_type=request.search_type,
            top_k=request.top_k,
            rerank_top_k=request.rerank_top_k,
            threshold=request.threshold,
            enable_rerank=request.enable_rerank,
        )

        return SearchResponse(
            query=result["query"],
            total=result["total"],
            results=result["results"],
            reranked=result["reranked"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")
