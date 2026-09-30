"""清空数据库并处理完整 PDF"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from src.smartcard_kb.docs_compile.pdf_parser import PDFParser
from src.smartcard_kb.docs_compile.database import (
    get_connection,
    query_chunks,
    query_document_items,
    query_document_info,
    delete_chunks_by_document,
    delete_document_items_by_document,
    delete_document_info,
)


def clear_database():
    """清空所有表"""
    print("=" * 80)
    print("清空数据库")
    print("=" * 80)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 删除所有数据（按依赖顺序）
    cursor.execute("DELETE FROM doc_chunks")
    chunks_count = cursor.rowcount
    print(f"  - 删除 doc_chunks: {chunks_count} 条")
    
    cursor.execute("DELETE FROM doc_items")
    items_count = cursor.rowcount
    print(f"  - 删除 doc_items: {items_count} 条")
    
    cursor.execute("DELETE FROM doc_info")
    info_count = cursor.rowcount
    print(f"  - 删除 doc_info: {info_count} 条")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print()
    print("数据库已清空！")
    print()


def process_full_pdf():
    """处理完整 PDF"""
    
    # 测试文件路径
    pdf_path = "specs/03-management-provisioning/gsma/SGP.01-v1.12.pdf"
    document_id = "SGP.01-v1.12"
    
    print("=" * 80)
    print(f"处理完整 PDF: {pdf_path}")
    print("=" * 80)
    print(f"文档 ID: {document_id}")
    print(f"页面范围: 全部")
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
    
    # 解析完整 PDF（不带 page_range 限制）
    print("开始解析完整 PDF...")
    print("注意：这可能需要较长时间，请耐心等待...")
    print()
    
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
    
    # 统计图片数量
    picture_items = [it for it in items if it["label"] == "picture"]
    pictures_with_vlm = [
        it for it in picture_items
        if it.get("metadata", {}).get("vlm_description")
    ]
    
    print(f"图片 items: {len(picture_items)} 个")
    print(f"包含 VLM 描述: {len(pictures_with_vlm)} 个")
    print()
    
    # 验证数据库
    print("=" * 80)
    print("验证数据库:")
    print("=" * 80)
    
    db_items = query_document_items(document_id=document_id)
    db_chunks = query_chunks(document_id=document_id)
    db_pictures = [it for it in db_items if it["label"] == "picture"]
    
    print(f"总 items: {len(db_items)} 个")
    print(f"总 chunks: {len(db_chunks)} 个")
    print(f"图片 items: {len(db_pictures)} 个")
    print()
    
    # 统计 token 分布
    token_counts = [c['token_count'] for c in db_chunks if c.get('token_count')]
    if token_counts:
        print("Token 分布统计:")
        print(f"  - 最小: {min(token_counts)}")
        print(f"  - 最大: {max(token_counts)}")
        print(f"  - 平均: {sum(token_counts) / len(token_counts):.1f}")
        print()
    
    # 按 label 统计
    print("=" * 80)
    print("按类型统计:")
    print("=" * 80)
    
    label_counts = {}
    for item in db_items:
        label = item["label"]
        label_counts[label] = label_counts.get(label, 0) + 1
    
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count} 个")
    print()
    
    print("=" * 80)
    print("处理完成！✅")
    print("=" * 80)


if __name__ == "__main__":
    # 清空数据库
    # clear_database()
    
    # 处理完整 PDF
    process_full_pdf()
