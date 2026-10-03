#!/usr/bin/env python3
"""批量解析 embedded 状态的文档（支持多实例并发）

使用 PostgreSQL 的 SKIP LOCKED 特性，多个脚本实例并发处理时
不会重复处理同一个文档。

用法:
    source venv/bin/activate && python3 /home/parse_embedded_docs.py --port 8000 --worker-id 0
"""

import subprocess
import time
import sys
import argparse
from smartcard_kb.docs_compile.database import get_connection

# 禁用输出缓冲
sys.stdout.reconfigure(line_buffering=True)

# 配置
API_BASE_URL = "http://localhost:{port}/api/docs/process/parse"
CURL_TIMEOUT = 300  # curl 超时（秒）
PARSE_TIMEOUT = 600  # 单个文档解析等待超时（秒）
POLL_INTERVAL = 2  # 轮询间隔（秒）


def get_next_document(cur):
    """获取下一个待处理的文档（使用 SKIP LOCKED）"""
    cur.execute("""
        SELECT id, document_code, file_name, file_path 
        FROM doc_info 
        WHERE processing_status = 'embedded'
        ORDER BY id
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    """)
    row = cur.fetchone()
    
    if row:
        # 立即更新状态为 parsing 并提交，释放行锁
        cur.execute("""
            UPDATE doc_info 
            SET processing_status = 'parsing', processing_error = NULL
            WHERE id = %s
        """, (row[0],))
        # 提交事务，释放行锁
        cur.connection.commit()
    
    return row


def main():
    parser = argparse.ArgumentParser(description='批量解析 embedded 状态的文档')
    parser.add_argument('--port', type=int, default=8000, help='API 端口 (默认: 8000)')
    parser.add_argument('--worker-id', type=int, default=0, help='Worker ID (默认: 0)')
    args = parser.parse_args()

    api_url = API_BASE_URL.format(port=args.port)
    worker_id = args.worker_id

    conn = get_connection()
    cur = conn.cursor()

    # 统计
    stats = {"success": 0, "failed": 0, "timeout": 0}
    processed_count = 0

    print(f"Worker {worker_id} 启动，API 端口: {args.port}\n")

    while True:
        # 获取下一个待处理文档（会自动更新状态并释放锁）
        row = get_next_document(cur)
        if not row:
            # 没有更多待处理文档，等待或退出
            time.sleep(5)
            row = get_next_document(cur)
            if not row:
                print(f"\nWorker {worker_id}: 没有更多待处理文档\n")
                break

        doc_id, doc_code, file_name, file_path = row

        # 构建绝对路径
        pdf_path = f"/home/smartcard-master-knowledge/{file_path}"

        # 构建 curl 命令
        curl_cmd = (
            f"curl -s --max-time {CURL_TIMEOUT} '{api_url}' "
            f"-X POST "
            f"-H 'Content-Type: application/json' "
            f"--data-raw '{{\"pdf_path\":\"{pdf_path}\",\"document_id\":\"{doc_id}\",\"do_ocr\":true}}'"
        )

        print(f"[Worker {worker_id}] {doc_code:15s} | {file_name[:45]:45s} | ", end="", flush=True)

        # 执行 curl
        try:
            result = subprocess.run(curl_cmd, shell=True, capture_output=True, text=True, timeout=CURL_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"✗ curl 超时 ({CURL_TIMEOUT}s)")
            stats["failed"] += 1
            continue

        if result.returncode != 0:
            print(f"✗ 请求失败 (exit={result.returncode})")
            stats["failed"] += 1
            continue

        # 轮询等待解析完成
        parsed = False
        elapsed = 0
        while elapsed < PARSE_TIMEOUT:
            time.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

            cur.execute(
                "SELECT processing_status, item_count, processing_error FROM doc_info WHERE id = %s;",
                (doc_id,)
            )
            status_row = cur.fetchone()
            if not status_row:
                continue

            status = status_row[0]

            if status == 'parsed':
                print(f"✓ {status_row[1]} items ({elapsed}s)")
                stats["success"] += 1
                parsed = True
                break
            elif status == 'parse_failed':
                error = status_row[2] if status_row[2] else "unknown"
                print(f"✗ {error[:60]} ({elapsed}s)")
                stats["failed"] += 1
                parsed = True
                break

        if not parsed:
            print(f"⚠ 超时 ({PARSE_TIMEOUT}s，仍在解析中)")
            stats["timeout"] += 1

        processed_count += 1

    cur.close()
    conn.close()

    # 输出统计
    print(f"\n{'='*60}")
    print(f"Worker {worker_id} 完成统计:")
    print(f"  成功: {stats['success']}")
    print(f"  失败: {stats['failed']}")
    print(f"  超时: {stats['timeout']}")
    print(f"  总计: {stats['success'] + stats['failed'] + stats['timeout']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
