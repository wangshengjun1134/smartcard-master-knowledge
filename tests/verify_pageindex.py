"""
PageIndex 输出校验脚本 — 对比原文档与 PageIndex 输出

用法：
    cd /home/buff/workspaces/smartcard/smartcard-master-knowledge
    source venv/bin/activate
    python tests/verify_pageindex.py --pdf specs/07-test/SGP.33-1-IoT-eUICC-v1.2-index-IoT-eSIM-Test.pdf --doc-id <文档ID>
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import fitz  # PyMuPDF


def analyze_pdf(pdf_path: str):
    """用 PyMuPDF 分析原文档，生成基准数据"""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)

    # 每页统计
    page_stats = []
    total_images = 0
    total_tables = 0
    total_links = 0
    total_drawings = 0

    for i in range(total_pages):
        page = doc[i]
        imgs = page.get_images(full=True)
        try:
            tabs = page.find_tables()
            tab_count = len(tabs) if tabs else 0
        except Exception:
            tab_count = 0
        links = page.get_links()
        try:
            drawings = page.get_drawings()
            draw_count = len(drawings) if drawings else 0
        except Exception:
            draw_count = 0

        page_stats.append({
            "page": i + 1,
            "images": len(imgs),
            "tables": tab_count,
            "links": len(links),
            "drawings": draw_count,
        })
        total_images += len(imgs)
        total_tables += tab_count
        total_links += len(links)
        total_drawings += draw_count

    doc.close()

    return {
        "total_pages": total_pages,
        "total_images": total_images,
        "total_tables": total_tables,
        "total_links": total_links,
        "total_drawings": total_drawings,
        "page_stats": page_stats,
    }


def analyze_skeleton(skeleton_path: str):
    """分析 skeleton.json 输出"""
    with open(skeleton_path, "r", encoding="utf-8") as f:
        skeleton = json.load(f)

    # 统计节点
    def count_nodes(nodes, depth=1):
        result = []
        for node in nodes:
            entry = {
                "number": node.get("number", ""),
                "title": node.get("title", ""),
                "level": node.get("level", depth),
                "page": node.get("page", 0),
                "contexts_count": len(node.get("contexts", [])),
                "children_count": len(node.get("children", [])),
            }
            # 统计 contexts 按类型
            ctx_types = defaultdict(int)
            for ctx in node.get("contexts", []):
                ctx_types[ctx.get("label", "unknown")] += 1
            entry["context_types"] = dict(ctx_types)
            result.append(entry)
            result.extend(count_nodes(node.get("children", []), depth + 1))
        return result

    all_nodes = count_nodes(skeleton)

    # 统计 contexts 总数按类型
    total_ctx_by_type = defaultdict(int)
    def count_all_ctx(nodes):
        for node in nodes:
            for ctx in node.get("contexts", []):
                total_ctx_by_type[ctx.get("label", "unknown")] += 1
            count_all_ctx(node.get("children", []))
    count_all_ctx(skeleton)

    return {
        "total_nodes": len(all_nodes),
        "nodes": all_nodes,
        "total_contexts_by_type": dict(total_ctx_by_type),
    }


def verify(pdf_path: str, doc_id: str):
    """主校验逻辑"""
    print("=" * 70)
    print("PageIndex 输出校验报告")
    print("=" * 70)
    print(f"PDF: {pdf_path}")
    print(f"Document ID: {doc_id}")
    print()

    # 1. 分析原文档
    print("【1】原文档基准分析")
    print("-" * 40)
    pdf_analysis = analyze_pdf(pdf_path)
    print(f"  总页数: {pdf_analysis['total_pages']}")
    print(f"  图片总数: {pdf_analysis['total_images']}")
    print(f"  表格总数: {pdf_analysis['total_tables']}")
    print(f"  链接总数: {pdf_analysis['total_links']}")
    print(f"  矢量图总数: {pdf_analysis['total_drawings']}")
    print()

    # 2. 分析 skeleton 输出
    skeleton_path = Path("output") / "toc" / doc_id / "skeleton.json"
    if not skeleton_path.exists():
        print(f"❌ skeleton.json 不存在: {skeleton_path}")
        print("   请先执行 PageIndex")
        return

    print("【2】Skeleton 输出分析")
    print("-" * 40)
    sk_analysis = analyze_skeleton(str(skeleton_path))
    print(f"  骨架节点总数: {sk_analysis['total_nodes']}")
    print(f"  Contexts 按类型统计:")
    for ctx_type, count in sorted(sk_analysis["total_contexts_by_type"].items()):
        print(f"    {ctx_type}: {count}")
    print()

    # 3. 校验对比
    print("【3】校验对比")
    print("-" * 40)

    # 3a. 图片数量校验
    skeleton_pictures = sk_analysis["total_contexts_by_type"].get("picture", 0)
    pdf_images = pdf_analysis["total_images"]
    match_img = "✅" if skeleton_pictures == pdf_images else "⚠️"
    print(f"  {match_img} 图片: PDF={pdf_images}, Skeleton={skeleton_pictures}")
    if skeleton_pictures != pdf_images:
        print(f"     差异: {pdf_images - skeleton_pictures} 张图片未在 skeleton 中")

    # 3b. 表格数量校验
    skeleton_tables = sk_analysis["total_contexts_by_type"].get("table", 0)
    pdf_tables = pdf_analysis["total_tables"]
    match_tab = "✅" if skeleton_tables == pdf_tables else "⚠️"
    print(f"  {match_tab} 表格: PDF={pdf_tables}, Skeleton={skeleton_tables}")
    if skeleton_tables != pdf_tables:
        print(f"     差异: {pdf_tables - skeleton_tables} 个表格未在 skeleton 中")

    # 3c. 链接数量校验
    skeleton_links = sk_analysis["total_contexts_by_type"].get("link", 0)
    pdf_links = pdf_analysis["total_links"]
    match_link = "✅" if skeleton_links == pdf_links else "⚠️"
    print(f"  {match_link} 链接: PDF={pdf_links}, Skeleton={skeleton_links}")
    if skeleton_links != pdf_links:
        print(f"     差异: {pdf_links - skeleton_links} 个链接未在 skeleton 中")

    # 3d. 矢量图数量校验
    skeleton_drawings = sk_analysis["total_contexts_by_type"].get("drawing", 0)
    pdf_drawings = pdf_analysis["total_drawings"]
    match_draw = "✅" if skeleton_drawings == pdf_drawings else "⚠️"
    print(f"  {match_draw} 矢量图: PDF={pdf_drawings}, Skeleton={skeleton_drawings}")
    if skeleton_drawings != pdf_drawings:
        print(f"     差异: {pdf_drawings - skeleton_drawings} 个矢量图未在 skeleton 中")

    print()

    # 4. 逐页对比
    print("【4】逐页对比")
    print("-" * 40)
    # 统计 skeleton 中每页的 contexts 分布
    page_ctx = defaultdict(lambda: defaultdict(int))
    skeleton_raw = skeleton_analysis_get(skeleton_path)
    def count_page_ctx(nodes):
        for node in nodes:
            for ctx in node.get("contexts", []):
                page = ctx.get("start_index")
                if page:
                    page_ctx[page][ctx.get("label", "unknown")] += 1
            count_page_ctx(node.get("children", []))
    count_page_ctx(skeleton_raw)

    print(f"  {'Page':>5} | {'Text':>5} | {'Pic':>4} | {'Tab':>4} | {'Drw':>4} | {'Lnk':>4} | {'Total':>5}")
    print(f"  {'-'*5}-+-{'-'*5}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*5}")
    for ps in pdf_analysis["page_stats"]:
        p = ps["page"]
        pc = page_ctx.get(p, {})
        total = sum(pc.values())
        if total > 0 or ps["images"] > 0 or ps["tables"] > 0:
            print(f"  {p:>5} | {pc.get('text',0)+pc.get('paragraph_title',0):>5} | {pc.get('picture',0):>4} | {pc.get('table',0):>4} | {pc.get('drawing',0):>4} | {pc.get('link',0):>4} | {total:>5}")

    print()

    # 5. 节点详情（前 20 个）
    print("【5】骨架节点详情（前 20 个）")
    print("-" * 40)
    for node in sk_analysis["nodes"][:20]:
        indent = "  " * (node["level"] - 1)
        ctx_types = ", ".join(f"{k}:{v}" for k, v in node["context_types"].items()) if node["context_types"] else "无"
        print(f"  {indent}{node['number']} {node['title']} (p.{node['page']}) — {node['contexts_count']} contexts [{ctx_types}]")

    if sk_analysis["total_nodes"] > 20:
        print(f"  ... 共 {sk_analysis['total_nodes']} 个节点")

    print()
    print("=" * 70)
    print("校验完成")
    print("=" * 70)


def skeleton_analysis_get(skeleton_path):
    """读取 skeleton.json 返回原始数据"""
    with open(skeleton_path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PageIndex 输出校验")
    parser.add_argument("--pdf", required=True, help="PDF 文件路径")
    parser.add_argument("--doc-id", required=True, help="文档 ID")
    args = parser.parse_args()

    if not Path(args.pdf).exists():
        print(f"❌ PDF 文件不存在: {args.pdf}")
        sys.exit(1)

    verify(args.pdf, args.doc_id)
