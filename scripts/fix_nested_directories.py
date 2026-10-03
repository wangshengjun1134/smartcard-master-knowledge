#!/usr/bin/env python3
"""修复嵌套目录结构

将 output/pictures/{document_id}/{document_id}/ 结构修复为 output/pictures/{document_id}/

用法:
    python3 /home/fix_nested_directories.py
"""

import shutil
from pathlib import Path


def main():
    pictures_dir = Path("/home/smartcard-master-knowledge/output/pictures")
    
    fixed = 0
    skipped = 0
    
    print("开始修复嵌套目录...\n")
    
    for doc_dir in sorted(pictures_dir.iterdir()):
        if not doc_dir.is_dir():
            continue
        
        doc_id = doc_dir.name
        
        # 检查是否存在嵌套的子目录
        nested_dir = doc_dir / doc_id
        if not nested_dir.exists() or not nested_dir.is_dir():
            # 没有嵌套结构，跳过
            skipped += 1
            continue
        
        # 检查嵌套目录中是否有文件
        files = list(nested_dir.iterdir())
        if not files:
            # 空目录，直接删除
            nested_dir.rmdir()
            print(f"○ {doc_id}: 空嵌套目录，已删除")
            skipped += 1
            continue
        
        # 将嵌套目录中的文件移动到外层
        for file in files:
            target = doc_dir / file.name
            if target.exists():
                # 如果外层已存在同名文件，跳过
                print(f"⚠ {doc_id}: {file.name} 已存在，跳过")
                continue
            file.rename(target)
        
        # 删除嵌套目录
        nested_dir.rmdir()
        fixed += 1
        print(f"✓ {doc_id}: 已修复 ({len(files)} 个文件)")
    
    print(f"\n{'='*60}")
    print(f"修复完成!")
    print(f"  已修复: {fixed}")
    print(f"  已跳过: {skipped}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
