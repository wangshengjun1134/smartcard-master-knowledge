"""Embedding 服务模块 - 负责为 Chunk 生成向量嵌入"""

import json
from typing import List, Dict, Any, Optional

from .database import query_chunks, get_connection
from ..llms.embedding_base import EmbeddingBackend
from ..llms.embedding_openai import OpenAIEmbeddingBackend
from ..llms.embedding_local import LocalEmbeddingBackend


class EmbeddingService:
    """负责为 Chunk 生成向量嵌入"""

    def __init__(self, embedding_backend: Optional[EmbeddingBackend] = None, embedding_config: Optional[Dict[str, Any]] = None):
        """
        初始化 Embedding 服务

        :param embedding_backend: Embedding 后端实例
        :param embedding_config: Embedding 配置字典
        """
        self.embedding_backend = embedding_backend
        if self.embedding_backend is None and embedding_config is not None:
            self.embedding_backend = self._create_embedding_backend(embedding_config)

    def _create_embedding_backend(self, config: Dict[str, Any]) -> EmbeddingBackend:
        """根据配置创建 Embedding 后端"""
        backend_type = config.get("backend_type", "openai")
        if backend_type == "openai":
            return OpenAIEmbeddingBackend(
                api_key=config.get("openai_api_key", ""),
                base_url=config.get("openai_base_url", ""),
                model=config.get("openai_model", "text-embedding-3-small"),
            )
        elif backend_type == "local":
            return LocalEmbeddingBackend(
                model_name=config.get("model_name", "sentence-transformers/all-MiniLM-L6-v2"),
            )
        else:
            raise ValueError(f"不支持的 Embedding 后端类型: {backend_type}")

    def generate_embeddings(
        self,
        document_id: str,
    ) -> Dict[str, Any]:
        """
        为指定文档的所有 Chunk 生成向量嵌入

        :param document_id: 文档 ID
        :return: 处理结果统计
        """
        if self.embedding_backend is None:
            raise ValueError("Embedding 后端未初始化，请提供 embedding_backend 或 embedding_config")

        # 查询所有 chunk
        chunks = query_chunks(document_id=document_id)

        processed_count = 0
        failed_chunks = []

        for chunk in chunks:
            chunk_id = chunk.get("id")
            chunk_text = chunk.get("text")

            if not chunk_text or not chunk_text.strip():
                print(f"Warning: Chunk {chunk_id} 没有文本内容，跳过")
                failed_chunks.append(chunk_id)
                continue

            # 检查是否已有 embedding
            if chunk.get("embedding"):
                processed_count += 1
                continue

            try:
                embedding = self._generate_embedding(chunk_text)

                if embedding:
                    self._update_chunk_embedding(chunk_id, embedding)
                    processed_count += 1
                    print(f"Success: Chunk {chunk_id} embedding 已更新")
                else:
                    failed_chunks.append(chunk_id)
            except Exception as e:
                print(f"Error: Chunk {chunk_id} embedding 生成失败: {e}")
                failed_chunks.append(chunk_id)

        return {
            "document_id": document_id,
            "processed": processed_count,
            "failed": len(failed_chunks),
            "failed_chunk_ids": failed_chunks,
        }

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """调用 Embedding 后端生成向量"""
        try:
            return self.embedding_backend.embed(text=text)
        except Exception as e:
            print(f"Warning: Embedding 生成失败: {e}")
            return None

    def _update_chunk_embedding(self, chunk_id: str, embedding: List[float]) -> None:
        """更新 chunk 的 embedding 字段（存储为 JSON 字节）"""
        conn = get_connection()
        cursor = conn.cursor()
        
        # 将 float 列表转换为 JSON 字节存储
        embedding_json = json.dumps(embedding)
        embedding_bytes = embedding_json.encode('utf-8')
        
        cursor.execute("""
            UPDATE doc_chunks
            SET embedding = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (embedding_bytes, chunk_id))
        conn.commit()
        cursor.close()
        conn.close()
