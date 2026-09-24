"""数据库模块 - document_item 表的建表和 CRUD 操作"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime


def get_db_path() -> Path:
    """获取数据库路径"""
    return Path("data/knowledge.db")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化数据库，创建 document_item 表"""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
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
            bbox TEXT,
            metadata TEXT,
            content TEXT,
            is_rag_enabled BOOLEAN DEFAULT 1,
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    conn.close()


def insert_document_item(item: Dict[str, Any]) -> None:
    """
    插入单个 document_item
    
    :param item: 包含所有字段的字典
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO document_item (
            id, document_id, page_id, parent_id, label, text,
            order_index, bbox, metadata, content, is_rag_enabled,
            raw_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    conn.close()


def insert_document_items(items: List[Dict[str, Any]]) -> None:
    """
    批量插入 document_items
    
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

    cursor.executemany("""
        INSERT OR REPLACE INTO document_item (
            id, document_id, page_id, parent_id, label, text,
            order_index, bbox, metadata, content, is_rag_enabled,
            raw_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data)

    conn.commit()
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
    cursor = conn.cursor()

    conditions = []
    params = []

    if document_id is not None:
        conditions.append("document_id = ?")
        params.append(document_id)
    if page_id is not None:
        conditions.append("page_id = ?")
        params.append(page_id)
    if label is not None:
        conditions.append("label = ?")
        params.append(label)
    if is_rag_enabled is not None:
        conditions.append("is_rag_enabled = ?")
        params.append(1 if is_rag_enabled else 0)

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    query = f"SELECT * FROM document_item WHERE {where_clause} ORDER BY {order_by}"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        item = dict(row)
        # 反序列化 JSON 字段
        if item.get("bbox"):
            item["bbox"] = json.loads(item["bbox"])
        if item.get("metadata"):
            item["metadata"] = json.loads(item["metadata"])
        if item.get("content"):
            item["content"] = json.loads(item["content"])
        if item.get("raw_json"):
            item["raw_json"] = json.loads(item["raw_json"])
        results.append(item)

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

    cursor.execute("DELETE FROM document_item WHERE document_id = ?", (document_id,))
    count = cursor.rowcount

    conn.commit()
    conn.close()

    return count
