"""测试 PDF 层级解析：将 Docling 扁平 item 列表转换为层级 JSON 结构"""

import sys
import json
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.smartcard_kb.document import DoclingPDFProcessor


def _parse_heading_level(title: str) -> tuple:
    """
    从标题文本中解析出层级深度。

    "3 Architecture"           -> depth=1, prefix="3"
    "3.1 Architecture Diagram" -> depth=2, prefix="3.1"
    "3.2.1 SM-DPf"            -> depth=3, prefix="3.2.1"
    "Security Classification"  -> depth=1 (无编号，视为顶层)

    返回 (depth, prefix)，depth 从 1 开始。
    """
    stripped = title.strip()
    # 匹配开头的数字编号：1, 1.2, 3.2.1, 10.3.2.1 等
    import re
    m = re.match(r'^(\d+(?:\.\d+)*)\s+', stripped)
    if m:
        prefix = m.group(1)
        depth = len(prefix.split('.'))
        return depth, prefix
    # 无编号标题（如 "Security Classification"），视为 depth=1
    return 1, ""


def build_hierarchy(flat_items: list) -> list:
    """
    将扁平的 item 列表（含 heading_path）转换为层级树结构。

    Docling 的 heading_path 只包含当前直接标题（单元素列表），
    因此需要根据标题编号的点分层级（如 3 → 3.1 → 3.2.1）来构建树。
    使用 prefix_map 精确匹配父子关系，避免将 1.1 错误挂到 Table of Contents 下。
    """
    root_nodes = []
    level_counters = {}

    def next_node_id(level: int) -> str:
        level_counters[level] = level_counters.get(level, 0) + 1
        return f"l{level}-{level_counters[level]}"

    def make_node(title: str, level: int, parent_id: str) -> dict:
        return {
            "title": title,
            "node_id": next_node_id(level),
            "parent_id": parent_id,
            "start_index": None,
            "end_index": None,
            "contexts": [],
            "summary": "",
            "children": [],
        }

    def update_page_range(node: dict, page: int):
        if page is None:
            return
        if node["start_index"] is None or page < node["start_index"]:
            node["start_index"] = page
        if node["end_index"] is None or page > node["end_index"]:
            node["end_index"] = page

    # prefix -> node 映射，用于精确查找父级
    # 例如: "1" -> node("1 Introduction"), "3.2" -> node("3.2 Interfaces")
    prefix_map: dict[str, dict] = {}
    untitled_node = None

    def add_context(node: dict, item: dict):
        """添加 context 到节点，seq 在当前节点的 contexts 内从 1 递增"""
        label = item.get("type", "text")
        if label == "picture":
            label = "image"
        seq = len(node["contexts"]) + 1
        node["contexts"].append({
            "seq": seq,
            "label": label,
            "context": item.get("text", ""),
            "start_index": item.get("page"),
            "end_index": item.get("page"),
        })

    def get_or_create_parent(prefix: str) -> tuple:
        """
        根据编号前缀获取或创建父节点，返回 (parent_children_list, parent_id)。

        - prefix=""  → root_nodes
        - prefix="1" → root_nodes（顶层）
        - prefix="3.2" → prefix_map["3"] 的 children
        - 如果父级不存在，自动创建隐式父级
        """
        if not prefix:
            return root_nodes, ""

        parts = prefix.split('.')
        if len(parts) == 1:
            # 顶层节点（如 "1", "2", "3"），父级是 root
            return root_nodes, ""

        # 父级前缀 = 去掉最后一段（如 "3.2.1" → "3.2"）
        parent_prefix = '.'.join(parts[:-1])

        if parent_prefix in prefix_map:
            parent = prefix_map[parent_prefix]
            return parent["children"], parent["node_id"]

        # 父级不存在，递归创建
        get_or_create_parent(parent_prefix)
        # 创建隐式父级节点
        parent_node = make_node(parent_prefix, len(parts) - 1,
                                prefix_map.get('.'.join(parts[:-2]))["node_id"] if '.'.join(parts[:-2]) in prefix_map else "")
        # 找到正确的父级 children 列表
        grandparent_prefix = '.'.join(parts[:-2]) if len(parts) > 2 else ""
        if grandparent_prefix and grandparent_prefix in prefix_map:
            prefix_map[grandparent_prefix]["children"].append(parent_node)
        else:
            root_nodes.append(parent_node)
        prefix_map[parent_prefix] = parent_node
        return parent_node["children"], parent_node["node_id"]

    for item in flat_items:
        heading_path = item.get("heading_path", [])
        page = item.get("page")

        # heading_path 为空 = 顶层无标题内容
        if not heading_path:
            if untitled_node is None:
                untitled_node = make_node("(Untitled Section)", 0, "")
                root_nodes.append(untitled_node)
            add_context(untitled_node, item)
            update_page_range(untitled_node, page)
            continue

        heading_title = heading_path[-1]
        depth, prefix = _parse_heading_level(heading_title)

        # 获取正确的父级 children 列表
        parent_children, parent_id = get_or_create_parent(prefix)

        # 查找或创建当前标题节点
        node = None
        for child in parent_children:
            if child["title"] == heading_title:
                node = child
                break

        if node is None:
            node = make_node(heading_title, depth, parent_id)
            parent_children.append(node)
            if prefix:
                prefix_map[prefix] = node

        # 非 heading 类型的内容添加到 contexts
        if item.get("type") not in ("section_header",):
            add_context(node, item)

        update_page_range(node, page)

    # 后处理：从子节点和 contexts 向上冒泡页码范围
    def finalize_page_ranges(nodes: list):
        for node in nodes:
            if node["children"]:
                finalize_page_ranges(node["children"])
                for child in node["children"]:
                    if child["start_index"] is not None:
                        update_page_range(node, child["start_index"])
                    if child["end_index"] is not None:
                        update_page_range(node, child["end_index"])
            for ctx in node["contexts"]:
                if ctx["start_index"] is not None:
                    update_page_range(node, ctx["start_index"])
                if ctx["end_index"] is not None:
                    update_page_range(node, ctx["end_index"])

    finalize_page_ranges(root_nodes)

    # 后处理：合并同一节点内相邻且 label 相同的 context（跨页同类内容合并为一条）
    def merge_consecutive_contexts(nodes: list):
        for node in nodes:
            merge_consecutive_contexts(node.get("children", []))
            ctxs = node.get("contexts", [])
            if len(ctxs) <= 1:
                continue
            merged = [ctxs[0].copy()]
            for ctx in ctxs[1:]:
                prev = merged[-1]
                if ctx["label"] == prev["label"]:
                    # 合并：内容拼接，页码取并集
                    prev["context"] = prev["context"] + "\n" + ctx["context"]
                    if ctx["start_index"] is not None:
                        if prev["start_index"] is None or ctx["start_index"] < prev["start_index"]:
                            prev["start_index"] = ctx["start_index"]
                    if ctx["end_index"] is not None:
                        if prev["end_index"] is None or ctx["end_index"] > prev["end_index"]:
                            prev["end_index"] = ctx["end_index"]
                else:
                    merged.append(ctx.copy())
            # 重新编号 seq
            for i, ctx in enumerate(merged):
                ctx["seq"] = i + 1
            node["contexts"] = merged

    merge_consecutive_contexts(root_nodes)

    return root_nodes


def test_hierarchical_parse():
    """测试 PDF 层级解析，输出层级 JSON"""

    pdf_path = "specs/03-management-provisioning/gsma/SGP.41/SGP.41-eSIM-IFPP-Architecture-and-Requirements-v1.0.pdf"
    output_json_path = "tests/output/sgp41_hierarchical_full.json"

    print("=" * 80)
    print("PDF 层级解析测试（完整文档）")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print(f"页面范围: 全部")
    print()

    # 检查文件是否存在
    if not Path(pdf_path).exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return

    # 初始化处理器（开启 OCR）
    print("初始化 DoclingPDFProcessor（OCR 开启）...")
    processor = DoclingPDFProcessor(do_ocr=True)

    # 解析完整 PDF
    print("开始解析 PDF（完整文档）...")
    flat_items = processor.process_pdf(
        pdf_path=pdf_path,
        output_dir="output/pictures",
        document_id="sgp41_full",
    )

    print(f"解析完成，共提取 {len(flat_items)} 个 item")
    print()

    # 打印扁平结构预览
    print("-" * 60)
    print("扁平 item 预览（前 20 个）:")
    print("-" * 60)
    for i, item in enumerate(flat_items[:20]):
        text_preview = (item.get("text") or "")[:80].replace("\n", " ")
        heading = " > ".join(item.get("heading_path", []))
        print(f"  [{i+1:3d}] page={item.get('page')} type={item.get('type'):15s} heading=[{heading}]")
        print(f"        text: {text_preview}...")
    if len(flat_items) > 20:
        print(f"  ... 共 {len(flat_items)} 个 item")
    print()

    # 构建层级结构
    print("-" * 60)
    print("构建层级结构...")
    print("-" * 60)
    hierarchy = build_hierarchy(flat_items)

    # 打印层级预览
    def print_tree(nodes: list, indent: int = 0):
        for node in nodes:
            prefix = "  " * indent
            ctx_count = len(node.get("contexts", []))
            child_count = len(node.get("children", []))
            pages = f"p{node.get('start_index', '?')}-{node.get('end_index', '?')}"
            print(f"{prefix}[{node['node_id']}] {node['title']}  ({pages}, {ctx_count} ctx, {child_count} children)")
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
    def count_nodes(nodes: list):
        total = len(nodes)
        for node in nodes:
            total += count_nodes(node.get("children", []))
        return total

    def count_contexts(nodes: list):
        total = sum(len(n.get("contexts", [])) for n in nodes)
        for node in nodes:
            total += count_contexts(node.get("children", []))
        return total

    total_nodes = count_nodes(hierarchy)
    total_contexts = count_contexts(hierarchy)

    print("=" * 80)
    print("统计:")
    print(f"  - 总节点数: {total_nodes}")
    print(f"  - 总 context 数: {total_contexts}")
    print(f"  - 扁平 item 数: {len(flat_items)}")
    print("=" * 80)


if __name__ == "__main__":
    test_hierarchical_parse()
