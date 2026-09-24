"""docs_compile 模块 - 基于 Docling 的 PDF 文档编译和结构化提取"""

from .database import (
    init_database,
    insert_document_item,
    insert_document_items,
    query_document_items,
    delete_document_items_by_document,
    get_document_stats,
    # document_info 表操作
    insert_document_info,
    query_document_info,
    update_document_info_stats,
    delete_document_info,
)
from .pdf_parser import PDFParser
from .extractors import (
    DocItemExtractor,
    NormalizedItem,
    TextExtractor,
    TitleExtractor,
    TableExtractor,
    PictureExtractor,
    FormulaExtractor,
    DocumentIndexExtractor,
    ListItemExtractor,
    extractors,
    get_extractor,
    extract_item,
)

__all__ = [
    # database - document_item
    "init_database",
    "insert_document_item",
    "insert_document_items",
    "query_document_items",
    "delete_document_items_by_document",
    "get_document_stats",
    # database - document_info
    "insert_document_info",
    "query_document_info",
    "update_document_info_stats",
    "delete_document_info",
    # pdf_parser
    "PDFParser",
    # extractors
    "DocItemExtractor",
    "NormalizedItem",
    "TextExtractor",
    "TitleExtractor",
    "TableExtractor",
    "PictureExtractor",
    "FormulaExtractor",
    "DocumentIndexExtractor",
    "ListItemExtractor",
    "extractors",
    "get_extractor",
    "extract_item",
]
