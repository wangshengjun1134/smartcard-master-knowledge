"""数据库模块 - PostgreSQL 版本的 document_item 表 CRUD 操作"""

import json
from typing import Optional, List, Dict, Any
from datetime import datetime

import psycopg2
import psycopg2.extras
from psycopg2.extras import execute_values

from smartcard_kb.config import settings


def get_connection():
    """获取 PostgreSQL 数据库连接"""
    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )
    return conn


def init_database():
    """初始化数据库，创建 document_item 表"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_item (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            page_id TEXT NOT NULL,
            parent_id TEXT,
            label TEXT NOT NULL,
            text TEXT,
            order_index INTEGER NOT NULL,
            bbox JSONB,
            metadata JSONB,
            content JSONB,
            is_rag_enabled BOOLEAN DEFAULT TRUE,
            raw_json JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建索引以提高查询性能
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_item_document_id 
        ON document_item(document_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_item_page_id 
        ON document_item(page_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_item_label 
        ON document_item(label)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_item_is_rag_enabled 
        ON document_item(is_rag_enabled)
    """)

    conn.commit()
    cursor.close()
    conn.close()


def insert_document_item(item: Dict[str, Any]) -> None:
    """
    插入单个 document_item
    
    :param item: 包含所有字段的字典
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO document_item (
            id, document_id, page_id, parent_id, label, text,
            order_index, bbox, metadata, content, is_rag_enabled,
            raw_json, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            text = EXCLUDED.text,
            content = EXCLUDED.content,
            updated_at = CURRENT_TIMESTAMP
    """, (
        item.get("id"),
        item.get("document_id"),
        item.get("page_id"),
        item.get("parent_id"),
        item.get("label"),
        item.get("text"),
        item.get("order_index"),
        json.dumps(item.get("bbox")) if item.get("bbox") else None,
        json.dumps(item.get("metadata")) if item.get("metadata") else None,
        json.dumps(item.get("content")) if item.get("content") else None,
        item.get("is_rag_enabled", True),
        json.dumps(item.get("raw_json")) if item.get("raw_json") else None,
        datetime.now().isoformat(),
        datetime.now().isoformat(),
    ))

    conn.commit()
    cursor.close()
    conn.close()


def insert_document_items(items: List[Dict[str, Any]]) -> None:
    """
    批量插入 document_items（使用 execute_values 提高性能）
    
    :param items: document_item 字典列表
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    data = []
    for item in items:
        data.append((
            item.get("id"),
            item.get("document_id"),
            item.get("page_id"),
            item.get("parent_id"),
            item.get("label"),
            item.get("text"),
            item.get("order_index"),
            json.dumps(item.get("bbox")) if item.get("bbox") else None,
            json.dumps(item.get("metadata")) if item.get("metadata") else None,
            json.dumps(item.get("content")) if item.get("content") else None,
            item.get("is_rag_enabled", True),
            json.dumps(item.get("raw_json")) if item.get("raw_json") else None,
            now,
            now,
        ))

    execute_values(
        cursor,
        """
        INSERT INTO document_item (
            id, document_id, page_id, parent_id, label, text,
            order_index, bbox, metadata, content, is_rag_enabled,
            raw_json, created_at, updated_at
        ) VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            text = EXCLUDED.text,
            content = EXCLUDED.content,
            updated_at = CURRENT_TIMESTAMP
        """,
        data,
        template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
    )

    conn.commit()
    cursor.close()
    conn.close()


def query_document_items(
    document_id: Optional[str] = None,
    page_id: Optional[str] = None,
    label: Optional[str] = None,
    is_rag_enabled: Optional[bool] = None,
    order_by: str = "order_index"
) -> List[Dict[str, Any]]:
    """
    查询 document_items
    
    :param document_id: 文档 ID
    :param page_id: 页面 ID
    :param label: DocItemLabel 类型
    :param is_rag_enabled: 是否启用 RAG
    :param order_by: 排序字段
    :return: 查询结果列表
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    conditions = []
    params = []

    if document_id is not None:
        conditions.append("document_id = %s")
        params.append(document_id)
    if page_id is not None:
        conditions.append("page_id = %s")
        params.append(page_id)
    if label is not None:
        conditions.append("label = %s")
        params.append(label)
    if is_rag_enabled is not None:
        conditions.append("is_rag_enabled = %s")
        params.append(is_rag_enabled)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    query = f"SELECT * FROM document_item WHERE {where_clause} ORDER BY {order_by}"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        item = dict(row)
        # PostgreSQL JSONB 字段会自动解析为 Python 对象
        results.append(item)

    cursor.close()
    conn.close()
    return results


def delete_document_items_by_document(document_id: str) -> int:
    """
    删除指定文档的所有 item
    
    :param document_id: 文档 ID
    :return: 删除的记录数
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM document_item WHERE document_id = %s", (document_id,))
    count = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()

    return count


def get_document_stats(document_id: str) -> Dict[str, Any]:
    """
    获取文档统计信息
    
    :param document_id: 文档 ID
    :return: 统计信息字典
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            label,
            COUNT(*) as count
        FROM document_item
        WHERE document_id = %s
        GROUP BY label
        ORDER BY count DESC
    """, (document_id,))

    stats = {}
    for row in cursor.fetchall():
        stats[row[0]] = row[1]

    cursor.close()
    conn.close()

    return stats
