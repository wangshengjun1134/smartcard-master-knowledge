"""
PageIndex 统一序列处理 — 独立验证脚本

绕过 HTTP API，直接调用核心逻辑验证：
1. 读取已有 toc.json（跳过 LLM 调用）
2. 用 PyMuPDF 提取所有 blocks（text + picture + table + drawing + link）
3. 按 (page_idx, y) 排序
4. 标题检测 + assign_blocks_to_skeleton()
5. 对比 PDF 原始统计 vs skeleton contexts 统计

用法：
    cd /home/buff/workspaces/smartcard/smartcard-master-knowledge
    source venv/bin/activate
    python tests/verify_unified_sequence.py \
        --pdf specs/07-test/SGP.33-1-IoT-eUICC-v1.2-index-IoT-eSIM-Test.pdf \
        --doc-id 5bae91b3-69e8-4132-9d6a-c4bde37360e3
"""

import argparse
import json
import sys
import time
from pathlib import Path
from collections import defaultdict, Counter

import fitz  # PyMuPDF

# 确保 src 在 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "tests"))

from toc_skeleton import build_skeleton_tree, assign_blocks_to_skeleton, detect_page_offset


def extract_all_blocks(pdf_path: str):
    """用 PyMuPDF 提取所有类型的 blocks，按 (page_idx, y) 排序"""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    all_blocks = []
    img_counter = 0

    for page_idx in range(total_pages):
        page = doc[page_idx]

        # 文本 blocks
        for tb in page.get_text("blocks"):
            text = tb[4].strip() if len(tb) > 4 else ""
            if text:
                all_blocks.append({
                    "type": "text",
                    "text": text,
                    "page_idx": page_idx,
                    "y": tb[1],
                })

        # 图片 blocks（用 get_image_info 获取 bbox）
        for ii in page.get_image_info():
            img_counter += 1
            bbox = ii.get("bbox", (0, 0, 0, 0))
            all_blocks.append({
                "type": "picture",
                "page_idx": page_idx,
                "y": bbox[1],
                "metadata": {"image_path": f"picture_{img_counter:04d}.png"},
            })

        # 表格 blocks
        try:
            for tab in page.find_tables():
                table_data = tab.extract()
                if table_data:
                    all_blocks.append({
                        "type": "table",
                        "page_idx": page_idx,
                        "y": tab.bbox[1],
                        "metadata": {"rows": len(table_data), "cols": len(table_data[0]) if table_data else 0},
                    })
        except Exception:
            pass

        # 矢量图 blocks
        try:
            for dr in page.get_drawings():
                rect = dr.get("rect")
                all_blocks.append({
                    "type": "drawing",
                    "page_idx": page_idx,
                    "y": rect[1] if rect else 0,
                    "metadata": {"items_count": len(dr.get("items", []))},
                })
        except Exception:
            pass

        # 链接 blocks
        try:
            for lnk in page.get_links():
                from_rect = lnk.get("from")
                all_blocks.append({
                    "type": "link",
                    "page_idx": page_idx,
                    "y": from_rect[1] if from_rect else 0,
                    "metadata": {"uri": lnk.get("uri", ""), "kind": lnk.get("kind")},
                })
        except Exception:
            pass

    doc.close()

    # 按 (page_idx, y) 排序
    all_blocks.sort(key=lambda b: (b["page_idx"], b.get("y", 0)))
    return all_blocks


def detect_titles(blocks: list, skeleton: list):
    """检测标题 blocks"""
    import re

    def flatten_titles(nodes, titles=None):
        if titles is None:
            titles = set()
        for node in nodes:
            t = node.get("title", "").strip().lower()
            if t:
                t = re.sub(r'[\u2013\u2014\u2012\u2015\ufe58\ufe63\uff0d]', '-', t)
                t = re.sub(r'\s+', ' ', t)
                titles.add(t)
            flatten_titles(node.get("children", []), titles)
        return titles

    skeleton_titles = flatten_titles(skeleton)
    title_count = 0
    for block in blocks:
        if block.get("type") != "text":
            continue
        text = block.get("text", "").strip().lower()
        if not text:
            continue
        text_norm = re.sub(r'[\u2013\u2014\u2012\u2015\ufe58\ufe63\uff0d]', '-', text)
        text_norm = re.sub(r'\s+', ' ', text_norm)
        if text_norm in skeleton_titles:
            block["type"] = "paragraph_title"
            title_count += 1
    return title_count


def count_contexts_by_type(nodes):
    """递归统计 contexts 按类型"""
    counts = Counter()
    for node in nodes:
        for ctx in node.get("contexts", []):
            counts[ctx.get("label", "unknown")] += 1
        counts += count_contexts_by_type(node.get("children", []))
    return counts


def count_nodes(nodes):
    """递归统计节点数"""
    c = len(nodes)
    for node in nodes:
        c += count_nodes(node.get("children", []))
    return c


def main():
    parser = argparse.ArgumentParser(description="PageIndex 统一序列处理验证")
    parser.add_argument("--pdf", required=True, help="PDF 文件路径")
    parser.add_argument("--doc-id", required=True, help="文档 ID（用于读取 toc.json）")
    args = parser.parse_args()

    pdf_path = args.pdf
    doc_id = args.doc_id

    print("=" * 70)
    print("PageIndex 统一序列处理验证")
    print("=" * 70)
    print(f"PDF: {pdf_path}")
    print(f"Document ID: {doc_id}")
    print()

    # 1. 读取已有 toc.json
    toc_path = Path("output") / "toc" / doc_id / "toc.json"
    if not toc_path.exists():
        print(f"❌ toc.json 不存在: {toc_path}")
        print("   请先通过 API 执行 TOC 提取")
        sys.exit(1)

    with open(toc_path, "r", encoding="utf-8") as f:
        toc = json.load(f)
    print(f"【1】读取 toc.json: {len(toc)} 个 TOC 条目")

    # 2. 构建骨架
    skeleton = build_skeleton_tree(toc)
    print(f"【2】构建骨架: {count_nodes(skeleton)} 个节点")
    print()

    # 3. 提取所有 blocks
    print("【3】提取所有 blocks（PyMuPDF）...")
    t0 = time.time()
    all_blocks = extract_all_blocks(pdf_path)
    elapsed = time.time() - t0

    # 统计各类型
    type_counts = Counter(b["type"] for b in all_blocks)
    print(f"  提取完成: {len(all_blocks)} blocks in {elapsed:.1f}s")
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")
    print()

    # 4. 标题检测
    print("【4】标题检测...")
    title_count = detect_titles(all_blocks, skeleton)
    print(f"  检测到 {title_count} 个标题 blocks")
    print()

    # 5. 页码偏移检测 + 分配
    print("【5】分配 blocks 到骨架节点...")
    t0 = time.time()
    page_offset = detect_page_offset(toc, all_blocks)
    print(f"  页码偏移: {page_offset}")
    skeleton = assign_blocks_to_skeleton(skeleton, all_blocks, page_offset)
    elapsed = time.time() - t0
    print(f"  分配完成 in {elapsed:.1f}s")
    print()

    # 6. 统计结果
    print("【6】Skeleton contexts 统计")
    print("-" * 40)
    ctx_counts = count_contexts_by_type(skeleton)
    total_ctx = sum(ctx_counts.values())
    print(f"  总 contexts: {total_ctx}")
    for label, count in sorted(ctx_counts.items()):
        print(f"    {label}: {count}")
    print()

    # 7. 校验对比
    print("【7】校验对比：PDF 原始统计 vs Skeleton contexts")
    print("-" * 40)
    checks = [
        ("picture", type_counts.get("picture", 0), ctx_counts.get("picture", 0)),
        ("table", type_counts.get("table", 0), ctx_counts.get("table", 0)),
        ("drawing", type_counts.get("drawing", 0), ctx_counts.get("drawing", 0)),
        ("link", type_counts.get("link", 0), ctx_counts.get("link", 0)),
    ]
    all_pass = True
    for label, pdf_count, sk_count in checks:
        status = "✅" if pdf_count == sk_count else "❌"
        if pdf_count != sk_count:
            all_pass = False
        print(f"  {status} {label}: PDF={pdf_count}, Skeleton={sk_count}" +
              (f" (差异: {pdf_count - sk_count})" if pdf_count != sk_count else ""))

    # text 比较（text blocks 可能被标题检测消耗一部分）
    text_in_ctx = ctx_counts.get("text", 0) + ctx_counts.get("paragraph_title", 0)
    print(f"  ℹ️  text: PDF={type_counts.get('text', 0)}, Skeleton contexts={text_in_ctx} (含 {title_count} 个标题)")
    print()

    # 8. 逐页分布（前 20 页）
    print("【8】逐页 contexts 分布（前 20 页）")
    print("-" * 40)
    page_ctx = defaultdict(lambda: Counter())
    def collect_page_ctx(nodes):
        for node in nodes:
            for ctx in node.get("contexts", []):
                p = ctx.get("start_index")
                if p:
                    page_ctx[p][ctx.get("label", "?")] += 1
            collect_page_ctx(node.get("children", []))
    collect_page_ctx(skeleton)

    print(f"  {'Page':>5} | {'Text':>5} | {'Pic':>4} | {'Tab':>4} | {'Drw':>4} | {'Lnk':>4} | {'Total':>5}")
    print(f"  {'-'*5}-+-{'-'*5}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*5}")
    for p in range(1, min(21, max(page_ctx.keys()) + 1)):
        pc = page_ctx.get(p, Counter())
        total = sum(pc.values())
        if total > 0:
            print(f"  {p:>5} | {pc.get('text',0)+pc.get('paragraph_title',0):>5} | {pc.get('picture',0):>4} | {pc.get('table',0):>4} | {pc.get('drawing',0):>4} | {pc.get('link',0):>4} | {total:>5}")
    print()

    # 9. 总结
    print("=" * 70)
    if all_pass:
        print("✅ 校验通过！所有非文本 block 类型数量一致")
    else:
        print("⚠️  校验有差异，请检查上方详情")
    print("=" * 70)

    # 10. 保存验证用 skeleton
    output_path = Path("output") / "toc" / doc_id / "skeleton_verified.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(skeleton, f, ensure_ascii=False, indent=2)
    print(f"\n验证用 skeleton 已保存到: {output_path}")


if __name__ == "__main__":
    main()
