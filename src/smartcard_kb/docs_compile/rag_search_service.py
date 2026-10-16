"""RAG 检索服务（v2）

实现 POST /api/v1/rag/search 的检索逻辑：
- scope 降维：先经 doc_info 解析 document_id，再过滤 doc_chunks（不做 join）
- page_id 复用 doc_chunks.page_nos
- vector / keyword / hybrid(RRF) 三路检索
- 重排
- options 投影

设计文档：docs/search-api-v2-design.md
"""

import json
from typing import List, Dict, Any, Optional

import psycopg2.extras

from smartcard_kb.logger import logger

from .database import get_connection, resolve_document_ids, query_document_info
from ..llms.embedding_base import EmbeddingBackend
from ..llms.reranker_base import RerankerBackend

# chunk 检索返回的列（不含 embedding_vec）
_CHUNK_COLS = (
    "id, document_id, chunk_index, text, headings, heading_path, "
    "linked_item_ids, page_nos, token_count, chunk_token_limit, tokenizer"
)

_JSON_FIELDS = ("headings", "linked_item_ids", "page_nos")

# RRF 融合常数
_RRF_K = 60

# HNSW 检索时的候选池大小（缓解带过滤检索的召回不足）
_HNSW_EF_SEARCH = 200


class RAGSearchService:
    """RAG 检索服务 v2"""

    def __init__(
        self,
        embedding_backend: EmbeddingBackend,
        reranker_backend: Optional[RerankerBackend] = None,
    ):
        self.embedding_backend = embedding_backend
        self.reranker_backend = reranker_backend

    # ==================== 主流程 ====================

    def search(
        self,
        *,
        queries: List[str],
        scope: Dict[str, Any],
        retrieval: Dict[str, Any],
        filters: Dict[str, Any],
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        scope = scope or {}
        retrieval = retrieval or {}
        filters = filters or {}
        options = options or {}

        self._validate(scope, retrieval, filters)

        # 1. scope -> document_ids
        document_ids = resolve_document_ids(
            series_ids=scope.get("series_id"),
            revisions=scope.get("revision"),
            language=filters.get("language"),
            version_policy=scope.get("version_policy", "all"),
        )

        explicit_ids = scope.get("document_id") or []
        if explicit_ids:
            if document_ids is None:
                document_ids = list(explicit_ids)
            else:
                document_ids = list(set(document_ids) & set(explicit_ids))

        # 2. chunk 级过滤条件
        page_ints = []
        for p in (filters.get("page_id") or []):
            try:
                page_ints.append(int(p))
            except (ValueError, TypeError):
                pass
        heading_path = filters.get("heading_path")

        # 3. 参数
        retrieval_type = retrieval.get("retrieval_type", "hybrid")
        top_k = int(retrieval.get("top_k", 50))
        threshold = retrieval.get("similarity_threshold")
        rerank_enabled = bool(retrieval.get("rerank_enabled", True))
        rerank_top_k = int(retrieval.get("rerank_top_k", 10))
        original_query_weight = int(retrieval.get("original_query_weight", 1))

        logger.info(
            f"RAG search: type={retrieval_type}, top_k={top_k}, queries={len(queries)}, "
            f"documents={len(document_ids) if document_ids is not None else 'all'}, "
            f"page_ids={page_ints}, heading_path={heading_path!r}, threshold={threshold}, "
            f"original_query_weight={original_query_weight}"
        )

        # 4. 多查询候选召回（每个查询保留各自的排名列表）
        per_query_candidates: List[List[Dict[str, Any]]] = []
        for i, query in enumerate(queries):
            query_label = "original" if i == 0 else f"rewritten_{i}"
            logger.info(f"Processing query {i+1}/{len(queries)} ({query_label}): {query!r}")

            if retrieval_type == "vector":
                candidates = self._vector_search(query, document_ids, page_ints, heading_path, top_k, threshold)
            elif retrieval_type == "keyword":
                candidates = self._keyword_search(query, document_ids, page_ints, heading_path, top_k)
            else:  # hybrid
                vec_hits = self._vector_search(query, document_ids, page_ints, heading_path, top_k, threshold)
                kw_hits = self._keyword_search(query, document_ids, page_ints, heading_path, top_k)
                candidates = self._rrf_fuse(vec_hits, kw_hits, top_k)
                logger.info(f"Hybrid RRF (query {i+1}): vector={len(vec_hits)}, keyword={len(kw_hits)}, fused={len(candidates)}")

            per_query_candidates.append(candidates)
            logger.info(f"Query {i+1} collected {len(candidates)} candidates")

        # 5. 跨查询 RRF 融合去重（方案 B：所有查询的候选一次性 RRF）
        total_entries = sum(len(c) for c in per_query_candidates)
        candidates = self._rrf_fuse_multi_query(per_query_candidates, top_k)
        logger.info(f"Multi-query RRF: {total_entries} candidate entries -> {len(candidates)} fused")

        # 6. 构造 rerank 查询（原始查询加权 + 改写查询）
        if queries:
            original_query = queries[0]
            rewritten_queries = queries[1:] if len(queries) > 1 else []
            rerank_query_parts = [original_query] * original_query_weight + rewritten_queries
            rerank_query = " ".join(rerank_query_parts)
        else:
            rerank_query = ""

        # 7. 重排
        reranked = False
        if rerank_enabled and self.reranker_backend is not None and len(candidates) > 1:
            candidates = self._rerank(rerank_query, candidates, rerank_top_k)
            reranked = True
        else:
            candidates = candidates[:rerank_top_k]

        if not candidates:
            logger.warning(f"RAG search: no results (queries={queries!r})")

        # 8. 补充文档信息 + 投影
        candidates = self._enrich_with_doc_info(candidates)
        results = [self._project(c, options) for c in candidates]

        return {
            "queries": queries,
            "total": len(results),
            "reranked": reranked,
            "profile": retrieval.get("search_profile", "default"),
            "results": results,
        }

    # ==================== 校验 ====================

    def _validate(self, scope: Dict[str, Any], retrieval: Dict[str, Any], filters: Dict[str, Any]) -> None:
        if scope.get("document_id") and scope.get("revision"):
            raise ValueError("document_id 与 revision 不能同时指定")

        if filters.get("label"):
            raise ValueError("label 过滤暂未支持（契约已预留）")

        rt = retrieval.get("retrieval_type", "hybrid")
        if rt not in ("vector", "keyword", "hybrid"):
            raise ValueError(f"retrieval_type 非法: {rt}")

        vp = scope.get("version_policy", "all")
        if vp not in ("all", "latest", "exact", "selected"):
            raise ValueError(f"version_policy 非法: {vp}")
        if vp in ("exact", "selected") and not scope.get("revision"):
            raise ValueError("version_policy=exact/selected 需要指定 revision")

        top_k = int(retrieval.get("top_k", 50))
        rerank_top_k = int(retrieval.get("rerank_top_k", 10))
        if rerank_top_k > top_k:
            raise ValueError("rerank_top_k 不能大于 top_k")

    # ==================== 过滤条件构建 ====================

    def _build_chunk_filters(
        self,
        document_ids: Optional[List[str]],
        page_ints: List[int],
        heading_path: Optional[str],
    ):
        """返回 (SQL 片段列表, 参数列表)"""
        clauses: List[str] = []
        params: List[Any] = []

        if document_ids is not None:
            clauses.append("document_id = ANY(%s)")
            params.append(document_ids)

        if page_ints:
            ors = []
            for p in page_ints:
                ors.append("page_nos @> %s::jsonb")
                params.append(json.dumps([p]))
            clauses.append("(" + " OR ".join(ors) + ")")

        if heading_path:
            clauses.append("heading_path ILIKE %s")
            params.append(f"%{heading_path}%")

        return clauses, params

    # ==================== 向量检索 ====================

    def _vector_search(
        self,
        query: str,
        document_ids: Optional[List[str]],
        page_ints: List[int],
        heading_path: Optional[str],
        top_k: int,
        threshold: Optional[float],
    ) -> List[Dict[str, Any]]:
        q_vec = json.dumps(self.embedding_backend.embed(query))
        clauses, clause_params = self._build_chunk_filters(document_ids, page_ints, heading_path)

        where = ["embedding_vec IS NOT NULL"] + clauses
        params: List[Any] = [q_vec]  # SELECT 中的 score 表达式
        params.extend(clause_params)
        if threshold is not None:
            where.append("1 - (embedding_vec <=> %s::vector) >= %s")
            params.extend([q_vec, float(threshold)])
        params.extend([q_vec, top_k])  # ORDER BY 与 LIMIT

        sql = f"""
            SELECT {_CHUNK_COLS},
                   1 - (embedding_vec <=> %s::vector) AS score
            FROM doc_chunks
            WHERE {' AND '.join(where)}
            ORDER BY embedding_vec <=> %s::vector
            LIMIT %s
        """
        # SELECT 的 %s 在 params[0]，ORDER BY 与 LIMIT 在末尾
        # 注意参数顺序：SELECT(q_vec) -> clauses -> threshold(q_vec, thr) -> order(q_vec) -> limit
        # 上面的 params 顺序与 SQL 中 %s 出现顺序一致
        # 但 SELECT 的占位符在 SQL 文本最前面，需要把 q_vec 放最前——已满足。
        # ORDER BY/LIMIT 的 q_vec、top_k 已 append 在末尾。OK。

        rows = self._execute_chunk_query(sql, params, set_hnsw=True)
        for r in rows:
            r["score_stage"] = "vector"
        logger.info(f"Vector search: {len(rows)} hits")
        return rows

    # ==================== 关键词检索 ====================

    def _keyword_search(
        self,
        query: str,
        document_ids: Optional[List[str]],
        page_ints: List[int],
        heading_path: Optional[str],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        clauses, clause_params = self._build_chunk_filters(document_ids, page_ints, heading_path)

        ts = "to_tsvector('simple', coalesce(text, ''))"
        tsq = "plainto_tsquery('simple', %s)"
        where = [f"{ts} @@ {tsq}"] + clauses
        params: List[Any] = [query]           # SELECT 的 ts_rank 查询
        params.append(query)                   # WHERE 的 @@ 查询
        params.extend(clause_params)
        params.append(top_k)                   # LIMIT

        sql = f"""
            SELECT {_CHUNK_COLS},
                   ts_rank({ts}, {tsq}) AS score
            FROM doc_chunks
            WHERE {' AND '.join(where)}
            ORDER BY score DESC
            LIMIT %s
        """
        rows = self._execute_chunk_query(sql, params, set_hnsw=False)
        for r in rows:
            r["score_stage"] = "keyword"
        logger.info(f"Keyword search: {len(rows)} hits")
        return rows

    # ==================== RRF 融合 ====================

    def _rrf_fuse(
        self,
        vec_hits: List[Dict[str, Any]],
        kw_hits: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        fused: Dict[str, float] = {}
        items: Dict[str, Dict[str, Any]] = {}

        for rank, hit in enumerate(vec_hits):
            cid = hit["id"]
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            items.setdefault(cid, hit)

        for rank, hit in enumerate(kw_hits):
            cid = hit["id"]
            fused[cid] = fused.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
            items.setdefault(cid, hit)

        ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        results = []
        for cid, fscore in ranked:
            item = dict(items[cid])
            item["score"] = fscore
            item["score_stage"] = "hybrid"
            results.append(item)
        return results

    def _rrf_fuse_multi_query(
        self,
        ranked_lists: List[List[Dict[str, Any]]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        跨查询 RRF 融合去重（方案 B）

        将每个查询的候选列表视为一个有序列表，按排名位置做 RRF 融合。
        同一 chunk 被多个查询命中时会累加分数，从而被自然提升。

        :param ranked_lists: 每个查询各自的有序候选列表
        :param top_k: 融合后保留数量
        :return: 融合去重后的候选列表
        """
        fused: Dict[str, float] = {}
        items: Dict[str, Dict[str, Any]] = {}

        for ranked in ranked_lists:
            for rank, hit in enumerate(ranked):
                cid = hit["id"]
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (_RRF_K + rank + 1)
                items.setdefault(cid, hit)

        ranked_items = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        results = []
        for cid, fscore in ranked_items:
            item = dict(items[cid])
            item["score"] = fscore
            item["score_stage"] = "hybrid"
            results.append(item)
        return results

    # ==================== 重排 ====================

    def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        documents = [c.get("text") or "" for c in candidates]
        pairs = self.reranker_backend.rerank(query=query, documents=documents, top_k=top_k)

        results = []
        for idx, score in pairs:
            item = dict(candidates[idx])
            item["score"] = float(score)
            item["score_stage"] = "rerank"
            results.append(item)
        logger.info(f"Rerank: {len(candidates)} -> {len(results)}")
        return results

    # ==================== 查询执行 ====================

    def _execute_chunk_query(
        self,
        sql: str,
        params: List[Any],
        set_hnsw: bool,
    ) -> List[Dict[str, Any]]:
        conn = get_connection()
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if set_hnsw:
                # 缓解带过滤向量检索的召回不足
                try:
                    cursor.execute(f"SET LOCAL hnsw.ef_search = {_HNSW_EF_SEARCH}")
                    cursor.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
                except Exception as e:
                    logger.warning(f"设置 hnsw 参数失败（忽略）: {e}")
            cursor.execute(sql, params)
            rows = []
            for row in cursor.fetchall():
                item = dict(row)
                for f in _JSON_FIELDS:
                    v = item.get(f)
                    if isinstance(v, str):
                        try:
                            item[f] = json.loads(v)
                        except (json.JSONDecodeError, TypeError):
                            item[f] = None
                rows.append(item)
            cursor.close()
            return rows
        finally:
            conn.close()

    # ==================== 文档信息补充 ====================

    def _enrich_with_doc_info(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        doc_ids = {r.get("document_id") for r in results if r.get("document_id")}
        doc_map: Dict[str, Dict[str, Any]] = {}
        for doc_id in doc_ids:
            docs = query_document_info(document_id=doc_id)
            if docs:
                d = docs[0]
                doc_map[doc_id] = {
                    "document_name": d.get("file_name", ""),
                    "document_code": d.get("document_code", ""),
                    "file_path": d.get("file_path", ""),
                    "series_id": d.get("series_id", ""),
                    "revision": d.get("revision", ""),
                    "language": d.get("language", ""),
                }
        for r in results:
            r.update(doc_map.get(r.get("document_id"), {}))
        return results

    # ==================== 响应投影 ====================

    def _project(self, c: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "chunk_id": c.get("id"),
            "document_id": c.get("document_id"),
            "chunk_index": c.get("chunk_index"),
            "score": c.get("score"),
            "score_stage": c.get("score_stage", "retrieval"),
        }

        if options.get("include_content", True):
            result["content"] = c.get("text")

        if options.get("include_metadata", True):
            result["metadata"] = {
                "headings": c.get("headings"),
                "heading_path": c.get("heading_path"),
                "page_nos": c.get("page_nos"),
                "token_count": c.get("token_count"),
                "chunk_token_limit": c.get("chunk_token_limit"),
                "chunk_tokenizer": c.get("tokenizer"),
            }

        if options.get("include_citations", True):
            result["citation"] = {
                "document_name": c.get("document_name"),
                "document_code": c.get("document_code"),
                "series_id": c.get("series_id"),
                "revision": c.get("revision"),
                "file_path": c.get("file_path"),
                "page_nos": c.get("page_nos"),
                "linked_item_ids": c.get("linked_item_ids"),
            }

        return result
