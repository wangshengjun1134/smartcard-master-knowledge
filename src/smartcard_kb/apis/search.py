"""检索 API 接口"""

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from smartcard_kb.logger import logger
from smartcard_kb.docs_compile.search_service import SearchService
from smartcard_kb.docs_compile.embedding_service import EmbeddingService
from smartcard_kb.llms.reranker_local import LocalRerankerBackend
from smartcard_kb.config import settings

router = APIRouter(prefix="/api", tags=["文档检索"])


# ==================== 全局模型实例（单例，启动时加载一次） ====================

_embedding_backend = None
_reranker_backend = None
_search_service = None


def _get_search_service() -> SearchService:
    """获取 SearchService 单例，首次调用时初始化"""
    global _embedding_backend, _reranker_backend, _search_service

    if _search_service is None:
        logger.info("正在加载 Embedding 模型...")
        _embedding_backend = EmbeddingService.create_backend(
            backend_type="local",
            model_name=settings.embedding_model,
        )

        _reranker_backend = None
        try:
            logger.info("正在加载 Reranker 模型...")
            _reranker_backend = LocalRerankerBackend(model_path=settings.reranker_model)
            logger.info("Reranker 模型加载完成")
        except Exception as e:
            logger.warning(f"Warning: 重排模型加载失败: {e}")

        _search_service = SearchService(
            embedding_backend=_embedding_backend,
            reranker_backend=_reranker_backend,
        )
        logger.info("检索服务初始化完成")

    return _search_service


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
        service = _get_search_service()

        result = service.search(
            query=request.query,
            document_id=request.document_id,
            search_type=request.search_type,
            top_k=request.top_k,
            rerank_top_k=request.rerank_top_k,
            threshold=request.threshold,
            enable_rerank=request.enable_rerank,
        )

        logger.info(
            f"Search completed: query='{request.query}', "
            f"total={result['total']}, "
            f"reranked={result['reranked']}, "
            f"top_score={result['results'][0]['score']:.4f if result['results'] else 0}"
        )

        return SearchResponse(
            query=result["query"],
            total=result["total"],
            results=result["results"],
            reranked=result["reranked"],
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")
