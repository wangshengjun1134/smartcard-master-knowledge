#!/usr/bin/env python
"""
导出数据库表数据到 CSV 文件

用法：
    python scripts/export_db_data.py [--output-dir OUTPUT_DIR]
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extras


def export_table_to_csv(conn, table_name: str, output_path: Path):
    """导出单个表到 CSV 文件"""
    print(f"正在导出 {table_name}...")

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY created_at")
    rows = cursor.fetchall()

    if not rows:
        print(f"  ⚠️  {table_name} 表为空，跳过")
        cursor.close()
        return

    # 获取列名
    columns = list(rows[0].keys())

    # 写入 CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for row in rows:
            # 将非字符串类型转换为字符串
            csv_row = {}
            for col in columns:
                value = row[col]
                if isinstance(value, (dict, list)):
                    csv_row[col] = json.dumps(value, ensure_ascii=False)
                elif isinstance(value, datetime):
                    csv_row[col] = value.isoformat()
                else:
                    csv_row[col] = value
            writer.writerow(csv_row)

    print(f"  ✅ {table_name}: {len(rows)} 条记录 → {output_path}")
    cursor.close()


def main():
    parser = argparse.ArgumentParser(description="导出数据库表数据到 CSV")
    parser.add_argument(
        "--output-dir",
        default="output/db_export",
        help="输出目录（默认: output/db_export）",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 连接数据库
    print("正在连接数据库...")
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="123456",
        dbname="smartcard_master_knowledge",
    )

    tables = ["doc_info", "doc_items", "doc_chunks"]

    print(f"\n开始导出 {len(tables)} 个表...\n")
    for table in tables:
        output_path = output_dir / f"{table}.csv"
        export_table_to_csv(conn, table, output_path)

    conn.close()
    print(f"\n✅ 导出完成！文件保存在: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
