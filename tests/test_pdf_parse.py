"""测试脚本 - 使用 SGP.01-v1.12.pdf 文档前 10页测试 PDF 解析功能"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from smartcard_kb.docs_compile import (
    PDFParser,
    init_database,
    query_document_items,
    get_document_stats,
    delete_document_items_by_document,
)


def test_pdf_parsing():
    """测试 PDF 解析功能"""
    pdf_path = "specs/03-management-provisioning/gsma/SGP.01-v1.12.pdf"

    # 检查 PDF 文件是否存在
    if not Path(pdf_path).exists():
        print(f"❌ PDF 文件不存在: {pdf_path}")
        return

    print(f"📄 测试 PDF 文件: {pdf_path}")
    print(f"📄 解析范围: 前 10 页")
    print("=" * 60)

    # 初始化数据库
    print("\n🔧 初始化数据库...")
    init_database()
    print("✅ 数据库初始化完成")

    # 如果之前有测试数据，先删除
    document_id = "SGP.01-v1.12"
    print(f"\n🗑️  清理旧数据 (document_id={document_id})...")
    deleted = delete_document_items_by_document(document_id)
    print(f"✅ 删除了 {deleted} 条旧记录")

    # 解析 PDF
    print("\n🔄 开始解析 PDF...")
    parser = PDFParser(do_ocr=True)
    items = parser.parse_pdf(
        pdf_path=pdf_path,
        document_id=document_id,
        page_range=(1, 10),
        output_dir="output/pictures"
    )
    print(f"✅ 解析完成，共提取 {len(items)} 个 item")

    # 显示统计信息
    print("\n📊 文档统计信息:")
    stats = get_document_stats(document_id)
    for label, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {label}: {count}")

    # 查询不同类型的数据
    print("\n" + "=" * 60)
    print("📝 查询测试:")

    # 1. 查询所有文本项
    texts = query_document_items(document_id=document_id, label="text")
    print(f"\n📄 文本项 (text): {len(texts)} 条")
    if texts:
        print(f"  示例: {texts[0]['text'][:100]}..." if texts[0].get('text') else "  示例: 无文本内容")

    # 2. 查询所有标题
    titles = query_document_items(document_id=document_id, label="section_header")
    print(f"\n📑 标题项 (section_header): {len(titles)} 条")
    if titles:
        for i, title in enumerate(titles[:5]):
            level = title.get('metadata', {}).get('level', '?')
            print(f"  [{i+1}] (level={level}) {title.get('text', 'N/A')}")

    # 3. 查询所有表格
    tables = query_document_items(document_id=document_id, label="table")
    print(f"\n📊 表格项 (table): {len(tables)} 条")
    if tables:
        print(f"  示例: {tables[0].get('text', 'N/A')[:100]}..." if tables[0].get('text') else "  示例: 无表格内容")

    # 4. 查询所有图片
    pictures = query_document_items(document_id=document_id, label="picture")
    print(f"\n🖼️  图片项 (picture): {len(pictures)} 条")
    if pictures:
        for i, pic in enumerate(pictures[:3]):
            content = pic.get('content', {})
            image_path = content.get('image_path', 'N/A') if content else 'N/A'
            caption = pic.get('metadata', {}).get('caption', '无标题')
            print(f"  [{i+1}] {image_path} - {caption}")

    # 5. 查询启用 RAG 的项
    rag_items = query_document_items(
        document_id=document_id,
        is_rag_enabled=True
    )
    print(f"\n🔍 启用 RAG 的项: {len(rag_items)} 条")

    # 6. 查询指定页面的项
    page_items = query_document_items(
        document_id=document_id,
        page_id=f"{document_id}_page_1"
    )
    print(f"\n📄 第 1 页的项: {len(page_items)} 条")

    # 显示前 5 个 item 的详细信息
    print("\n" + "=" * 60)
    print("📋 前 5 个 item 详情:")
    all_items = query_document_items(document_id=document_id)
    for i, item in enumerate(all_items[:5]):
        print(f"\n  [{i+1}] ID: {item['id']}")
        print(f"      Label: {item['label']}")
        print(f"      Order: {item['order_index']}")
        print(f"      Page: {item['page_id']}")
        print(f"      Text: {item.get('text', 'N/A')[:80]}..." if item.get('text') else "      Text: N/A")
        print(f"      RAG: {item['is_rag_enabled']}")

    print("\n" + "=" * 60)
    print("✅ 测试完成!")


if __name__ == "__main__":
    test_pdf_parsing()
