"""测试脚本 - 测试 textualize 功能"""

import sys
import io
from pathlib import Path

# 设置 UTF-8 编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from smartcard_kb.docs_compile import (
    query_items_needing_textualization,
    textualize_item,
    textualize_all_items,
    update_item_textualization,
    query_document_items,
)


def test_textualize_dry_run():
    """测试文本化功能（dry_run 模式，不更新数据库）"""
    print("=" * 60)
    print("[TEST] 测试 textualize 功能（dry_run 模式）")
    print("=" * 60)

    # 查询待文本化的 item
    items = query_items_needing_textualization(
        document_id="SGP.01-v1.12",
        limit=20
    )

    print(f"\n[INFO] 找到 {len(items)} 条待文本化的记录")

    # 按类型分组统计
    type_stats = {}
    for item in items:
        label = item.get("label", "unknown")
        type_stats[label] = type_stats.get(label, 0) + 1

    print("\n[INFO] 待文本化记录类型分布:")
    for label, count in sorted(type_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {label}: {count}")

    # 测试每种类型的文本化
    print("\n" + "=" * 60)
    print("[TEST] 测试各类型文本化:")
    print("=" * 60)

    tested_labels = set()
    for item in items:
        label = item.get("label", "")
        if label in tested_labels:
            continue

        result = textualize_item(item)
        if result:
            print(f"\n[OK] [{label}] {item['id'][:8]}...")
            print(f"   长度: {len(result)} chars")
            print(f"   预览: {result[:100]}..." if len(result) > 100 else f"   内容: {result}")
            tested_labels.add(label)

        if len(tested_labels) >= 5:
            break

    print("\n" + "=" * 60)
    print("[OK] Dry run 测试完成!")


def test_textualize_all():
    """测试批量文本化功能"""
    print("=" * 60)
    print("[TEST] 测试批量 textualize 功能")
    print("=" * 60)

    # 执行文本化（dry_run 模式）
    stats = textualize_all_items(
        document_id="SGP.01-v1.12",
        dry_run=True,
        batch_size=20
    )

    print(f"\n[INFO] 文本化统计:")
    print(f"  - 总计: {stats['total']}")
    print(f"  - 成功: {stats['success']}")
    print(f"  - 失败: {stats['failed']}")


def test_update_textualization():
    """测试更新 textualization 字段"""
    print("\n" + "=" * 60)
    print("[TEST] 测试更新 textualization 字段")
    print("=" * 60)

    # 查询第一条待文本化的记录
    items = query_items_needing_textualization(
        document_id="SGP.01-v1.12",
        limit=1
    )

    if not items:
        print("[WARN] 没有待文本化的记录")
        return

    item = items[0]
    item_id = item["id"]
    label = item.get("label", "")

    print(f"\n[INFO] 测试 item: {item_id}")
    print(f"   类型: {label}")

    # 文本化
    result = textualize_item(item)
    if result:
        print(f"   文本化成功: {len(result)} chars")

        # 更新数据库
        update_item_textualization(item_id, result)
        print(f"   [OK] 已更新数据库")

        # 验证更新
        updated_items = query_document_items(document_id="SGP.01-v1.12")
        updated_item = next((i for i in updated_items if i["id"] == item_id), None)

        if updated_item and updated_item.get("textualization"):
            print(f"   [OK] 验证成功: textualization 字段已更新")
            print(f"   内容预览: {updated_item['textualization'][:100]}...")
        else:
            print(f"   [FAIL] 验证失败: textualization 字段未更新")
    else:
        print(f"   [FAIL] 文本化失败")


def test_textualization_summary():
    """测试文本化统计"""
    print("\n" + "=" * 60)
    print("[INFO] 文本化统计汇总")
    print("=" * 60)

    # 查询所有已文本化的记录
    all_items = query_document_items(document_id="SGP.01-v1.12")
    textualized = [i for i in all_items if i.get("textualization")]

    print(f"\n[INFO] 文档 SGP.01-v1.12 文本化状态:")
    print(f"  - 总记录数: {len(all_items)}")
    print(f"  - 已文本化: {len(textualized)}")
    print(f"  - 待文本化: {len(all_items) - len(textualized)}")

    # 按类型统计
    type_stats = {}
    for item in all_items:
        label = item.get("label", "unknown")
        has_textualization = 1 if item.get("textualization") else 0
        if label not in type_stats:
            type_stats[label] = {"total": 0, "textualized": 0}
        type_stats[label]["total"] += 1
        type_stats[label]["textualized"] += has_textualization

    print(f"\n[INFO] 按类型统计:")
    for label, stats in sorted(type_stats.items()):
        pct = (stats["textualized"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  - {label}: {stats['textualized']}/{stats['total']} ({pct:.1f}%)")


if __name__ == "__main__":
    # 运行测试
    test_textualize_dry_run()
    test_textualize_all()
    test_update_textualization()
    test_textualization_summary()
