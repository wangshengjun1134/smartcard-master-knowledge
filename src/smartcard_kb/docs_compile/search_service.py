"""检索服务模块 - 支持向量检索、关键词检索、混合检索和重排"""

import json
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from smartcard_kb.logger import logger

from .database import query_chunks
from ..llms.embedding_base import EmbeddingBackend
from ..llms.reranker_base import RerankerBackend


class SearchService:
    """检索服务"""

    def __init__(
        self,
        embedding_backend: EmbeddingBackend,
        reranker_backend: Optional[RerankerBackend] = None,
    ):
        """
        初始化检索服务

        :param embedding_backend: Embedding 后端（必需）
        :param reranker_backend: 重排后端（可选）
        """
        self.embedding_backend = embedding_backend
        self.reranker_backend = reranker_backend
        self.reranker_available = reranker_backend is not None

    def search(
        self,
        query: str,
        document_id: Optional[str] = None,
        search_type: str = "hybrid",
        top_k: int = 20,
        rerank_top_k: int = 10,
        threshold: float = 0.3,
        enable_rerank: bool = True,
    ) -> Dict[str, Any]:
        """
        执行检索
        
        :param query: 查询文本
        :param document_id: 文档 ID（可选，限定检索范围）
        :param search_type: 检索类型 (vector/keyword/hybrid)
        :param top_k: 初始召回数量
        :param rerank_top_k: 重排数量
        :param threshold: 相似度阈值
        :param enable_rerank: 是否启用重排
        :return: 检索结果
        """
        # 1. 获取所有 chunks
        all_chunks = query_chunks(document_id=document_id)
        
        if not all_chunks:
            return {
                "query": query,
                "total": 0,
                "results": [],
                "reranked": False,
            }

        # 2. 向量检索
        if search_type in ("vector", "hybrid"):
            results = self._vector_search(query, all_chunks, top_k, threshold)
        else:
            results = self._keyword_search(query, all_chunks, top_k)

        # 3. 重排
        reranked = False
        if enable_rerank and len(results) > 1:
            results, reranked = self._rerank(query, results, rerank_top_k, threshold)

        return {
            "query": query,
            "total": len(results),
            "results": results,
            "reranked": reranked,
        }

    def _vector_search(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int,
        threshold: float,
    ) -> List[Dict[str, Any]]:
        """向量检索"""
        # 生成查询向量
        query_embedding = self.embedding_backend.embed(query)
        query_vec = np.array(query_embedding)

        # 计算相似度
        scored_chunks = []
        for chunk in chunks:
            embedding_bytes = chunk.get("embedding")
            if not embedding_bytes:
                continue

            # 解析 embedding（JSON 字节格式）
            try:
                # PostgreSQL bytea 返回 memoryview，需要转换
                if isinstance(embedding_bytes, memoryview):
                    embedding_bytes = embedding_bytes.tobytes()
                if isinstance(embedding_bytes, bytes):
                    embedding_json = embedding_bytes.decode('utf-8')
                else:
                    embedding_json = str(embedding_bytes)
                chunk_embedding = json.loads(embedding_json)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
                logger.warning(f"Warning: Failed to parse embedding for chunk {chunk.get('id')}: {e}")
                continue

            chunk_vec = np.array(chunk_embedding)

            # 计算余弦相似度
            similarity = self._cosine_similarity(query_vec, chunk_vec)

            if similarity >= threshold:
                scored_chunks.append({
                    **chunk,
                    "score": float(similarity),
                })

        # 按相似度降序排序
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)

        return scored_chunks[:top_k]

    def _keyword_search(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """关键词检索（简单的 TF-IDF 风格）"""
        from collections import Counter
        import re

        # 简单的分词
        def tokenize(text: str) -> List[str]:
            text = text.lower()
            # 英文单词
            words = re.findall(r'\b[a-z]{2,}\b', text)
            # 中文单字
            chinese_chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
            return words + chinese_chars

        query_tokens = set(tokenize(query))
        
        scored_chunks = []
        for chunk in chunks:
            chunk_text = chunk.get("text", "")
            chunk_tokens = tokenize(chunk_text)
            
            # 计算匹配分数
            match_count = sum(1 for token in chunk_tokens if token in query_tokens)
            if match_count > 0:
                # 简单的 BM25 风格分数
                score = match_count / max(len(query_tokens), 1)
                scored_chunks.append({
                    **chunk,
                    "score": float(score),
                })

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:top_k]

    def _rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        rerank_top_k: int,
        threshold: float,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """重排"""
        if len(results) <= 1:
            return results, False
        
        # 如果重排模型不可用，返回原始结果
        if not self.reranker_available or self.reranker_backend is None:
            return results, False

        # 提取文档文本
        documents = [r.get("text", "") for r in results]

        # 调用重排模型
        reranked_indices = self.reranker_backend.rerank(
            query=query,
            documents=documents,
            top_k=rerank_top_k,
        )

        # 构建重排后的结果
        new_results = []
        for original_idx, new_score in reranked_indices:
            if new_score >= threshold:
                result = results[original_idx].copy()
                result["score"] = float(new_score)
                new_results.append(result)

        return new_results, True

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(vec1, vec2) / (norm1 * norm2))
