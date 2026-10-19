"""用 PyPDF2 重新实现 PDF 层级解析，作为 Docling 版（tests/test_hierarchical_parse.py）的独立对照实现。

- 只用 PyPDF2 读取 PDF outline（书签）与逐页文本，不依赖 Docling/OCR。
- 输出与 Docling 版相同的层级 JSON 结构：
  {title, node_id, parent_id, start_index, end_index, contexts, summary, children}
- 输出到独立的 JSON 文件，便于与 Docling 版逐节点对比。
- PyPDF2 无法识别表格/图片，因此所有非标题内容统一标记为 text。

用法：
    ./venv/bin/pip install PyPDF2
    ./venv/bin/python tests/test_hierarchical_parse_pypdf2.py --max-pages 10
    ./venv/bin/python tests/test_hierarchical_parse_pypdf2.py --max-pages 0   # 全文
"""

import argparse
import json
import re
import sys
from pathlib import Path

from PyPDF2 import PdfReader

DEFAULT_PDF = (
    "specs/03-management-provisioning/gsma/SGP.41/"
    "SGP.41-eSIM-IFPP-Architecture-and-Requirements-v1.0.pdf"
)
DEFAULT_OUT = "tests/output/sgp41_hierarchical_pypdf2.json"

# "3 Architecture" / "3.2.1 SM-DPf"
HEADING_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(\S.*)$")
MAX_HEADING_LEN = 140
# "A.1 Consumer Devices Use Case"
LETTER_HEADING_RE = re.compile(r"^([A-Z]\.\d+(?:\.\d+)*)\s+(\S.*)$")
ANNEX_RE = re.compile(r"^Annex\s+[A-Z]\b")
# 目录行：标题 + 尾部页码，如 "1 Introduction  4"
TOC_LINE_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*|[A-Z]\.\d+(?:\.\d+)*|Annex\s+[A-Z])\s+.+?\s+\d{1,3}$"
)
# 页眉："SGP. 41 V1.0  Page 4 of 26 "
PAGE_HEADER_RE = re.compile(r"SGP\.\s*41\s+V[\d.]+\s+Page\s+\d+\s+of\s+\d+\s*")
DATE_RE = re.compile(
    r"^\d{1,2}\s+"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{4}$",
    re.IGNORECASE,
)
FRONT_MATTER_PREFIXES = (
    "Security Classification",
    "Copyright Notice",
    "Disclaimer",
    "Compliance Notice",
    "Table of Contents",
)


def _normalize_title(title: str) -> str:
    """折叠多余空白，并去掉括号/标点前的空格（如 'ES2f )'、' ,'）。"""
    text = re.sub(r"\s+", " ", title).strip()
    return re.sub(r"\s+([),.;:])", r"\1", text)


def _strip_page_header(text: str) -> str:
    """去掉每页页眉；页眉常与首个标题粘在同一行。"""
    return PAGE_HEADER_RE.sub("", text, count=1)


def _is_toc_page(lines: list) -> bool:
    """目录页：含 'Table of Contents'，或有 3 行以上「标题 + 页码」形式。"""
    if any("Table of Contents" in line for line in lines):
        return True
    return sum(1 for line in lines if TOC_LINE_RE.match(line)) >= 3


def _front_matter_heading(line: str) -> str | None:
    """GSMA 规范封面/目录里的无编号标题。"""
    title = _normalize_title(line)
    for prefix in FRONT_MATTER_PREFIXES:
        if title == prefix or title.startswith(prefix + ":"):
            return title
    return None


def _parse_heading_level(title: str) -> tuple:
    """解析标题层级与编号：
    '3.2.1 Foo' -> (3, '3.2.1')；'Annex A Foo' -> (1, 'A')；'A.1 Foo' -> (2, 'A.1')；
    无编号 -> (1, '')。
    """
    stripped = title.strip()
    m = re.match(r"^Annex\s+([A-Z])\b", stripped)
    if m:
        return 1, m.group(1)
    m = LETTER_HEADING_RE.match(stripped)
    if m:
        prefix = m.group(1)
        return 1 + prefix.count("."), prefix
    m = re.match(r"^(\d+(?:\.\d+)*)\s+", stripped)
    if m:
        prefix = m.group(1)
        return len(prefix.split(".")), prefix
    return 1, ""


def _flatten_outline(items, reader: PdfReader, depth: int = 1, out=None):
    """把 PyPDF2 的嵌套 outline 展平成 [(title, page, depth)]，page 为 1-based。"""
    if out is None:
        out = []
    for item in items or []:
        if isinstance(item, list):
            _flatten_outline(item, reader, depth + 1, out)
            continue
        title = (getattr(item, "title", "") or "").strip()
        if not title:
            continue
        try:
            page = reader.get_destination_page_number(item) + 1
        except Exception:
            continue
        out.append((title, max(1, page), depth))
    return out


def _numbered_heading(line: str) -> str | None:
    """判断一行是否为编号/Annex 标题，返回规范化标题；正文行返回 None。"""
    stripped = _normalize_title(line)
    if not stripped or len(stripped) > MAX_HEADING_LEN:
        return None
    if DATE_RE.match(stripped):
        return None
    # 目录行（标题 + 尾部页码）不当作正文标题
    if TOC_LINE_RE.match(stripped):
        return None
    if ANNEX_RE.match(stripped):
        return stripped
    if LETTER_HEADING_RE.match(stripped):
        return stripped
    m = HEADING_RE.match(stripped)
    if not m:
        return None
    prefix, rest = m.group(1), m.group(2).strip()
    # 四位及以上且不带点的数字更像年份（如 "2025 GSM Association"）
    if "." not in prefix and len(prefix) >= 4:
        return None
    # 标题通常不以句号结尾，且标题正文应以字母开头
    if rest.endswith(".") or not rest[:1].isalpha():
        return None
    return stripped


def _current_path(stack: dict) -> list:
    return [stack[d] for d in sorted(stack)]


def _push_heading(stack: dict, title: str, depth: int) -> list:
    """把标题压入栈（丢弃更深的层级），返回该标题的 heading_path。"""
    for key in [k for k in stack if k >= depth]:
        del stack[key]
    stack[depth] = title
    return _current_path(stack)


def extract_flat_items(pdf_path: str, max_pages: int | None = None):
    """用 PyPDF2 抽取扁平 item 列表，字段与 DoclingPDFProcessor 的输出保持一致。

    处理策略：
    - 去掉每页页眉（页眉常与首个标题粘连）；
    - 目录页只产出一个 "Table of Contents" 节点，目录行不当作标题；
    - 正文按编号标题（1 / 1.2 / 3.2.1 / Annex A / A.1）切分，遇到新标题就把
      之前累积的正文作为一个 text item 归到当前 heading_path 下。
    """
    reader = PdfReader(pdf_path)
    page_count = len(reader.pages)
    limit = page_count if not max_pages or max_pages <= 0 else min(page_count, max_pages)

    outline_by_page: dict[int, list[tuple[str, int]]] = {}
    for title, page, depth in _flatten_outline(reader.outline, reader):
        outline_by_page.setdefault(page, []).append((title, depth))

    items: list[dict] = []
    seen_headings: set[tuple[int, str]] = set()
    stack: dict[int, str] = {}
    body_lines: list[str] = []
    body_page: int | None = None
    toc_page_seen = False

    def flush_body(page: int):
        nonlocal body_page
        if not body_lines:
            return
        items.append(
            {
                "type": "text",
                "text": "\n".join(body_lines),
                "heading_path": _current_path(stack),
                "page": body_page if body_page is not None else page,
                "caption": None,
                "bbox": None,
            }
        )
        body_lines.clear()
        body_page = None

    def emit_heading(title: str, page: int, depth: int):
        title = _normalize_title(title)
        flush_body(page)
        key = (page, title)
        if key in seen_headings:
            return
        seen_headings.add(key)
        items.append(
            {
                "type": "section_header",
                "text": title,
                "heading_path": _push_heading(stack, title, depth),
                "page": page,
                "caption": None,
                "bbox": None,
            }
        )

    for page_index in range(limit):
        page_no = page_index + 1
        text = _strip_page_header(reader.pages[page_index].extract_text() or "")
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # 目录页：只建一个 "Table of Contents" 节点，整页文本作为它的 context
        if _is_toc_page(lines):
            if not toc_page_seen:
                emit_heading("Table of Contents", page_no, 1)
                toc_page_seen = True
            toc_text = "\n".join(
                line for line in lines if line != "Table of Contents"
            )
            if toc_text:
                items.append(
                    {
                        "type": "text",
                        "text": toc_text,
                        "heading_path": _current_path(stack),
                        "page": page_no,
                        "caption": None,
                        "bbox": None,
                    }
                )
            continue

        # 书签标题（这份 PDF 没有 outline，保留兼容分支）
        for title, depth in outline_by_page.get(page_no, []):
            _, prefix = _parse_heading_level(title)
            emit_heading(
                title, page_no, depth if not prefix else len(prefix.split("."))
            )

        for line in lines:
            front_matter = _front_matter_heading(line)
            if front_matter:
                emit_heading(front_matter, page_no, 1)
                continue
            heading = _numbered_heading(line)
            if heading:
                depth, _ = _parse_heading_level(heading)
                emit_heading(heading, page_no, depth)
                continue
            if body_page is None:
                body_page = page_no
            body_lines.append(line)

        flush_body(page_no)

    return items, limit, page_count


def build_hierarchy(flat_items: list) -> list:
    """把扁平 item 列表转换为层级树（与 Docling 版测试保持同一算法/契约）。"""
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

    prefix_map: dict[str, dict] = {}
    untitled_node = None

    def add_context(node: dict, item: dict):
        label = item.get("type", "text")
        if label == "picture":
            label = "image"
        seq = len(node["contexts"]) + 1
        node["contexts"].append(
            {
                "seq": seq,
                "label": label,
                "context": item.get("text", ""),
                "start_index": item.get("page"),
                "end_index": item.get("page"),
            }
        )

    def get_or_create_parent(prefix: str) -> tuple:
        if not prefix:
            return root_nodes, ""

        parts = prefix.split(".")
        if len(parts) == 1:
            return root_nodes, ""

        parent_prefix = ".".join(parts[:-1])
        if parent_prefix in prefix_map:
            parent = prefix_map[parent_prefix]
            return parent["children"], parent["node_id"]

        get_or_create_parent(parent_prefix)
        grandparent_prefix = ".".join(parts[:-2]) if len(parts) > 2 else ""
        parent_node = make_node(
            parent_prefix,
            len(parts) - 1,
            prefix_map[grandparent_prefix]["node_id"]
            if grandparent_prefix in prefix_map
            else "",
        )
        if grandparent_prefix and grandparent_prefix in prefix_map:
            prefix_map[grandparent_prefix]["children"].append(parent_node)
        else:
            root_nodes.append(parent_node)
        prefix_map[parent_prefix] = parent_node
        return parent_node["children"], parent_node["node_id"]

    for item in flat_items:
        heading_path = item.get("heading_path", [])
        page = item.get("page")

        if not heading_path:
            if untitled_node is None:
                untitled_node = make_node("(Untitled Section)", 0, "")
                root_nodes.append(untitled_node)
            add_context(untitled_node, item)
            update_page_range(untitled_node, page)
            continue

        heading_title = heading_path[-1]
        depth, prefix = _parse_heading_level(heading_title)

        parent_children, parent_id = get_or_create_parent(prefix)

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

        if item.get("type") not in ("section_header",):
            add_context(node, item)

        update_page_range(node, page)

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
                        if (
                            prev["start_index"] is None
                            or ctx["start_index"] < prev["start_index"]
                        ):
                            prev["start_index"] = ctx["start_index"]
                    if ctx["end_index"] is not None:
                        if (
                            prev["end_index"] is None
                            or ctx["end_index"] > prev["end_index"]
                        ):
                            prev["end_index"] = ctx["end_index"]
                else:
                    merged.append(ctx.copy())
            for i, ctx in enumerate(merged):
                ctx["seq"] = i + 1
            node["contexts"] = merged

    merge_consecutive_contexts(root_nodes)

    return root_nodes


def _print_tree(nodes: list, indent: int = 0):
    for node in nodes:
        prefix = "  " * indent
        pages = f"p{node.get('start_index', '?')}-{node.get('end_index', '?')}"
        print(
            f"{prefix}[{node['node_id']}] {node['title']}  "
            f"({pages}, {len(node.get('contexts', []))} ctx, "
            f"{len(node.get('children', []))} children)"
        )
        if node.get("children"):
            _print_tree(node["children"], indent + 1)


def _count_nodes(nodes: list) -> int:
    return sum(1 + _count_nodes(n.get("children", [])) for n in nodes)


def _count_contexts(nodes: list) -> int:
    return sum(
        len(n.get("contexts", [])) + _count_contexts(n.get("children", []))
        for n in nodes
    )


def test_hierarchical_parse_pypdf2(
    pdf_path: str = DEFAULT_PDF,
    out_path: str = DEFAULT_OUT,
    max_pages: int = 10,
):
    """PyPDF2 版层级解析测试：抽取 -> 建树 -> 输出独立 JSON。"""
    print("=" * 80)
    print("PDF 层级解析测试（PyPDF2 版）")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print(f"页面范围: {'全部' if max_pages <= 0 else f'前 {max_pages} 页'}")
    print()

    if not Path(pdf_path).exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return None

    flat_items, used_pages, total_pages = extract_flat_items(pdf_path, max_pages)
    print(f"PDF 总页数: {total_pages}，本次解析: {used_pages} 页")
    print(f"提取 item 数: {len(flat_items)}")
    print()

    print("-" * 60)
    print("扁平 item 预览（前 20 个）:")
    print("-" * 60)
    for i, item in enumerate(flat_items[:20]):
        text_preview = (item.get("text") or "")[:80].replace("\n", " ")
        heading = " > ".join(item.get("heading_path", []))
        print(
            f"  [{i + 1:3d}] page={item.get('page')} "
            f"type={item.get('type', ''):14s} heading=[{heading}]"
        )
        print(f"        text: {text_preview}...")
    if len(flat_items) > 20:
        print(f"  ... 共 {len(flat_items)} 个 item")
    print()

    print("-" * 60)
    print("构建层级结构...")
    print("-" * 60)
    hierarchy = build_hierarchy(flat_items)
    _print_tree(hierarchy)
    print()

    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(hierarchy, f, ensure_ascii=False, indent=2)

    print(f"✅ 层级 JSON 已保存到: {output}")
    print()
    print("=" * 80)
    print("统计:")
    print(f"  - 总节点数: {_count_nodes(hierarchy)}")
    print(f"  - 总 context 数: {_count_contexts(hierarchy)}")
    print(f"  - 扁平 item 数: {len(flat_items)}")
    print("=" * 80)
    return hierarchy


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="用 PyPDF2 重新实现 PDF 层级解析（Docling 版的独立对照实现）"
    )
    parser.add_argument("--pdf", default=DEFAULT_PDF, help="PDF 文件路径")
    parser.add_argument("--out", default=DEFAULT_OUT, help="输出 JSON 路径")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="最多解析前 N 页；0 表示全文（默认 10）",
    )
    args = parser.parse_args(argv)
    test_hierarchical_parse_pypdf2(args.pdf, args.out, args.max_pages)


if __name__ == "__main__":
    sys.exit(main())
