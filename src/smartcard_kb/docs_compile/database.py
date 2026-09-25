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
    """初始化数据库，创建 document_item 和 document_info 表"""
    conn = get_connection()
    cursor = conn.cursor()

    # 创建 document_info 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_info (
            id TEXT PRIMARY KEY,
            document_code TEXT,
            title TEXT,
            series_id TEXT,
            file_name TEXT NOT NULL,
            file_path TEXT,
            file_hash TEXT,
            file_size INTEGER,
            file_format TEXT,
            page_count INTEGER,
            revision TEXT,
            publication_date TEXT,
            effective_date TEXT,
            issuer TEXT,
            language TEXT,
            source_type TEXT,
            parser TEXT,
            parser_version TEXT,
            processing_status TEXT,
            processing_started_at TEXT,
            processing_finished_at TEXT,
            processing_error TEXT,
            item_count INTEGER DEFAULT 0,
            text_count INTEGER DEFAULT 0,
            title_count INTEGER DEFAULT 0,
            table_count INTEGER DEFAULT 0,
            picture_count INTEGER DEFAULT 0,
            formula_count INTEGER DEFAULT 0,
            metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # document_info 表索引
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_info_document_code
        ON document_info(document_code)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_info_series_id
        ON document_info(series_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_info_processing_status
        ON document_info(processing_status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_info_file_hash
        ON document_info(file_hash)
    """)

    # 创建 document_item 表
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
            textualization TEXT,
            raw_json JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 创建 document_item 表索引以提高查询性能
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

    # 为已存在的表添加 textualization 字段（如果不存在）
    cursor.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'document_item' AND column_name = 'textualization'
            ) THEN
                ALTER TABLE document_item ADD COLUMN textualization TEXT;
            END IF;
        END $$;
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


def update_item_textualization(item_id: str, textualization: str) -> None:
    """
    更新 item 的 textualization 字段

    :param item_id: item ID
    :param textualization: 文本化内容
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE document_item 
        SET textualization = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (textualization, item_id))

    conn.commit()
    cursor.close()
    conn.close()


def query_items_needing_textualization(
    document_id: Optional[str] = None,
    label: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    查询需要文本化的 item（textualization 为 NULL 的记录）

    :param document_id: 文档 ID（可选）
    :param label: 类型（可选）
    :param limit: 返回数量限制
    :return: 需要文本化的 item 列表
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    conditions = ["textualization IS NULL"]
    params = []

    if document_id is not None:
        conditions.append("document_id = %s")
        params.append(document_id)
    if label is not None:
        conditions.append("label = %s")
        params.append(label)

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT * FROM document_item 
        WHERE {where_clause} 
        ORDER BY order_index 
        LIMIT %s
    """
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = [dict(row) for row in rows]

    cursor.close()
    conn.close()
    return results


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


# ==================== document_info 表操作 ====================


def insert_document_info(doc_info: Dict[str, Any]) -> None:
    """
    插入或更新 document_info 记录

    :param doc_info: 包含所有字段的字典
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO document_info (
            id, document_code, title, series_id,
            file_name, file_path, file_hash, file_size, file_format, page_count,
            revision, publication_date, effective_date, issuer, language,
            source_type, parser, parser_version,
            processing_status, processing_started_at, processing_finished_at, processing_error,
            item_count, text_count, title_count, table_count, picture_count, formula_count,
            metadata, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            document_code = EXCLUDED.document_code,
            title = EXCLUDED.title,
            series_id = EXCLUDED.series_id,
            file_name = EXCLUDED.file_name,
            file_path = EXCLUDED.file_path,
            file_hash = EXCLUDED.file_hash,
            file_size = EXCLUDED.file_size,
            file_format = EXCLUDED.file_format,
            page_count = EXCLUDED.page_count,
            revision = EXCLUDED.revision,
            publication_date = EXCLUDED.publication_date,
            effective_date = EXCLUDED.effective_date,
            issuer = EXCLUDED.issuer,
            language = EXCLUDED.language,
            source_type = EXCLUDED.source_type,
            parser = EXCLUDED.parser,
            parser_version = EXCLUDED.parser_version,
            processing_status = EXCLUDED.processing_status,
            processing_started_at = EXCLUDED.processing_started_at,
            processing_finished_at = EXCLUDED.processing_finished_at,
            processing_error = EXCLUDED.processing_error,
            item_count = EXCLUDED.item_count,
            text_count = EXCLUDED.text_count,
            title_count = EXCLUDED.title_count,
            table_count = EXCLUDED.table_count,
            picture_count = EXCLUDED.picture_count,
            formula_count = EXCLUDED.formula_count,
            metadata = EXCLUDED.metadata,
            updated_at = CURRENT_TIMESTAMP
    """, (
        doc_info.get("id"),
        doc_info.get("document_code"),
        doc_info.get("title"),
        doc_info.get("series_id"),
        doc_info.get("file_name"),
        doc_info.get("file_path"),
        doc_info.get("file_hash"),
        doc_info.get("file_size"),
        doc_info.get("file_format"),
        doc_info.get("page_count"),
        doc_info.get("revision"),
        doc_info.get("publication_date"),
        doc_info.get("effective_date"),
        doc_info.get("issuer"),
        doc_info.get("language"),
        doc_info.get("source_type"),
        doc_info.get("parser"),
        doc_info.get("parser_version"),
        doc_info.get("processing_status"),
        doc_info.get("processing_started_at"),
        doc_info.get("processing_finished_at"),
        doc_info.get("processing_error"),
        doc_info.get("item_count", 0),
        doc_info.get("text_count", 0),
        doc_info.get("title_count", 0),
        doc_info.get("table_count", 0),
        doc_info.get("picture_count", 0),
        doc_info.get("formula_count", 0),
        json.dumps(doc_info.get("metadata")) if doc_info.get("metadata") else None,
        datetime.now().isoformat(),
        datetime.now().isoformat(),
    ))

    conn.commit()
    cursor.close()
    conn.close()


def query_document_info(
    document_id: Optional[str] = None,
    document_code: Optional[str] = None,
    series_id: Optional[str] = None,
    processing_status: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    查询 document_info 记录

    :param document_id: 文档 ID
    :param document_code: 文档编号
    :param series_id: 系列 ID
    :param processing_status: 处理状态
    :param file_hash: 文件哈希
    :return: 查询结果列表
    """
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    conditions = []
    params = []

    if document_id is not None:
        conditions.append("id = %s")
        params.append(document_id)
    if document_code is not None:
        conditions.append("document_code = %s")
        params.append(document_code)
    if series_id is not None:
        conditions.append("series_id = %s")
        params.append(series_id)
    if processing_status is not None:
        conditions.append("processing_status = %s")
        params.append(processing_status)
    if file_hash is not None:
        conditions.append("file_hash = %s")
        params.append(file_hash)

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    query = f"SELECT * FROM document_info WHERE {where_clause} ORDER BY created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        item = dict(row)
        # 反序列化 JSON 字段
        if item.get("metadata"):
            try:
                item["metadata"] = json.loads(item["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(item)

    cursor.close()
    conn.close()
    return results


def update_document_info_stats(
    document_id: str,
    stats: Dict[str, int]
) -> None:
    """
    更新文档统计信息（缓存字段）

    :param document_id: 文档 ID
    :param stats: 统计信息字典，例如 {"item_count": 48, "text_count": 13, ...}
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE document_info SET
            item_count = %s,
            text_count = %s,
            title_count = %s,
            table_count = %s,
            picture_count = %s,
            formula_count = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """, (
        stats.get("item_count", 0),
        stats.get("text_count", 0),
        stats.get("title_count", 0),
        stats.get("table_count", 0),
        stats.get("picture_count", 0),
        stats.get("formula_count", 0),
        document_id,
    ))

    conn.commit()
    cursor.close()
    conn.close()


def delete_document_info(document_id: str) -> int:
    """
    删除文档信息及其关联的 document_items

    :param document_id: 文档 ID
    :return: 删除的记录数
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 先删除关联的 document_items
    cursor.execute("DELETE FROM document_item WHERE document_id = %s", (document_id,))

    # 再删除 document_info
    cursor.execute("DELETE FROM document_info WHERE id = %s", (document_id,))
    count = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()

    return count
