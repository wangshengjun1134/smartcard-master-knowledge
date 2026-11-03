"""
从 specs/ 目录树导入 doc_directory 表数据

用法：
    cd /home/buff/workspaces/smartcard/smartcard-master-knowledge
    source venv/bin/activate
    python scripts/import_directory.py [--root specs] [--dry-run]
"""

import argparse
import os
import sys
from pathlib import Path

# 确保 src 在 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from smartcard_kb.docs_compile.database import init_database, get_connection, query_all_directories


def scan_directory_tree(root_path: Path) -> list:
    """
    递归扫描目录树，返回扁平化的目录记录列表。

    每条记录: {name, relative_path, level, parent_relative_path}
    """
    records = []
    root_path = root_path.resolve()

    def _scan(dir_path: Path, level: int):
        # 获取直接子目录，按名称排序
        subdirs = sorted(
            [d for d in dir_path.iterdir() if d.is_dir() and not d.name.startswith(".")],
            key=lambda d: d.name,
        )

        for sort_order, subdir in enumerate(subdirs):
            rel_path = str(subdir.relative_to(root_path.parent))  # 相对于 root 的父目录
            records.append({
                "name": subdir.name,
                "relative_path": rel_path,
                "level": level,
                "sort_order": sort_order,
                "parent_relative_path": str(dir_path.relative_to(root_path.parent)) if dir_path != root_path.parent else "",
            })
            _scan(subdir, level + 1)

    _scan(root_path, 1)
    return records


def import_directories(root_path: Path, dry_run: bool = False):
    """将目录树导入 doc_directory 表"""
    init_database()

    records = scan_directory_tree(root_path)
    print(f"扫描到 {len(records)} 个目录")

    if dry_run:
        for r in records:
            indent = "  " * (r["level"] - 1)
            print(f"  {indent}{r['name']} (level={r['level']}, path=/{r['relative_path']})")
        print(f"\n[dry-run] 共 {len(records)} 条记录，未写入数据库")
        return

    # 检查是否已有数据
    existing = query_all_directories()
    if existing:
        print(f"数据库已有 {len(existing)} 条目录记录，跳过导入（如需重新导入请先清空表）")
        return

    # 按层级排序，确保父目录先插入
    records.sort(key=lambda r: (r["level"], r["relative_path"]))

    # path -> id 映射，用于设置 parent_id
    path_to_id = {"": 0}  # 空 path 对应顶级（parent_id=0）
    conn = get_connection()
    cursor = conn.cursor()

    inserted = 0
    for r in records:
        parent_id = path_to_id.get(r["parent_relative_path"], 0)
        # path 格式：/1/5/12/（用 ID 构建，但首次导入时 ID 尚未知）
        # 先用相对路径作为临时 path，后续可更新
        mat_path = f"/{r['relative_path']}/"

        cursor.execute(
            """
            INSERT INTO doc_directory (parent_id, name, path, level, sort_order)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (parent_id, r["name"], mat_path, r["level"], r["sort_order"]),
        )
        new_id = cursor.fetchone()[0]
        path_to_id[r["relative_path"]] = new_id
        inserted += 1

    conn.commit()

    # 更新 path 为物化路径（用实际 ID）
    # 重新构建 path：从根到叶的 ID 链
    id_to_parent = {}
    id_to_name = {}
    for r in records:
        dir_id = path_to_id[r["relative_path"]]
        parent_id = path_to_id.get(r["parent_relative_path"], 0)
        id_to_parent[dir_id] = parent_id
        id_to_name[dir_id] = r["name"]

    # 构建每个节点的物化路径
    for dir_id in id_to_parent:
        chain = []
        current = dir_id
        while current != 0:
            chain.append(current)
            current = id_to_parent.get(current, 0)
        chain.reverse()
        mat_path = "/" + "/".join(str(x) for x in chain) + "/"

        cursor.execute(
            "UPDATE doc_directory SET path = %s WHERE id = %s",
            (mat_path, dir_id),
        )

    conn.commit()
    cursor.close()
    conn.close()

    print(f"✅ 成功导入 {inserted} 条目录记录")

    # 验证
    all_dirs = query_all_directories()
    print(f"数据库当前共 {len(all_dirs)} 条目录记录")
    for d in all_dirs[:10]:
        indent = "  " * (d["level"] - 1)
        print(f"  {indent}[{d['id']}] {d['name']} (path={d['path']})")
    if len(all_dirs) > 10:
        print(f"  ... 共 {len(all_dirs)} 条")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 specs/ 目录导入 doc_directory")
    parser.add_argument("--root", default="specs", help="根目录路径（默认 specs）")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不写入")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"❌ 目录不存在: {root}")
        sys.exit(1)

    print(f"根目录: {root}")
    import_directories(root, dry_run=args.dry_run)
