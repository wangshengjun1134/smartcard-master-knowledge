"""
上传 specs/ 目录下所有文件到 MinIO，每个对象设置 filename tag 为文件名

用法：
    cd /home/buff/workspaces/smartcard/smartcard-master-knowledge
    source venv/bin/activate
    pip install minio  # 如果还没装
    python scripts/upload_to_minio.py [--bucket specs] [--dry-run]
"""

import argparse
import os
import sys
from pathlib import Path

from minio import Minio
from minio.commonconfig import Tags


def main():
    parser = argparse.ArgumentParser(description="上传 specs/ 到 MinIO")
    parser.add_argument("--endpoint", default="localhost:9000")
    parser.add_argument("--access-key", default="admin")
    parser.add_argument("--secret-key", default="admin123")
    parser.add_argument("--bucket", default="specs")
    parser.add_argument("--source", default="specs", help="本地源目录")
    parser.add_argument("--secure", action="store_true", default=False)
    parser.add_argument("--dry-run", action="store_true", help="只列出文件不上传")
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    if not source_dir.is_dir():
        print(f"❌ 目录不存在: {source_dir}")
        sys.exit(1)

    # 收集所有文件
    files = []
    for f in sorted(source_dir.rglob("*")):
        if f.is_file() and not f.name.startswith("."):
            rel_path = str(f.relative_to(source_dir))
            files.append((f, rel_path))

    print(f"找到 {len(files)} 个文件")
    print(f"MinIO: {args.endpoint}, bucket: {args.bucket}")

    if args.dry_run:
        for f, rel in files:
            print(f"  {rel}  (tag: filename={f.name})")
        print(f"\n[dry-run] 共 {len(files)} 个文件，未上传")
        return

    # 连接 MinIO
    client = Minio(
        args.endpoint,
        access_key=args.access_key,
        secret_key=args.secret_key,
        secure=args.secure,
    )

    # 创建 bucket（如果不存在）
    if not client.bucket_exists(args.bucket):
        client.make_bucket(args.bucket)
        print(f"✅ 创建 bucket: {args.bucket}")

    # 上传文件
    uploaded = 0
    for f, rel_path in files:
        # object name 保持相对路径结构
        object_name = rel_path

        # 设置 tag：filename = 文件名
        tags = Tags(for_object=True)
        tags["filename"] = f.name

        client.fput_object(
            args.bucket,
            object_name,
            str(f),
            tags=tags,
        )
        uploaded += 1
        if uploaded % 20 == 0 or uploaded == len(files):
            print(f"  进度: {uploaded}/{len(files)}")

    print(f"\n✅ 上传完成: {uploaded} 个文件到 {args.bucket}")


if __name__ == "__main__":
    main()
