"""测试 Docling + TOC 骨架方案进行 PDF 层级解析"""

import sys
import json
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.smartcard_kb.document import DoclingPDFProcessor
from toc_skeleton import SGP41_TOC, build_skeleton_tree, detect_page_offset, assign_blocks_to_skeleton


# ==================== Docling 解析 ====================

def parse_pdf_with_docling(pdf_path: str, page_range: tuple = None) -> list:
    """
    使用 Docling 解析 PDF，返回扁平化的 block 列表。

    每个 block 包含:
    - type: "title" | "text" | "image" | "table"
    - text: 内容文本
    - page_idx: 页码（0-based）
    """
    print(f"使用 Docling 解析 PDF: {pdf_path}")
    if page_range:
        print(f"  页面范围: {page_range}")

    processor = DoclingPDFProcessor(do_ocr=False)

    kwargs = {
        "pdf_path": pdf_path,
        "output_dir": "output/pictures",
        "document_id": "sgp41_docling_skeleton",
    }
    if page_range:
        kwargs["page_range"] = page_range

    flat_items = processor.process_pdf(**kwargs)
    print(f"Docling 解析完成，共 {len(flat_items)} 个 item")

    # 将 Docling items 转换为统一的 block 格式
    blocks = []
    for item in flat_items:
        item_type = item.get("type", "")
        page = item.get("page", 1)
        page_idx = page - 1  # 转为 0-based

        heading_path = item.get("heading_path", [])

        if item_type == "section_header" and heading_path:
            # 标题：取 heading_path 最后一个元素
            blocks.append({
                "type": "title",
                "text": heading_path[-1],
                "page_idx": page_idx,
            })
        elif item_type == "picture":
            blocks.append({
                "type": "image",
                "img_path": item.get("text", ""),
                "page_idx": page_idx,
            })
        elif item_type == "table":
            blocks.append({
                "type": "table",
                "text": item.get("text", ""),
                "page_idx": page_idx,
            })
        else:
            text = item.get("text", "")
            if text.strip():
                blocks.append({
                    "type": "text",
                    "text": text.strip(),
                    "page_idx": page_idx,
                })

    print(f"转换为 {len(blocks)} 个 block")
    return blocks


# ==================== 测试入口 ====================

def test_hierarchical_parse():
    """使用 Docling + TOC 骨架方案解析 PDF 并输出层级 JSON"""

    pdf_path = "specs/03-management-provisioning/gsma/SGP.41/SGP.41-eSIM-IFPP-Architecture-and-Requirements-v1.0.pdf"
    output_json_path = "tests/output/sgp41_hierarchical_full.json"

    print("=" * 80)
    print("Docling + TOC 骨架方案 PDF 层级解析测试")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print()

    if not Path(pdf_path).exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return

    # 第 1 步：Docling 解析 PDF，提取 blocks
    print("步骤 1: Docling 解析 PDF...")
    blocks = parse_pdf_with_docling(pdf_path)
    print(f"  提取 {len(blocks)} 个 block")

    # 打印 block 类型分布
    type_dist = {}
    for block in blocks:
        t = block.get("type", "unknown")
        type_dist[t] = type_dist.get(t, 0) + 1
    print("  Block 类型分布:")
    for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}")
    print()

    # 第 2 步：构建 TOC 骨架
    print("步骤 2: 构建 TOC 骨架...")
    skeleton = build_skeleton_tree(SGP41_TOC)
    skeleton_count = sum(1 for _ in _iter_nodes(skeleton))
    print(f"  骨架节点数: {skeleton_count}")
    print()

    # 第 3 步：检测页码偏移
    print("步骤 3: 检测页码偏移...")
    offset = detect_page_offset(SGP41_TOC, blocks)
    print(f"  页码偏移: {offset} (physical = toc_page + {offset})")
    print()

    # 第 4 步：将 blocks 分配到骨架节点
    print("步骤 4: 将 blocks 分配到骨架节点...")
    hierarchy = assign_blocks_to_skeleton(skeleton, blocks, page_offset=offset)
    print()

    # 打印层级预览
    print("-" * 60)
    print("层级结构预览:")
    print("-" * 60)

    def print_tree(nodes: list, indent: int = 0):
        for node in nodes:
            pfx = "  " * indent
            ctx_count = len(node.get("contexts", []))
            child_count = len(node.get("children", []))
            pages = f"p{node.get('start_index', '?')}-{node.get('end_index', '?')}"
            print(f"{pfx}[{node['node_id']}] {node['title'][:50]}  ({pages}, {ctx_count} ctx, {child_count} ch)")
            if node.get("children"):
                print_tree(node["children"], indent + 1)

    print_tree(hierarchy)
    print()

    # 输出 JSON
    Path(output_json_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(hierarchy, f, ensure_ascii=False, indent=2)

    print(f"✅ 层级 JSON 已保存到: {output_json_path}")
    print()

    # 统计
    total_nodes = sum(1 for _ in _iter_nodes(hierarchy))
    total_contexts = sum(len(n.get("contexts", [])) for n in _iter_nodes(hierarchy))

    print("=" * 80)
    print("统计:")
    print(f"  - 总节点数: {total_nodes}")
    print(f"  - 总 context 数: {total_contexts}")
    print(f"  - Docling block 数: {len(blocks)}")
    print(f"  - 页码偏移: {offset}")
    print("=" * 80)


def _iter_nodes(nodes: list):
    """递归遍历所有节点（扁平迭代器）"""
    for node in nodes:
        yield node
        yield from _iter_nodes(node.get("children", []))


if __name__ == "__main__":
    test_hierarchical_parse()
