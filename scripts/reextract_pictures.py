#!/usr/bin/env python3
"""重新提取所有已解析文档的图片（支持多实例并行）

从 doc_info 表中获取所有 parsed 状态的文档，
使用 docling 重新提取图片并保存到 output/{document_id}/ 目录。

支持多实例并行：使用 FOR UPDATE SKIP LOCKED 防止重复处理。

状态流转：
    parsed -> picturing -> picted

用法:
    # 单实例
    source venv/bin/activate && python3 /home/reextract_pictures.py
    
    # 3个并行实例
    # 终端1:
    source venv/bin/activate && python3 /home/reextract_pictures.py --worker-id 0 --total-workers 3
    # 终端2:
    source venv/bin/activate && python3 /home/reextract_pictures.py --worker-id 1 --total-workers 3
    # 终端3:
    source venv/bin/activate && python3 /home/reextract_pictures.py --worker-id 2 --total-workers 3
"""

import os
import sys
import argparse
from pathlib import Path

# 项目根目录（scripts 的上一级）
PROJECT_ROOT = Path(__file__).parent.parent

# 模型目录（与项目平级，不在项目内部）
MODELS_DIR = PROJECT_ROOT.parent / "models"

# 设置环境变量（必须在导入 smartcard_kb.document 之前设置）
os.environ["DOCLING_MODELS_PATH"] = str(MODELS_DIR / "docling-models")
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "smartcard-master-knowledge" / "src"))

from smartcard_kb.docs_compile.database import get_connection
from smartcard_kb.document import DoclingPDFProcessor


def get_next_document(cur, worker_id: int, total_workers: int):
    """获取下一个待处理的文档（使用 SKIP LOCKED）"""
    cur.execute("""
        SELECT id, document_code, file_name, file_path
        FROM doc_info
        WHERE processing_status = 'parsed'
        ORDER BY id
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    """)
    row = cur.fetchone()

    if row:
        # 锁定该行，更新状态为 picturing，其他 worker 会跳过
        cur.execute("""
            UPDATE doc_info
            SET processing_status = 'picturing'
            WHERE id = %s
        """, (row[0],))
        # 提交事务，释放行锁
        cur.connection.commit()

    return row


def main():
    parser = argparse.ArgumentParser(description='重新提取所有已解析文档的图片')
    parser.add_argument('--worker-id', type=int, default=0, help='Worker ID (默认: 0)')
    parser.add_argument('--total-workers', type=int, default=1, help='总 Worker 数量 (默认: 1)')
    args = parser.parse_args()

    worker_id = args.worker_id
    total_workers = args.total_workers

    conn = get_connection()
    cur = conn.cursor()

    # 初始化处理器
    print(f"Worker {worker_id}/{total_workers} 启动，初始化 DoclingPDFProcessor...")
    processor = DoclingPDFProcessor(do_ocr=True)
    print("处理器初始化完成\n")

    # 统计
    stats = {"success": 0, "failed": 0, "skipped": 0}
    total_pictures = 0
    processed_count = 0

    while True:
        # 获取下一个待处理文档
        row = get_next_document(cur, worker_id, total_workers)
        if not row:
            # 没有更多待处理文档
            time.sleep(2)
            row = get_next_document(cur, worker_id, total_workers)
            if not row:
                print(f"\nWorker {worker_id}: 没有更多待处理文档\n")
                break

        doc_id, doc_code, file_name, file_path = row

        # 构建 PDF 绝对路径
        pdf_path = f"/home/smartcard-master-knowledge/{file_path}"

        # 检查文件是否存在
        if not Path(pdf_path).exists():
            print(f"[Worker {worker_id}] {doc_code:15s} | {file_name[:40]:40s} | ✗ 文件不存在")
            stats["failed"] += 1
            conn.rollback()
            continue

        # 输出目录
        output_dir = f"/home/smartcard-master-knowledge/output/pictures/{doc_id}"

        # 检查图片目录是否已存在（避免重复处理）
        output_path = Path(output_dir)
        if output_path.exists() and any(output_path.iterdir()):
            existing_count = len(list(output_path.iterdir()))
            print(f"○ 已存在 ({existing_count} 张图片)，跳过")
            stats["skipped"] += 1
            processed_count += 1
            # 恢复文档状态为 picted（已提取图片）
            cur.execute("""
                UPDATE doc_info 
                SET processing_status = 'picted'
                WHERE id = %s
            """, (doc_id,))
            conn.commit()
            continue

        print(f"[Worker {worker_id}] {doc_code:15s} | {file_name[:40]:40s} | ", end="", flush=True)

        try:
            # 提取图片
            items = processor.process_pdf(pdf_path, output_dir=output_dir, document_id=doc_id)

            # 统计图片数量
            picture_count = sum(1 for item in items if item.get("type") == "picture")
            total_pictures += picture_count

            if picture_count > 0:
                print(f"✓ {picture_count} 张图片 -> {output_dir}")
            else:
                print(f"○ 无图片")
                stats["skipped"] += 1

            stats["success"] += 1
            processed_count += 1

            # 更新文档状态为 picted（已提取图片）
            cur.execute("""
                UPDATE doc_info 
                SET processing_status = 'picted'
                WHERE id = %s
            """, (doc_id,))
            conn.commit()

        except Exception as e:
            print(f"✗ 错误: {str(e)[:50]}")
            stats["failed"] += 1
            conn.rollback()

    cur.close()
    conn.close()

    # 输出统计
    print(f"\n{'='*60}")
    print(f"Worker {worker_id} 完成统计:")
    print(f"  成功: {stats['success']}")
    print(f"  跳过: {stats['skipped']}")
    print(f"  失败: {stats['failed']}")
    print(f"  总计: {stats['success'] + stats['skipped'] + stats['failed']}")
    print(f"  总图片数: {total_pictures}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
