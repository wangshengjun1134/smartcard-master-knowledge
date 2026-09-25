"""测试数据脚本 - 在数据库中添加测试文档信息"""

import sys
import uuid
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from smartcard_kb.docs_compile.database import (
    init_database,
    insert_document_info,
    query_document_info,
)


def create_test_data():
    """创建测试数据"""
    # 初始化数据库
    init_database()

    # 检查是否已有测试数据
    existing = query_document_info(document_code="TEST-001")
    if existing:
        print("⚠️  测试数据已存在，跳过创建")
        return

    # 测试文档列表
    test_docs = [
        {
            "id": str(uuid.uuid4()),
            "document_code": "TEST-001",
            "title": "Test Document 1 - eSIM Architecture",
            "series_id": "SGP",
            "file_name": "test_doc_1.pdf",
            "file_path": "specs/test/test_doc_1.pdf",
            "file_hash": "abc123def456",
            "file_size": 1024000,
            "file_format": "pdf",
            "page_count": 50,
            "revision": "A",
            "publication_date": "2024-01-15",
            "effective_date": "2024-02-01",
            "issuer": "GSMA",
            "language": "en",
            "source_type": "upload",
            "parser": "docling",
            "parser_version": "2.50.0",
            "processing_status": "completed",
            "processing_started_at": "2024-01-20T10:00:00",
            "processing_finished_at": "2024-01-20T10:05:00",
            "item_count": 120,
            "text_count": 80,
            "title_count": 25,
            "table_count": 10,
            "picture_count": 5,
            "formula_count": 0,
            "metadata": {
                "author": "Test Author",
                "department": "Engineering",
                "document_type": "standard",
            },
        },
        {
            "id": str(uuid.uuid4()),
            "document_code": "TEST-002",
            "title": "Test Document 2 - Security Requirements",
            "series_id": "SGP",
            "file_name": "test_doc_2.pdf",
            "file_path": "specs/test/test_doc_2.pdf",
            "file_hash": "def456ghi789",
            "file_size": 2048000,
            "file_format": "pdf",
            "page_count": 75,
            "revision": "B",
            "publication_date": "2024-03-10",
            "effective_date": "2024-04-01",
            "issuer": "GSMA",
            "language": "en",
            "source_type": "upload",
            "parser": "docling",
            "parser_version": "2.50.0",
            "processing_status": "completed",
            "processing_started_at": "2024-03-15T14:00:00",
            "processing_finished_at": "2024-03-15T14:10:00",
            "item_count": 200,
            "text_count": 150,
            "title_count": 35,
            "table_count": 10,
            "picture_count": 5,
            "formula_count": 0,
            "metadata": {
                "author": "Test Author 2",
                "department": "Security",
                "document_type": "standard",
            },
        },
        {
            "id": str(uuid.uuid4()),
            "document_code": "TEST-003",
            "title": "测试文档 3 - 智能卡规范",
            "series_id": "TEST",
            "file_name": "test_doc_3.pdf",
            "file_path": "specs/test/test_doc_3.pdf",
            "file_hash": "ghi789jkl012",
            "file_size": 512000,
            "file_format": "pdf",
            "page_count": 30,
            "revision": "1.0",
            "publication_date": "2024-05-20",
            "effective_date": "2024-06-01",
            "issuer": "测试机构",
            "language": "zh-CN",
            "source_type": "upload",
            "parser": "docling",
            "parser_version": "2.50.0",
            "processing_status": "pending",
            "item_count": 0,
            "text_count": 0,
            "title_count": 0,
            "table_count": 0,
            "picture_count": 0,
            "formula_count": 0,
            "metadata": {
                "author": "测试作者",
                "department": "研发部",
                "document_type": "standard",
            },
        },
        {
            "id": str(uuid.uuid4()),
            "document_code": "TEST-004",
            "title": "Test Document 4 - Processing Status",
            "series_id": "SGP",
            "file_name": "test_doc_4.pdf",
            "file_path": "specs/test/test_doc_4.pdf",
            "file_hash": "jkl012mno345",
            "file_size": 768000,
            "file_format": "pdf",
            "page_count": 40,
            "revision": "A",
            "publication_date": "2024-06-01",
            "effective_date": "2024-07-01",
            "issuer": "GSMA",
            "language": "en",
            "source_type": "upload",
            "parser": "docling",
            "parser_version": "2.50.0",
            "processing_status": "processing",
            "processing_started_at": datetime.now().isoformat(),
            "item_count": 50,
            "text_count": 30,
            "title_count": 15,
            "table_count": 5,
            "picture_count": 0,
            "formula_count": 0,
            "metadata": {
                "author": "Test Author",
                "document_type": "standard",
            },
        },
        {
            "id": str(uuid.uuid4()),
            "document_code": "TEST-005",
            "title": "Test Document 5 - Failed Processing",
            "series_id": "SGP",
            "file_name": "test_doc_5.pdf",
            "file_path": "specs/test/test_doc_5.pdf",
            "file_hash": "mno345pqr678",
            "file_size": 256000,
            "file_format": "pdf",
            "page_count": 20,
            "revision": "A",
            "publication_date": "2024-07-01",
            "effective_date": "2024-08-01",
            "issuer": "GSMA",
            "language": "en",
            "source_type": "upload",
            "parser": "docling",
            "parser_version": "2.50.0",
            "processing_status": "failed",
            "processing_started_at": "2024-07-05T09:00:00",
            "processing_finished_at": "2024-07-05T09:01:00",
            "processing_error": "PDF parsing failed: invalid format",
            "item_count": 0,
            "text_count": 0,
            "title_count": 0,
            "table_count": 0,
            "picture_count": 0,
            "formula_count": 0,
            "metadata": {
                "author": "Test Author",
                "document_type": "standard",
            },
        },
    ]

    # 插入测试数据
    print("📝 创建测试数据...")
    for doc in test_docs:
        insert_document_info(doc)
        print(f"  ✅ {doc['document_code']} - {doc['title']}")

    print(f"\n✅ 成功创建 {len(test_docs)} 条测试数据")


if __name__ == "__main__":
    create_test_data()
