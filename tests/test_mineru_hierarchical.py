"""测试 MinerU 4.0 框架进行 PDF 层级解析，输出与 Docling 版相同的层级 JSON 结构"""

import sys
import json
import io
import re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


# ==================== MinerU 4.0 解析 ====================

def _extract_text_from_content(content_list) -> str:
    """从 MinerU 4.0 的 content 列表中提取纯文本"""
    if not content_list:
        return ""
    parts = []
    for item in content_list:
        if isinstance(item, str):
            parts.append(item)
        elif hasattr(item, "content"):
            c = item.content
            if isinstance(c, str):
                parts.append(c)
    return "".join(parts).strip()


def _extract_image_path(block) -> str:
    """从 MinerU 4.0 的 image block 中提取图片路径"""
    for item in (block.content or []):
        if hasattr(item, "image_path") and item.image_path:
            return item.image_path
    return ""


def _extract_table_text(block) -> str:
    """从 MinerU 4.0 的 table block 中提取表格文本"""
    for item in (block.content or []):
        if hasattr(item, "content") and isinstance(item.content, str) and item.content.strip():
            return item.content.strip()
    return ""


def parse_pdf_with_mineru(pdf_path: str, page_range: str = "") -> list:
    """
    使用 MinerU 4.0 解析 PDF，返回扁平化的 block 列表。

    每个 block 包含:
    - type: "title" | "text" | "image" | "table"
    - text: 内容文本
    - page_idx: 页码（0-based）
    - level: (title 专用) 标题层级（0-based）
    - img_path: (image 专用) 图片路径
    """
    from mineru.parser import parse

    print(f"使用 MinerU 4.0 解析 PDF: {pdf_path}")
    if page_range:
        print(f"  页面范围: {page_range}")

    result = parse(
        pdf_path,
        tier="basic",
        ocr_mode="txt",
        image_analysis=False,
        page_range=page_range,
    )

    # 将 ParseResult 转换为扁平 block 列表
    blocks = []
    for page in result.pages:
        page_idx = page.page_idx
        for block in page.blocks:
            block_type = block.type

            if block_type == "paragraph_title":
                # 标题块：提取文本和层级
                text = _extract_text_from_content(block.content)
                level = getattr(block, "level", 0)
                blocks.append({
                    "type": "title",
                    "text": text,
                    "page_idx": page_idx,
                    "level": level,
                })

            elif block_type == "text":
                # 文本块：提取文本
                text = _extract_text_from_content(block.content)
                if text:
                    blocks.append({
                        "type": "text",
                        "text": text,
                        "page_idx": page_idx,
                    })

            elif block_type == "image":
                # 图片块：提取图片路径
                img_path = _extract_image_path(block)
                blocks.append({
                    "type": "image",
                    "img_path": img_path,
                    "page_idx": page_idx,
                })

            elif block_type == "table":
                # 表格块：提取表格内容（Markdown 格式）
                table_text = _extract_table_text(block)
                if table_text:
                    blocks.append({
                        "type": "table",
                        "text": table_text,
                        "page_idx": page_idx,
                    })

    print(f"MinerU 4.0 解析完成，共 {len(blocks)} 个 block")
    return blocks


# ==================== 层级构建 ====================

def _parse_heading_level(title: str, mineru_level: int = None) -> tuple:
    """
    从标题文本中解析出层级深度。

    优先从编号推断（如 "3.2.1 SM-DPf" → depth=3），
    如果没有编号则使用 MinerU 提供的 level 字段。

    返回 (depth, prefix)，depth 从 1 开始。
    """
    stripped = title.strip()
    m = re.match(r'^(\d+(?:\.\d+)*)\s+', stripped)
    if m:
        prefix = m.group(1)
        depth = len(prefix.split('.'))
        return depth, prefix

    # 无编号标题，使用 MinerU 的 level（0-based → 1-based）
    if mineru_level is not None:
        return mineru_level + 1, ""

    return 1, ""


def build_hierarchy_from_mineru(blocks: list) -> list:
    """
    将 MinerU 4.0 的 block 列表转换为层级树结构。

    block 类型:
    - {"type": "title", "text": "...", "level": 0, "page_idx": 3}
    - {"type": "text", "text": "...", "page_idx": 3}
    - {"type": "image", "img_path": "...", "page_idx": 5}
    - {"type": "table", "text": "...", "page_idx": 6}
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

    # level -> 最近该层节点 的映射，用于快速查找父级
    level_node_map: dict[int, dict] = {}
    prefix_map: dict[str, dict] = {}

    def add_context(node: dict, label: str, text: str, page: int):
        seq = len(node["contexts"]) + 1
        node["contexts"].append({
            "seq": seq,
            "label": label,
            "context": text,
            "start_index": page,
            "end_index": page,
        })

    def get_or_create_parent(prefix: str) -> tuple:
        """根据编号前缀获取或创建父节点"""
        if not prefix:
            return root_nodes, ""

        parts = prefix.split('.')
        if len(parts) == 1:
            return root_nodes, ""

        parent_prefix = '.'.join(parts[:-1])

        if parent_prefix in prefix_map:
            parent = prefix_map[parent_prefix]
            return parent["children"], parent["node_id"]

        # 递归创建父级
        get_or_create_parent(parent_prefix)
        parent_depth = len(parts) - 1
        grandparent_prefix = '.'.join(parts[:-2]) if len(parts) > 2 else ""
        parent_id = ""
        if grandparent_prefix and grandparent_prefix in prefix_map:
            parent_id = prefix_map[grandparent_prefix]["node_id"]

        parent_node = make_node(parent_prefix, parent_depth, parent_id)
        if grandparent_prefix and grandparent_prefix in prefix_map:
            prefix_map[grandparent_prefix]["children"].append(parent_node)
        else:
            root_nodes.append(parent_node)
        prefix_map[parent_prefix] = parent_node
        return parent_node["children"], parent_node["node_id"]

    current_node = None

    for block in blocks:
        block_type = block.get("type", "")
        page_idx = block.get("page_idx", 0)
        page = page_idx + 1  # 转为 1-based

        if block_type == "title":
            title_text = block.get("text", "").strip()
            if not title_text:
                continue

            mineru_level = block.get("level", 0)
            depth, prefix = _parse_heading_level(title_text, mineru_level)

            # 获取父级
            if prefix:
                parent_children, parent_id = get_or_create_parent(prefix)
            else:
                # 无编号标题：用 level 信息找父级
                parent_children = root_nodes
                parent_id = ""
                if depth > 1:
                    # 查找上一层的最近节点
                    for d in range(depth - 1, 0, -1):
                        if d in level_node_map:
                            parent_node = level_node_map[d]
                            parent_children = parent_node["children"]
                            parent_id = parent_node["node_id"]
                            break

            # 查找或创建节点
            node = None
            for child in parent_children:
                if child["title"] == title_text:
                    node = child
                    break

            if node is None:
                node = make_node(title_text, depth, parent_id)
                parent_children.append(node)
                if prefix:
                    prefix_map[prefix] = node

            level_node_map[depth] = node
            current_node = node
            update_page_range(node, page)

        elif block_type == "text":
            text = block.get("text", "").strip()
            if not text:
                continue
            if current_node:
                add_context(current_node, "text", text, page)
                update_page_range(current_node, page)

        elif block_type == "image":
            img_path = block.get("img_path", "")
            if current_node:
                add_context(current_node, "image", img_path, page)
                update_page_range(current_node, page)

        elif block_type == "table":
            text = block.get("text", "").strip()
            if not text:
                continue
            if current_node:
                add_context(current_node, "table", text, page)
                update_page_range(current_node, page)

    # 后处理：冒泡页码
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

    # 后处理：合并相邻同类 context
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
                    prev["context"] = prev["context"] + "\n" + ctx["context"]
                    if ctx["start_index"] is not None:
                        if prev["start_index"] is None or ctx["start_index"] < prev["start_index"]:
                            prev["start_index"] = ctx["start_index"]
                    if ctx["end_index"] is not None:
                        if prev["end_index"] is None or ctx["end_index"] > prev["end_index"]:
                            prev["end_index"] = ctx["end_index"]
                else:
                    merged.append(ctx.copy())
            for i, ctx in enumerate(merged):
                ctx["seq"] = i + 1
            node["contexts"] = merged

    merge_consecutive_contexts(root_nodes)

    return root_nodes


# ==================== 测试入口 ====================

def test_mineru_hierarchical():
    """使用 MinerU 4.0 解析 PDF 并输出层级 JSON"""

    pdf_path = "specs/03-management-provisioning/gsma/SGP.41/SGP.41-eSIM-IFPP-Architecture-and-Requirements-v1.0.pdf"
    output_json_path = "tests/output/sgp41_mineru_hierarchical_full.json"

    print("=" * 80)
    print("MinerU 4.0 PDF 层级解析测试（完整文档）")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print()

    if not Path(pdf_path).exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return

    # 解析 PDF
    print("使用 MinerU 4.0 解析 PDF...")
    blocks = parse_pdf_with_mineru(pdf_path)

    print(f"\n共提取 {len(blocks)} 个 block")

    # 打印 block 类型分布
    type_dist = {}
    for block in blocks:
        t = block.get("type", "unknown")
        type_dist[t] = type_dist.get(t, 0) + 1
    print("Block 类型分布:")
    for t, c in sorted(type_dist.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
    print()

    # 预览前 20 个 block
    print("-" * 60)
    print("Block 预览（前 20 个）:")
    print("-" * 60)
    for i, block in enumerate(blocks[:20]):
        btype = block.get("type", "?")
        page = block.get("page_idx", 0) + 1
        level = block.get("level", "")
        text = (block.get("text") or block.get("img_path") or "")[:80].replace("\n", " ")
        level_info = f" level={level}" if btype == "title" else ""
        print(f"  [{i+1:3d}] page={page} type={btype:10s}{level_info}  {text}...")
    if len(blocks) > 20:
        print(f"  ... 共 {len(blocks)} 个 block")
    print()

    # 构建层级
    print("-" * 60)
    print("构建层级结构...")
    print("-" * 60)
    hierarchy = build_hierarchy_from_mineru(blocks)

    # 打印层级预览
    def print_tree(nodes: list, indent: int = 0):
        for node in nodes:
            pfx = "  " * indent
            ctx_count = len(node.get("contexts", []))
            child_count = len(node.get("children", []))
            pages = f"p{node.get('start_index', '?')}-{node.get('end_index', '?')}"
            print(f"{pfx}[{node['node_id']}] {node['title']}  ({pages}, {ctx_count} ctx, {child_count} children)")
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
        return sum(1 + count_nodes(n.get("children", [])) for n in nodes)

    def count_contexts(nodes: list):
        return sum(len(n.get("contexts", [])) + count_contexts(n.get("children", [])) for n in nodes)

    print("=" * 80)
    print("统计:")
    print(f"  - 总节点数: {count_nodes(hierarchy)}")
    print(f"  - 总 context 数: {count_contexts(hierarchy)}")
    print(f"  - MinerU block 数: {len(blocks)}")
    print("=" * 80)


if __name__ == "__main__":
    test_mineru_hierarchical()
