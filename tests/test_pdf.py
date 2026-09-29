"""PDF 解析功能测试"""

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


# ==================== 测试 1: HybridChunker 快速测试 ====================

def test_hybrid_chunker_quick():
    """快速测试 HybridChunker 分块功能（使用小页面范围）"""
    
    # 测试文件路径
    pdf_path = "specs/03-management-provisioning/gsma/SGP.22_v2.1.pdf"
    document_id = "SGP.22_v2.1_quick_test"
    
    print("=" * 80)
    print("HybridChunker 快速测试（仅解析前 10 页）")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print(f"文档 ID: {document_id}")
    print(f"页面范围: 1-10")
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
    
    # 解析 PDF（仅前 10 页）
    print("开始解析 PDF（前 10 页）...")
    result = parser.parse_pdf(
        pdf_path=pdf_path,
        document_id=document_id,
        page_range=(1, 10),  # 只解析前 10 页
        output_dir="output/pictures",
    )
    
    items = result["items"]
    chunks = result["chunks"]
    
    print(f"\n解析完成！")
    print(f"  - 提取 items: {len(items)} 个")
    print(f"  - 生成 chunks: {len(chunks)} 个")
    print()
    
    # 显示前 3 个 chunk 的详细信息
    print("=" * 80)
    print("前 3 个 Chunk 详情:")
    print("=" * 80)
    
    for i, chunk in enumerate(chunks[:3]):
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


# ==================== 测试 2: HybridChunker 完整测试 ====================

def test_hybrid_chunker_full():
    """完整测试 HybridChunker 分块功能"""
    
    # 测试文件路径
    pdf_path = "specs/03-management-provisioning/gsma/SGP.22_v2.1.pdf"
    document_id = "SGP.22_v2.1_test"
    
    print("=" * 80)
    print("HybridChunker 完整分块功能测试")
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
    
    # 解析完整 PDF
    print("开始解析完整 PDF...")
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
    print()
    
    print("=" * 80)
    print("测试完成！")
    print("=" * 80)


# ==================== 测试 3: 完整流程测试（HybridChunker + VLM） ====================

def test_full_pipeline():
    """完整测试：HybridChunker + VLM"""
    
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # 测试文件路径
    pdf_path = "specs/03-management-provisioning/gsma/SGP.22_v2.1.pdf"
    document_id = "SGP.22_v2.1_full_test"
    
    print("=" * 80)
    print("完整测试：HybridChunker + VLM")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print(f"文档 ID: {document_id}")
    print(f"页面范围: 1-5")
    print()
    
    # 清理旧数据
    print("清理旧数据...")
    delete_chunks_by_document(document_id)
    delete_document_items_by_document(document_id)
    print()
    
    # 配置 VLM
    vlm_config = {
        "backend_type": "openai",
        "openai_api_key": os.getenv("VLM_OPENAI_API_KEY", ""),
        "openai_base_url": os.getenv("VLM_OPENAI_BASE_URL", ""),
        "openai_model": os.getenv("VLM_OPENAI_MODEL", "qwen-vl-max"),
    }
    
    print(f"VLM 配置:")
    print(f"  - 模型: {vlm_config['openai_model']}")
    print()
    
    # 初始化解析器（启用 VLM）
    print("初始化 PDFParser（包含 HybridChunker + VLM）...")
    parser = PDFParser(
        do_ocr=True,
        max_tokens=512,
        tokenizer_name="BAAI/bge-m3",
        vlm_config=vlm_config,
    )
    print()
    
    # 解析 PDF（仅前 5 页）
    print("开始解析 PDF（前 5 页）...")
    print("注意：每张图片都会调用 VLM API...")
    print()
    
    result = parser.parse_pdf(
        pdf_path=pdf_path,
        document_id=document_id,
        page_range=(1, 5),
        output_dir="output/pictures",
    )
    
    items = result["items"]
    chunks = result["chunks"]
    
    print(f"\n解析完成！")
    print(f"  - 提取 items: {len(items)} 个")
    print(f"  - 生成 chunks: {len(chunks)} 个")
    print()
    
    # 统计图片数量
    picture_items = [it for it in items if it["label"] == "picture"]
    pictures_with_vlm = [
        it for it in picture_items
        if it.get("metadata", {}).get("vlm_description")
    ]
    
    print(f"图片 items: {len(picture_items)} 个")
    print(f"包含 VLM 描述: {len(pictures_with_vlm)} 个")
    print()
    
    # 显示前 3 个 chunk 的详细信息
    print("=" * 80)
    print("前 3 个 Chunk 详情:")
    print("=" * 80)
    
    for i, chunk in enumerate(chunks[:3]):
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
    print()
    
    # 显示图片的 VLM 描述
    if pictures_with_vlm:
        print("=" * 80)
        print("图片 VLM 描述详情:")
        print("=" * 80)
        
        for i, item in enumerate(pictures_with_vlm[:2]):
            metadata = item.get("metadata", {})
            caption = metadata.get("caption", "无")
            vlm_desc = metadata.get("vlm_description", "未生成")
            
            print(f"\n--- 图片 {i+1} ---")
            print(f"ID: {item['id']}")
            print(f"Caption: {caption}")
            print(f"VLM 描述 (前 200 字符): {vlm_desc[:200]}...")
            print()
    
    print("=" * 80)
    print("测试完成！✅")
    print("=" * 80)
    print()
    print("总结:")
    print(f"  ✅ HybridChunker 分块: {len(db_chunks)} 个 chunks")
    print(f"  ✅ Items 提取: {len(db_items)} 个 items")
    print(f"  ✅ self_ref 关联: {len(items_with_ref)} 个")
    print(f"  ✅ VLM 描述: {len(pictures_with_vlm)} 个图片")
    print(f"  ✅ Token 统计: 最小 {min(token_counts)}, 最大 {max(token_counts)}, 平均 {sum(token_counts)/len(token_counts):.1f}")


if __name__ == "__main__":
    import sys
    
    # 根据命令行参数选择测试
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "quick":
            test_hybrid_chunker_quick()
        elif test_name == "full":
            test_hybrid_chunker_full()
        elif test_name == "pipeline":
            test_full_pipeline()
        else:
            print(f"未知测试: {test_name}")
            print("可用测试: quick, full, pipeline")
    else:
        # 运行快速测试
        test_hybrid_chunker_quick()
