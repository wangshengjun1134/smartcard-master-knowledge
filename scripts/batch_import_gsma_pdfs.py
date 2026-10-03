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

# 使用脚本所在目录自动计算项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
GSMA_DIR = PROJECT_ROOT / "specs" / "03-management-provisioning" / "gsma"


def extract_doc_info(file_path: Path) -> dict:
    """从文件名提取文档信息"""
    name = file_path.name.replace(".pdf", "")
    
    # 提取 series_id (如 SGP.01, SGP.23-1, SGP.11-4)
    # 使用负向前瞻：如果 -数字 后面跟着 .数字，说明是版本号而非子系列号
    # 例如：SGP.29-1.0 → SGP.29 (因为 -1 后面是 .0)，SGP.23-1-v3.1 → SGP.23-1
    match = re.match(r'(SGP\.\d+(?:-\d+)?)(?!\.\d)', name, re.IGNORECASE)
    series_id = match.group(1).upper().replace("_", "-") if match else None

    # 提取 revision - 支持多种格式：
    # 1. 带 v 前缀：SGP.01-v1.12.pdf → revision=1.12
    # 2. 带 v 前缀含连字符：SGP.05v1-0.pdf → revision=1-0
    # 3. 不带 v 前缀：SGP.29-1.0.pdf → revision=1.0
    # 4. 多段版本号：SGP.32-1.0.1.pdf → revision=1.0.1
    revision = None

    # 先尝试带 v 前缀的格式（支持 . 和 - 分隔的版本号）
    rev_match = re.search(r'[vV](\d+(?:[\.-]\d+)*)', name)
    if rev_match:
        revision = rev_match.group(1)
    elif series_id:
        # 如果不带 v，尝试从系列号后提取版本号
        # 例如：SGP.29-1.0 → 系列号 SGP.29，版本号 1.0
        suffix = name[len(series_id):]  # 移除系列号前缀
        suffix_match = re.match(r'[._-]?(\d+(?:\.\d+)*)', suffix)
        if suffix_match:
            revision = suffix_match.group(1)
    
    # document_code = series_id + "-v" + revision
    document_code = f"{series_id}-v{revision}" if series_id and revision else series_id
    
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
            relative_path = pdf_file.relative_to(PROJECT_ROOT)
            # 使用正斜杠路径（跨平台兼容）
            file_path_str = str(relative_path).replace("\\", "/")
            
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
