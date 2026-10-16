"""RAG 检索 API（v2）

端点：POST /api/v1/rag/search
设计文档：docs/search-api-v2-design.md
"""

import json
import re
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from smartcard_kb.logger import logger
from smartcard_kb.docs_compile.rag_search_service import RAGSearchService
# 复用现有单例中的 Embedding / Reranker 模型，避免重复加载
from .search import _get_search_service

router = APIRouter(prefix="/api/v1/rag", tags=["RAG 检索"])


def _parse_rewrite_output(content: str) -> List[str]:
    """
    Parse the LLM rewrite output into a list of query strings.

    Supports the JSON contract produced by the default rewrite prompt:
        {"queries": [{"query_id": "q1", "query": "...", "filters": {}, "purpose": "..."}]}
    Falls back to one-query-per-line parsing for plain-text responses.
    """
    text = (content or "").strip()

    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text.strip())

    # Try JSON first
    try:
        parsed = json.loads(text)
        items = parsed.get("queries") if isinstance(parsed, dict) else parsed
        queries: List[str] = []
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    q = item.get("query")
                    if q and str(q).strip():
                        queries.append(str(q).strip())
                elif isinstance(item, str) and item.strip():
                    queries.append(item.strip())
        if queries:
            return queries
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Fallback: one query per line
    return [line.strip() for line in text.split("\n") if line.strip()]


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
    original_query_weight: int = 1  # 原始查询在 rerank 时的权重（重复次数）


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
    queries: List[str]  # 第一个是原始查询，其余是改写查询
    scope: Scope = Field(default_factory=Scope)
    retrieval: Retrieval = Field(default_factory=Retrieval)
    filters: Filters = Field(default_factory=Filters)
    options: Options = Field(default_factory=Options)


class RAGSearchResponse(BaseModel):
    """RAG 检索响应"""
    queries: List[str]
    total: int
    reranked: bool
    profile: str
    results: List[Dict[str, Any]]


class RewriteRequest(BaseModel):
    """查询重写请求"""
    query: str
    api_url: str
    api_key: str
    model: str
    prompt: str


class RewriteResponse(BaseModel):
    """查询重写响应"""
    original_query: str
    rewritten_queries: List[str]


# ==================== API 接口 ====================


@router.post("/rewrite", response_model=RewriteResponse)
def rewrite_query(request: RewriteRequest):
    """
    查询重写 - 调用 LLM API 将单个查询改写为多个查询

    - **query**: 原始查询
    - **api_url**: LLM API 地址
    - **api_key**: API Key
    - **model**: 模型名称
    - **prompt**: 提示词模板
    """
    import httpx
    
    logger.debug(f"Rewrite request: query={request.query!r}, model={request.model}")
    
    try:
        # 构造 LLM 请求
        headers = {
            "Authorization": f"Bearer {request.api_key}",
            "Content-Type": "application/json",
        }
        
        # 构造消息：若提示词含 {query} 占位符则填入单条 user 消息，
        # 否则把提示词作为 system、原始问题作为 user（适配新版 JSON 提示词）
        if "{query}" in request.prompt:
            user_content = request.prompt.replace("{query}", request.query)
            messages = [{"role": "user", "content": user_content}]
        else:
            messages = [
                {"role": "system", "content": request.prompt},
                {"role": "user", "content": request.query},
            ]

        payload = {
            "model": request.model,
            "messages": messages,
            "temperature": 0.2,
        }

        # OpenAI 兼容协议：Base URL 后需追加 /chat/completions
        api_url = request.api_url.rstrip("/")
        if not api_url.endswith("/chat/completions"):
            api_url = f"{api_url}/chat/completions"

        # 调用 LLM API
        with httpx.Client(timeout=60.0) as client:
            response = client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()

        result = response.json()

        # 提取 LLM 响应内容（兼容 OpenAI 格式）
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
        else:
            raise ValueError(f"Unexpected LLM response format: {result}")

        # 解析改写查询（优先 JSON：{"queries":[{"query": "..."}]}，回退按行拆分）
        rewritten_queries = _parse_rewrite_output(content)

        if not rewritten_queries:
            rewritten_queries = [request.query]

        logger.info(f"Rewrite completed: {len(rewritten_queries)} queries generated")
        logger.debug(f"Rewritten queries: {rewritten_queries}")
        
        return RewriteResponse(
            original_query=request.query,
            rewritten_queries=rewritten_queries,
        )
        
    except httpx.HTTPError as e:
        logger.error(f"LLM API call failed: {e}")
        raise HTTPException(status_code=502, detail=f"LLM API 调用失败: {str(e)}")
    except Exception as e:
        logger.error(f"Rewrite failed: {e}")
        raise HTTPException(status_code=500, detail=f"查询重写失败: {str(e)}")


@router.post("/search", response_model=RAGSearchResponse)
def rag_search(request: RAGSearchRequest):
    """
    RAG 检索（v2）- 支持多查询融合

    - **queries**: 查询列表（第一个是原始查询，其余是改写查询）
    - **scope**: 范围（series_id / document_id / revision / version_policy）
    - **retrieval**: 策略（retrieval_type / top_k / rerank_* / similarity_threshold / search_profile / original_query_weight）
    - **filters**: 过滤（page_id / heading_path / label[预留] / language）
    - **options**: 返回裁剪（include_content / include_metadata / include_citations）
    """
    # Log request payload
    logger.debug(f"RAG search request: {request.model_dump_json()}")
    
    try:
        service = _get_rag_service()
        result = service.search(
            queries=request.queries,
            scope=request.scope.model_dump(),
            retrieval=request.retrieval.model_dump(),
            filters=request.filters.model_dump(),
            options=request.options.model_dump(),
        )
        
        response = RAGSearchResponse(**result)
        
        # Log response summary (not full content to avoid huge logs)
        result_summary = {
            "queries": response.queries,
            "total": response.total,
            "reranked": response.reranked,
            "profile": response.profile,
            "results_count": len(response.results),
            "top_scores": [r["score"] for r in response.results[:3]],
        }
        logger.debug(f"RAG search response: {result_summary}")
        logger.info(
            f"RAG search completed: queries={request.queries!r}, "
            f"total={result['total']}, reranked={result['reranked']}"
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")
