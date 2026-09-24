"""使用示例 - docs_compile 模块的使用方法"""

from smartcard_kb.docs_compile import (
    PDFParser,
    init_database,
    query_document_items,
    extract_item,
)


def example_parse_pdf():
    """示例：解析 PDF 文件"""
    # 初始化解析器（启用 OCR）
    parser = PDFParser(do_ocr=True)

    # 解析 PDF 并保存到数据库
    document_id = "spec_001"
    pdf_path = "specs/01-foundation/RSG_ESP_001_202206Z.pdf"

    items = parser.parse_pdf(
        pdf_path=pdf_path,
        document_id=document_id,
        page_range=(1, 10),  # 可选：只解析第 1-10 页
        output_dir="output/pictures"
    )

    print(f"解析完成，共提取 {len(items)} 个 item")


def example_query_items():
    """示例：查询 document_items"""
    # 查询指定文档的所有 item
    items = query_document_items(document_id="spec_001")
    print(f"文档 spec_001 共有 {len(items)} 个 item")

    # 查询指定文档的所有表格
    tables = query_document_items(
        document_id="spec_001",
        label="table"
    )
    print(f"文档 spec_001 共有 {len(tables)} 个表格")

    # 查询启用 RAG 的所有文本
    rag_items = query_document_items(
        document_id="spec_001",
        is_rag_enabled=True,
        label="text"
    )
    print(f"文档 spec_001 共有 {len(rag_items)} 个启用 RAG 的文本项")


def example_use_extractors():
    """示例：使用提取器处理 item"""
    from docling.datamodel.base_models import DocItemLabel
    from smartcard_kb.docs_compile import get_extractor

    # 获取表格提取器
    table_extractor = get_extractor(DocItemLabel.TABLE)

    # 假设你有一个 docling item
    # normalized_item = table_extractor.extract(item, context)


if __name__ == "__main__":
    # 初始化数据库
    init_database()

    # 运行示例
    example_parse_pdf()
    example_query_items()
