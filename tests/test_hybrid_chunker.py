"""测试 HybridChunker 分块功能"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.smartcard_kb.docs_compile.pdf_parser import PDFParser
from src.smartcard_kb.docs_compile.database import (
    query_chunks,
    query_document_items,
    delete_chunks_by_document,
    delete_document_items_by_document,
)


def test_hybrid_chunker():
    """测试 HybridChunker 分块功能"""
    
    # 测试文件路径
    pdf_path = "specs/03-management-provisioning/gsma/SGP.22_v2.1.pdf"
    document_id = "SGP.22_v2.1_test"
    
    print("=" * 80)
    print("HybridChunker 分块功能测试")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print(f"文档 ID: {document_id}")
    print()
    
    # 清理旧数据
    print("清理旧数据...")
    delete_chunks_by_document(document_id)
    delete_document_items_by_document(document_id)
    print()
    
    # 初始化解析器
    print("初始化 PDFParser（包含 HybridChunker）...")
    parser = PDFParser(
        do_ocr=True,
        max_tokens=512,
        tokenizer_name="BAAI/bge-m3",
    )
    print()
    
    # 解析 PDF
    print("开始解析 PDF...")
    result = parser.parse_pdf(
        pdf_path=pdf_path,
        document_id=document_id,
        output_dir="output/pictures",
    )
    
    items = result["items"]
    chunks = result["chunks"]
    
    print(f"\n解析完成！")
    print(f"  - 提取 items: {len(items)} 个")
    print(f"  - 生成 chunks: {len(chunks)} 个")
    print()
    
    # 显示前 5 个 chunk 的详细信息
    print("=" * 80)
    print("前 5 个 Chunk 详情:")
    print("=" * 80)
    
    for i, chunk in enumerate(chunks[:5]):
        print(f"\n--- Chunk {i+1} ---")
        print(f"ID: {chunk['id']}")
        print(f"Chunk Index: {chunk['chunk_index']}")
        print(f"Heading Path: {chunk['heading_path']}")
        print(f"Token Count: {chunk['token_count']}")
        print(f"Page Nos: {chunk['page_nos']}")
        print(f"Linked Items: {len(chunk['linked_item_ids'])} 个")
        print(f"Text (前 200 字符): {chunk['text'][:200]}...")
        print()
    
    # 验证数据库中的 chunks
    print("=" * 80)
    print("验证数据库中的 chunks:")
    print("=" * 80)
    
    db_chunks = query_chunks(document_id=document_id)
    print(f"数据库中查询到 chunks: {len(db_chunks)} 个")
    print()
    
    # 统计 token 分布
    token_counts = [c['token_count'] for c in db_chunks if c.get('token_count')]
    if token_counts:
        print("Token 分布统计:")
        print(f"  - 最小: {min(token_counts)}")
        print(f"  - 最大: {max(token_counts)}")
        print(f"  - 平均: {sum(token_counts) / len(token_counts):.1f}")
        print()
    
    # 验证 items 的 self_ref
    print("=" * 80)
    print("验证 items 的 self_ref 字段:")
    print("=" * 80)
    
    db_items = query_document_items(document_id=document_id)
    items_with_ref = [it for it in db_items if it.get('self_ref')]
    print(f"总 items: {len(db_items)} 个")
    print(f"包含 self_ref: {len(items_with_ref)} 个")
    
    if items_with_ref:
        print(f"\n前 3 个 item 的 self_ref:")
        for item in items_with_ref[:3]:
            print(f"  - {item['id']}: {item['self_ref']}")
    print()
    
    # 验证关联关系
    print("=" * 80)
    print("验证 chunks 与 items 的关联关系:")
    print("=" * 80)
    
    chunks_with_links = [c for c in db_chunks if c.get('linked_item_ids')]
    print(f"包含关联的 chunks: {len(chunks_with_links)} 个")
    
    if chunks_with_links:
        total_links = sum(len(c['linked_item_ids']) for c in chunks_with_links)
        print(f"总关联数: {total_links}")
        print(f"\n第一个有关联的 chunk:")
        first = chunks_with_links[0]
        print(f"  Chunk ID: {first['id']}")
        print(f"  Linked Items: {first['linked_item_ids']}")
    print()
    
    print("=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_hybrid_chunker()
