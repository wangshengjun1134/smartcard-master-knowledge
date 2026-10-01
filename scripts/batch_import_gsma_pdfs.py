"""批量导入 GSMA PDF 文档到 doc_info 表"""

import sys
import uuid
import hashlib
import re
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from smartcard_kb.docs_compile.database import init_database, insert_document_info, query_document_info

GSMA_DIR = Path(r"D:\softdata\workspaces\buff\smartcard-master-knowledge\specs\03-management-provisioning\gsma")


def extract_doc_info(file_path: Path) -> dict:
    """从文件名提取文档信息"""
    name = file_path.name.replace(".pdf", "")
    
    # 提取 series_id (如 SGP.01, SGP.23-1)
    match = re.match(r'(SGP\.\d+(?:-\d+)?)', name, re.IGNORECASE)
    series_id = match.group(1).upper().replace("_", "-") if match else None
    
    # 提取 revision (如 v1.12, v4.0)
    rev_match = re.search(r'[vV](\d+(?:\.\d+)*)', name)
    revision = rev_match.group(1) if rev_match else None
    
    # document_code = series_id + "-v" + revision
    document_code = f"{series_id}-v{revision}" if series_id and revision else None
    
    return {
        "document_code": document_code,
        "series_id": series_id,
        "revision": revision,
    }


def calculate_hash(file_path: Path) -> str:
    """计算文件 SHA256 哈希"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def main():
    print("="*60)
    print("批量导入 GSMA PDF 文档")
    print("="*60)
    
    # 初始化数据库
    init_database()
    print("✅ 数据库连接成功\n")
    
    # 扫描所有 PDF 文件
    pdf_files = sorted(GSMA_DIR.glob("**/*.pdf"))
    print(f"找到 {len(pdf_files)} 个 PDF 文件\n")
    
    # 统计
    stats = {
        "total": len(pdf_files),
        "skipped": 0,
        "inserted": 0,
        "errors": 0,
    }
    
    # 处理每个文件
    for i, pdf_file in enumerate(pdf_files, 1):
        try:
            # 提取信息
            doc_info = extract_doc_info(pdf_file)
            file_hash = calculate_hash(pdf_file)
            file_size = pdf_file.stat().st_size
            
            # 检查是否已存在
            existing = query_document_info(file_hash=file_hash)
            if existing:
                print(f"[{i}/{stats['total']}] ⚠️  跳过 (已存在): {pdf_file.relative_to(GSMA_DIR.parent.parent)}")
                stats["skipped"] += 1
                continue
            
            # 构建文档记录
            relative_path = pdf_file.relative_to(Path(r"D:\softdata\workspaces\buff\smartcard-master-knowledge"))
            # 使用反斜杠路径（与参考记录一致）
            file_path_str = str(relative_path).replace("/", "\\")
            
            doc_data = {
                "id": str(uuid.uuid4()),
                "document_code": doc_info["document_code"] or "",
                "title": "",
                "series_id": doc_info["series_id"] or "",
                "file_name": pdf_file.name,
                "file_path": file_path_str,
                "file_hash": file_hash,
                "file_size": file_size,
                "file_format": "pdf",
                "page_count": None,
                "revision": doc_info["revision"] or "",
                "publication_date": None,
                "effective_date": None,
                "issuer": "",
                "language": "en",
                "source_type": "upload",
                "parser": "docling",
                "parser_version": None,
                "processing_status": "embedded",
                "processing_started_at": datetime.now().isoformat(),
                "processing_finished_at": None,
                "processing_error": None,
                "item_count": 0,
                "text_count": 0,
                "title_count": 0,
                "table_count": 0,
                "picture_count": 0,
                "formula_count": 0,
                "metadata": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            
            # 插入数据库
            insert_document_info(doc_data)
            stats["inserted"] += 1
            print(f"[{i}/{stats['total']}] ✅ 已导入: {pdf_file.relative_to(GSMA_DIR.parent.parent)}")
            
        except Exception as e:
            stats["errors"] += 1
            print(f"[{i}/{stats['total']}] ❌ 错误: {pdf_file.name} - {e}")
    
    # 输出统计
    print(f"\n{'='*60}")
    print("导入完成!")
    print(f"{'='*60}")
    print(f"总文件数: {stats['total']}")
    print(f"已导入: {stats['inserted']}")
    print(f"已跳过: {stats['skipped']}")
    print(f"错误: {stats['errors']}")


if __name__ == "__main__":
    main()
