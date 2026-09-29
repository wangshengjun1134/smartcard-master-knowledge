"""清空数据库并解析指定 PDF 文件"""

import sys
import io
import uuid
from pathlib import Path
from datetime import datetime

# 设置 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from smartcard_kb.docs_compile.database import (
    get_connection,
    init_database,
    insert_document_info,
    insert_document_items,
    query_document_info,
    query_document_items,
    get_document_stats,
)
from smartcard_kb.docs_compile.pdf_parser import PDFParser


def clear_database():
    """清空数据库所有数据"""
    print("=" * 60)
    print("🗑️  清空数据库...")
    print("=" * 60)

    conn = get_connection()
    cursor = conn.cursor()

    # 删除所有数据
    cursor.execute("DELETE FROM doc_items")
    item_count = cursor.rowcount

    cursor.execute("DELETE FROM doc_info")
    info_count = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()

    print(f"✅ 已删除 {item_count} 条 document_item 记录")
    print(f"✅ 已删除 {info_count} 条 document_info 记录")


def parse_and_save_pdf(pdf_path: str, document_code: str, title: str):
    """解析 PDF 并保存到数据库"""
    print(f"\n{'=' * 60}")
    print(f"📄 解析 PDF: {Path(pdf_path).name}")
    print(f"{'=' * 60}")

    # 检查文件是否存在
    if not Path(pdf_path).exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return None

    # 生成文档 ID
    document_id = str(uuid.uuid4())

    # 创建文档信息
    doc_info = {
        "id": document_id,
        "document_code": document_code,
        "title": title,
        "series_id": "SGP",
        "file_name": Path(pdf_path).name,
        "file_path": str(pdf_path),
        "file_format": "pdf",
        "issuer": "GSMA",
        "language": "en",
        "source_type": "upload",
        "parser": "docling",
        "parser_version": "2.50.0",
        "processing_status": "processing",
        "processing_started_at": datetime.now().isoformat(),
        "item_count": 0,
        "text_count": 0,
        "title_count": 0,
        "table_count": 0,
        "picture_count": 0,
        "formula_count": 0,
    }

    insert_document_info(doc_info)
    print(f"✅ 已创建文档记录: {document_code}")

    # 解析 PDF
    print(f"🔄 开始解析 PDF...")
    parser = PDFParser(do_ocr=True)

    try:
        items = parser.parse_pdf(
            pdf_path=pdf_path,
            document_id=document_id,
            output_dir="output/pictures"
        )

        print(f"✅ 解析完成，共提取 {len(items)} 个 item")

        # 获取统计信息
        stats = get_document_stats(document_id)
        type_counts = {
            "item_count": len(items),
            "text_count": stats.get("text", 0),
            "title_count": stats.get("section_header", 0),
            "table_count": stats.get("table", 0),
            "picture_count": stats.get("picture", 0),
            "formula_count": stats.get("formula", 0),
        }

        # 更新文档信息
        doc_info.update({
            "processing_status": "completed",
            "processing_finished_at": datetime.now().isoformat(),
            "page_count": len(set(i["page_id"] for i in items)),
            **type_counts,
        })

        insert_document_info(doc_info)

        print(f"✅ 已更新文档统计信息:")
        print(f"   - 总 Item 数: {type_counts['item_count']}")
        print(f"   - 文本: {type_counts['text_count']}")
        print(f"   - 标题: {type_counts['title_count']}")
        print(f"   - 表格: {type_counts['table_count']}")
        print(f"   - 图片: {type_counts['picture_count']}")
        print(f"   - 公式: {type_counts['formula_count']}")

        return {
            "document_id": document_id,
            "item_count": len(items),
            "stats": stats,
        }

    except Exception as e:
        print(f"❌ 解析失败: {str(e)}")
        doc_info.update({
            "processing_status": "failed",
            "processing_finished_at": datetime.now().isoformat(),
            "processing_error": str(e),
        })
        insert_document_info(doc_info)
        return None


def verify_results():
    """验证数据库结果"""
    print(f"\n{'=' * 60}")
    print("📊 验证数据库结果")
    print(f"{'=' * 60}")

    # 查询所有文档
    docs = query_document_info()
    print(f"\n📋 文档总数: {len(docs)}")

    for doc in docs:
        print(f"\n{'─' * 40}")
        print(f"📄 {doc.get('document_code', 'N/A')}: {doc.get('title', 'N/A')}")
        print(f"   ID: {doc['id']}")
        print(f"   状态: {doc.get('processing_status', 'N/A')}")
        print(f"   Item 数: {doc.get('item_count', 0)}")
        print(f"   文本: {doc.get('text_count', 0)}")
        print(f"   标题: {doc.get('title_count', 0)}")
        print(f"   表格: {doc.get('table_count', 0)}")
        print(f"   图片: {doc.get('picture_count', 0)}")

        # 查询 item 详情
        items = query_document_items(document_id=doc["id"])
        print(f"   实际 Item 数: {len(items)}")

        # 显示前 5 个 item
        print(f"\n   前 5 个 Item:")
        for i, item in enumerate(items[:5]):
            print(f"     [{i+1}] {item['label']}: {item.get('text', '')[:60]}...")

        # 显示类型分布
        type_dist = {}
        for item in items:
            label = item.get("label", "unknown")
            type_dist[label] = type_dist.get(label, 0) + 1

        print(f"\n   类型分布:")
        for label, count in sorted(type_dist.items(), key=lambda x: x[1], reverse=True):
            print(f"     - {label}: {count}")

    print(f"\n{'=' * 60}")
    print("✅ 验证完成!")


def main():
    """主函数"""
    # 初始化数据库
    init_database()

    # 1. 清空数据库
    clear_database()

    # 2. 解析 PDF 文件
    pdfs_to_parse = [
        {
            "path": "specs/03-management-provisioning/gsma/SGP.22_v2.1.pdf",
            "code": "SGP.22-v2.1",
            "title": "SGP.22 v2.1 - Remote Provisioning Architecture for GSMA eSIM",
        },
        {
            "path": "specs/03-management-provisioning/gsma/SGP.23-v1.9.pdf",
            "code": "SGP.23-v1.9",
            "title": "SGP.23 v1.9 - Remote Provisioning Architecture for GSMA eSIM",
        },
    ]

    results = []
    for pdf_info in pdfs_to_parse:
        result = parse_and_save_pdf(
            pdf_path=pdf_info["path"],
            document_code=pdf_info["code"],
            title=pdf_info["title"],
        )
        if result:
            results.append(result)

    # 3. 验证结果
    if results:
        verify_results()
    else:
        print("\n❌ 没有成功解析任何 PDF 文件")


if __name__ == "__main__":
    main()
