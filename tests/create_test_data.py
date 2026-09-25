"""测试数据脚本 - 在数据库中添加测试文档信息和 item 数据"""

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
    insert_document_items,
    query_document_info,
    query_document_items,
)


def create_test_data():
    """创建测试数据（包含 document_info 和 document_item）"""
    # 初始化数据库
    init_database()

    # 检查是否已有测试数据，如果有则先删除
    existing = query_document_info(document_code="TEST-001")
    if existing:
        print("⚠️  测试数据已存在，先删除旧数据...")
        from smartcard_kb.docs_compile.database import delete_document_info
        for doc in existing:
            delete_document_info(doc["id"])
        print("✅ 旧数据已删除")

    # 测试文档列表
    test_docs = [
        {
            "id": "381054b0-1588-4c6e-b4bb-e7a6bdc03893",
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
            "item_count": 15,
            "text_count": 8,
            "title_count": 4,
            "table_count": 2,
            "picture_count": 1,
            "formula_count": 0,
            "metadata": {
                "author": "Test Author",
                "department": "Engineering",
                "document_type": "standard",
            },
        },
        {
            "id": "55861363-a3fd-464f-ae9e-1d3a6f24e4bf",
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
            "item_count": 20,
            "text_count": 10,
            "title_count": 5,
            "table_count": 3,
            "picture_count": 2,
            "formula_count": 0,
            "metadata": {
                "author": "Test Author 2",
                "department": "Security",
                "document_type": "standard",
            },
        },
        {
            "id": "ab8fedcd-4823-4cf6-891a-69c3f5324909",
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
            "id": "1a396210-1b9e-45a1-b0c8-e4f8bb143fac",
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
            "item_count": 10,
            "text_count": 6,
            "title_count": 3,
            "table_count": 1,
            "picture_count": 0,
            "formula_count": 0,
            "metadata": {
                "author": "Test Author",
                "document_type": "standard",
            },
        },
        {
            "id": "5a6155c0-d2f7-4a65-ae7a-15f0f42483ac",
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

    # 插入文档信息
    print("📝 创建测试文档信息...")
    for doc in test_docs:
        insert_document_info(doc)
        print(f"  ✅ {doc['document_code']} - {doc['title']}")

    # 创建 document_item 测试数据
    print("\n📝 创建测试 Item 数据...")
    test_items = []

    # TEST-001 的 item
    doc_id_1 = "381054b0-1588-4c6e-b4bb-e7a6bdc03893"
    test_items.extend([
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_1", "parent_id": None, "label": "section_header", "text": "1. Introduction", "order_index": 1, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "1. Introduction", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_1", "parent_id": None, "label": "text", "text": "This document describes the eSIM architecture and remote provisioning framework.", "order_index": 2, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "This document describes the eSIM architecture.", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_2", "parent_id": None, "label": "section_header", "text": "1.1 System Overview", "order_index": 3, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "1.1 System Overview", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_2", "parent_id": None, "label": "text", "text": "The eSIM system consists of three main components: eUICC, SM-DP+, and SM-DS.", "order_index": 4, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "The eSIM system consists of three main components.", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_3", "parent_id": None, "label": "table", "text": "| Component | Description |\n|-----------|-------------|\n| eUICC | Embedded Universal Integrated Circuit Card |\n| SM-DP+ | Subscription Manager Data Preparation + |\n| SM-DS | Subscription Manager Discovery |", "order_index": 5, "bbox": {"l": 72.0, "t": 200.0, "r": 540.0, "b": 300.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "table", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_4", "parent_id": None, "label": "section_header", "text": "2. Security Architecture", "order_index": 6, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "2. Security Architecture", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_4", "parent_id": None, "label": "text", "text": "Security is a fundamental requirement for eSIM systems. All communications must be encrypted.", "order_index": 7, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "Security is a fundamental requirement.", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_5", "parent_id": None, "label": "picture", "text": "output/pictures/picture_0001.png", "order_index": 8, "bbox": {"l": 100.0, "t": 200.0, "r": 440.0, "b": 400.0}, "metadata": {"level": 1, "caption": "Figure 1: eSIM Architecture Diagram"}, "content": {"image_path": "output/pictures/picture_0001.png"}, "is_rag_enabled": False, "raw_json": {"label": "picture", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_6", "parent_id": None, "label": "section_header", "text": "2.1 Certificate Chain", "order_index": 9, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "2.1 Certificate Chain", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_6", "parent_id": None, "label": "text", "text": "The certificate chain includes Root Certificate, EUM Certificate, and eUICC Certificate.", "order_index": 10, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "The certificate chain includes Root Certificate.", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_7", "parent_id": None, "label": "list_item", "text": "Root Certificate: Issued by GSMA", "order_index": 11, "bbox": {"l": 90.0, "t": 200.0, "r": 540.0, "b": 220.0}, "metadata": {"level": 3}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "list_item", "level": 3}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_7", "parent_id": None, "label": "list_item", "text": "EUM Certificate: Issued by EUM to eUICC manufacturers", "order_index": 12, "bbox": {"l": 90.0, "t": 230.0, "r": 540.0, "b": 250.0}, "metadata": {"level": 3}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "list_item", "level": 3}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_8", "parent_id": None, "label": "table", "text": "| Certificate Type | Issuer | Subject |\n|-----------------|--------|---------|\n| Root | GSMA | EUM |\n| EUM | EUM | eUICC Manufacturer |\n| eUICC | eUICC Manufacturer | Individual eUICC |", "order_index": 13, "bbox": {"l": 72.0, "t": 300.0, "r": 540.0, "b": 400.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "table", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_9", "parent_id": None, "label": "section_header", "text": "3. Conclusion", "order_index": 14, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "3. Conclusion", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_1, "page_id": f"{doc_id_1}_page_9", "parent_id": None, "label": "text", "text": "This document provides a comprehensive overview of the eSIM architecture and security requirements.", "order_index": 15, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "This document provides a comprehensive overview.", "level": 1}},
    ])

    # TEST-002 的 item
    doc_id_2 = "55861363-a3fd-464f-ae9e-1d3a6f24e4bf"
    test_items.extend([
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_1", "parent_id": None, "label": "section_header", "text": "1. Security Requirements Overview", "order_index": 1, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "1. Security Requirements Overview", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_1", "parent_id": None, "label": "text", "text": "This document specifies the security requirements for eSIM remote provisioning.", "order_index": 2, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "This document specifies the security requirements.", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_2", "parent_id": None, "label": "section_header", "text": "1.1 Scope", "order_index": 3, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "1.1 Scope", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_2", "parent_id": None, "label": "text", "text": "The scope covers all aspects of eSIM security including authentication, encryption, and key management.", "order_index": 4, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "The scope covers all aspects of eSIM security.", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_3", "parent_id": None, "label": "table", "text": "| Requirement ID | Description | Priority |\n|---------------|-------------|----------|\n| SEC-001 | Mutual Authentication | Critical |\n| SEC-002 | End-to-End Encryption | Critical |\n| SEC-003 | Key Rotation | High |\n| SEC-004 | Secure Storage | High |", "order_index": 5, "bbox": {"l": 72.0, "t": 200.0, "r": 540.0, "b": 300.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "table", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_4", "parent_id": None, "label": "section_header", "text": "2. Authentication Mechanisms", "order_index": 6, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "2. Authentication Mechanisms", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_4", "parent_id": None, "label": "text", "text": "All parties must authenticate using X.509 certificates before establishing a secure channel.", "order_index": 7, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "All parties must authenticate using X.509 certificates.", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_5", "parent_id": None, "label": "picture", "text": "output/pictures/picture_0002.png", "order_index": 8, "bbox": {"l": 100.0, "t": 200.0, "r": 440.0, "b": 400.0}, "metadata": {"level": 1, "caption": "Figure 2: Authentication Flow"}, "content": {"image_path": "output/pictures/picture_0002.png"}, "is_rag_enabled": False, "raw_json": {"label": "picture", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_6", "parent_id": None, "label": "section_header", "text": "2.1 Certificate Validation", "order_index": 9, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "2.1 Certificate Validation", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_6", "parent_id": None, "label": "text", "text": "Certificate validation must include checking expiration dates, revocation status, and chain of trust.", "order_index": 10, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "Certificate validation must include checking expiration dates.", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_7", "parent_id": None, "label": "list_item", "text": "Check certificate expiration date", "order_index": 11, "bbox": {"l": 90.0, "t": 200.0, "r": 540.0, "b": 220.0}, "metadata": {"level": 3}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "list_item", "level": 3}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_7", "parent_id": None, "label": "list_item", "text": "Verify certificate revocation status (CRL/OCSP)", "order_index": 12, "bbox": {"l": 90.0, "t": 230.0, "r": 540.0, "b": 250.0}, "metadata": {"level": 3}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "list_item", "level": 3}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_8", "parent_id": None, "label": "list_item", "text": "Validate certificate chain of trust", "order_index": 13, "bbox": {"l": 90.0, "t": 260.0, "r": 540.0, "b": 280.0}, "metadata": {"level": 3}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "list_item", "level": 3}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_9", "parent_id": None, "label": "table", "text": "| Validation Step | Method | Status |\n|----------------|--------|--------|\n| Expiration Check | Local | Required |\n| Revocation Check | CRL/OCSP | Required |\n| Chain Validation | PKI | Required |", "order_index": 14, "bbox": {"l": 72.0, "t": 300.0, "r": 540.0, "b": 400.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "table", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_10", "parent_id": None, "label": "section_header", "text": "3. Encryption Requirements", "order_index": 15, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "3. Encryption Requirements", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_10", "parent_id": None, "label": "text", "text": "All data in transit must be encrypted using TLS 1.3 or higher.", "order_index": 16, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "All data in transit must be encrypted using TLS 1.3.", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_11", "parent_id": None, "label": "picture", "text": "output/pictures/picture_0003.png", "order_index": 17, "bbox": {"l": 100.0, "t": 200.0, "r": 440.0, "b": 400.0}, "metadata": {"level": 1, "caption": "Figure 3: Encryption Architecture"}, "content": {"image_path": "output/pictures/picture_0003.png"}, "is_rag_enabled": False, "raw_json": {"label": "picture", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_12", "parent_id": None, "label": "section_header", "text": "3.1 Key Management", "order_index": 18, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "3.1 Key Management", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_12", "parent_id": None, "label": "text", "text": "Encryption keys must be rotated periodically and stored in secure hardware modules.", "order_index": 19, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "Encryption keys must be rotated periodically.", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_2, "page_id": f"{doc_id_2}_page_13", "parent_id": None, "label": "section_header", "text": "4. Summary", "order_index": 20, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "4. Summary", "level": 1}},
    ])

    # TEST-004 的 item（processing 状态）
    doc_id_4 = "1a396210-1b9e-45a1-b0c8-e4f8bb143fac"
    test_items.extend([
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_1", "parent_id": None, "label": "section_header", "text": "1. Processing Status Document", "order_index": 1, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "1. Processing Status Document", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_1", "parent_id": None, "label": "text", "text": "This document is currently being processed and more items will be added.", "order_index": 2, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "This document is currently being processed.", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_2", "parent_id": None, "label": "section_header", "text": "1.1 Current Status", "order_index": 3, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "1.1 Current Status", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_2", "parent_id": None, "label": "text", "text": "The document parsing is in progress. Please check back later for complete results.", "order_index": 4, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "The document parsing is in progress.", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_3", "parent_id": None, "label": "table", "text": "| Status | Progress | Estimated Completion |\n|--------|----------|---------------------|\n| Processing | 25% | 5 minutes |", "order_index": 5, "bbox": {"l": 72.0, "t": 200.0, "r": 540.0, "b": 250.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "table", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_4", "parent_id": None, "label": "section_header", "text": "2. Next Steps", "order_index": 6, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "2. Next Steps", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_4", "parent_id": None, "label": "text", "text": "After processing completes, all document items will be available for search and retrieval.", "order_index": 7, "bbox": {"l": 72.0, "t": 130.0, "r": 540.0, "b": 160.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "text", "text": "After processing completes, all items will be available.", "level": 1}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_5", "parent_id": None, "label": "list_item", "text": "Wait for processing to complete", "order_index": 8, "bbox": {"l": 90.0, "t": 200.0, "r": 540.0, "b": 220.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "list_item", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_5", "parent_id": None, "label": "list_item", "text": "Review extracted items", "order_index": 9, "bbox": {"l": 90.0, "t": 230.0, "r": 540.0, "b": 250.0}, "metadata": {"level": 2}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "list_item", "level": 2}},
        {"id": str(uuid.uuid4()), "document_id": doc_id_4, "page_id": f"{doc_id_4}_page_6", "parent_id": None, "label": "section_header", "text": "3. Conclusion", "order_index": 10, "bbox": {"l": 72.0, "t": 100.0, "r": 540.0, "b": 120.0}, "metadata": {"level": 1}, "content": None, "is_rag_enabled": True, "raw_json": {"label": "section_header", "text": "3. Conclusion", "level": 1}},
    ])

    # 批量插入 item
    print(f"\n📝 批量插入 {len(test_items)} 条 Item 数据...")
    insert_document_items(test_items)
    print(f"✅ 成功插入 {len(test_items)} 条 Item 数据")

    # 验证
    print("\n📊 验证测试数据:")
    for doc in test_docs:
        items = query_document_items(document_id=doc["id"])
        print(f"  {doc['document_code']}: {len(items)} items")

    print(f"\n✅ 测试数据创建完成！")
    print(f"\n📋 测试文档列表:")
    print(f"  - TEST-001: 15 items (completed)")
    print(f"  - TEST-002: 20 items (completed)")
    print(f"  - TEST-003: 0 items (pending)")
    print(f"  - TEST-004: 10 items (processing)")
    print(f"  - TEST-005: 0 items (failed)")


if __name__ == "__main__":
    create_test_data()
