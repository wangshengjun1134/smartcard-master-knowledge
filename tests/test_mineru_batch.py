"""批量使用 MinerU 4.0 解析 PDF 目录，输出层级 JSON + 图片

支持两种模式：
1. 有 TOC 数据时：用 TOC 骨架方案（精确）
2. 无 TOC 数据时：用 prefix_map 推断（兜底）

TOC 数据可通过 LLM 从 PDF 前 N 页自动提取。
"""

import sys
import json
import io
import os
import re
import base64
import shutil
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from toc_skeleton import build_skeleton_tree, detect_page_offset, assign_blocks_to_skeleton
from toc_extractor_llm import extract_toc_from_pdf

# 批量解析的 PDF 根目录
GSMA_PDF_DIR = "specs/03-management-provisioning/gsma"
# 输出根目录
OUTPUT_ROOT = "tests/output/mineru_batch"


# ==================== MinerU 解析 ====================

def parse_pdf_with_mineru(pdf_path: str, image_output_dir: str) -> list:
    """
    使用 MinerU 4.0 解析单个 PDF，返回扁平 block 列表。
    图片保存到 image_output_dir，文件名带 PDF 文档名防止覆盖。
    """
    from mineru.parser import parse

    result = parse(
        pdf_path,
        tier="basic",
        ocr_mode="auto",
        image_analysis=False,
    )

    # 文档名（用于图片前缀）
    doc_name = Path(pdf_path).stem

    # 导出图片（base64 → 文件，跳过未知头部）
    image_count = 0
    for page in result.pages:
        page_idx = page.page_idx
        for block in page.blocks:
            if block.type == "image":
                for cb in (block.content or []):
                    if not hasattr(cb, "type") or cb.type != "image_body":
                        continue
                    saved_path = ""
                    if hasattr(cb, "image_path") and cb.image_path:
                        src = Path(cb.image_path)
                        if src.exists():
                            dst = Path(image_output_dir) / f"{doc_name}_p{page_idx+1}_img{image_count+1}{src.suffix}"
                            shutil.copy2(str(src), str(dst))
                            saved_path = str(dst)
                    elif hasattr(cb, "image_base64") and cb.image_base64:
                        img_data = base64.b64decode(cb.image_base64)
                        jpeg_off = img_data.find(b'\xff\xd8\xff')
                        png_off = img_data.find(b'\x89PNG\r\n\x1a\n')
                        if jpeg_off >= 0 and (png_off < 0 or jpeg_off <= png_off):
                            img_data = img_data[jpeg_off:]
                            ext = ".jpg"
                        elif png_off >= 0:
                            img_data = img_data[png_off:]
                            ext = ".png"
                        else:
                            ext = ".png"
                        dst = Path(image_output_dir) / f"{doc_name}_p{page_idx+1}_img{image_count+1}{ext}"
                        dst.write_bytes(img_data)
                        saved_path = str(dst)
                    if saved_path:
                        cb.image_path = saved_path
                        image_count += 1

    # 转换为扁平 block 列表
    blocks = []
    for page in result.pages:
        page_idx = page.page_idx
        for block in page.blocks:
            bt = block.type
            if bt == "paragraph_title":
                text = _extract_text(block.content)
                level = getattr(block, "level", 0)
                blocks.append({"type": "title", "text": text, "page_idx": page_idx, "level": level})
            elif bt == "text":
                text = _extract_text(block.content)
                if text:
                    blocks.append({"type": "text", "text": text, "page_idx": page_idx})
            elif bt == "image":
                img_path = ""
                for cb in (block.content or []):
                    if hasattr(cb, "image_path") and cb.image_path:
                        img_path = cb.image_path
                        break
                blocks.append({"type": "image", "img_path": img_path, "page_idx": page_idx})
            elif bt == "table":
                text = _extract_table(block)
                if text:
                    blocks.append({"type": "table", "text": text, "page_idx": page_idx})

    return blocks, image_count


def _extract_text(content_list) -> str:
    if not content_list:
        return ""
    parts = []
    for item in content_list:
        if isinstance(item, str):
            parts.append(item)
        elif hasattr(item, "content") and isinstance(item.content, str):
            parts.append(item.content)
    return "".join(parts).strip()


def _extract_table(block) -> str:
    for item in (block.content or []):
        if hasattr(item, "content") and isinstance(item.content, str) and item.content.strip():
            return item.content.strip()
    return ""


# ==================== 层级构建（prefix_map 推断） ====================

def _parse_heading_level(title: str, mineru_level: int = None) -> tuple:
    stripped = title.strip()
    m = re.match(r'^(\d+(?:\.\d+)*)\s+', stripped)
    if m:
        prefix = m.group(1)
        return len(prefix.split('.')), prefix
    if mineru_level is not None:
        return mineru_level + 1, ""
    return 1, ""


def build_hierarchy(blocks: list) -> list:
    """用 prefix_map 从扁平 blocks 构建层级树（无 TOC 时的通用方案）"""
    root_nodes = []
    level_counters = {}
    level_node_map = {}
    prefix_map = {}

    def next_id(level):
        level_counters[level] = level_counters.get(level, 0) + 1
        return f"l{level}-{level_counters[level]}"

    def make_node(title, level, parent_id):
        return {
            "title": title, "node_id": next_id(level), "parent_id": parent_id,
            "start_index": None, "end_index": None,
            "contexts": [], "summary": "", "children": [],
        }

    def update_range(node, page):
        if page is None:
            return
        if node["start_index"] is None or page < node["start_index"]:
            node["start_index"] = page
        if node["end_index"] is None or page > node["end_index"]:
            node["end_index"] = page

    def get_or_create_parent(prefix):
        if not prefix:
            return root_nodes, ""
        parts = prefix.split('.')
        if len(parts) == 1:
            return root_nodes, ""
        parent_prefix = '.'.join(parts[:-1])
        if parent_prefix in prefix_map:
            p = prefix_map[parent_prefix]
            return p["children"], p["node_id"]
        get_or_create_parent(parent_prefix)
        pdepth = len(parts) - 1
        gp = '.'.join(parts[:-2]) if len(parts) > 2 else ""
        pid = prefix_map[gp]["node_id"] if gp and gp in prefix_map else ""
        pnode = make_node(parent_prefix, pdepth, pid)
        if gp and gp in prefix_map:
            prefix_map[gp]["children"].append(pnode)
        else:
            root_nodes.append(pnode)
        prefix_map[parent_prefix] = pnode
        return pnode["children"], pnode["node_id"]

    current_node = None

    for block in blocks:
        bt = block.get("type", "")
        page = block.get("page_idx", 0) + 1

        if bt == "title":
            title = block.get("text", "").strip()
            if not title:
                continue
            depth, prefix = _parse_heading_level(title, block.get("level", 0))
            if prefix:
                pc, pid = get_or_create_parent(prefix)
            else:
                pc, pid = root_nodes, ""
                if depth > 1:
                    for d in range(depth - 1, 0, -1):
                        if d in level_node_map:
                            pc = level_node_map[d]["children"]
                            pid = level_node_map[d]["node_id"]
                            break
            node = None
            for c in pc:
                if c["title"] == title:
                    node = c
                    break
            if node is None:
                node = make_node(title, depth, pid)
                pc.append(node)
                if prefix:
                    prefix_map[prefix] = node
            level_node_map[depth] = node
            current_node = node
            update_range(node, page)
        elif bt in ("text", "table"):
            text = block.get("text", "")
            if text and current_node:
                seq = len(current_node["contexts"]) + 1
                current_node["contexts"].append({
                    "seq": seq, "label": bt, "context": text,
                    "start_index": page, "end_index": page,
                })
                update_range(current_node, page)
        elif bt == "image":
            img = block.get("img_path", "")
            if current_node:
                seq = len(current_node["contexts"]) + 1
                current_node["contexts"].append({
                    "seq": seq, "label": "image", "context": img,
                    "start_index": page, "end_index": page,
                })
                update_range(current_node, page)

    # 冒泡页码
    def bubble(nodes):
        for n in nodes:
            if n["children"]:
                bubble(n["children"])
                for c in n["children"]:
                    if c["start_index"] is not None:
                        update_range(n, c["start_index"])
                    if c["end_index"] is not None:
                        update_range(n, c["end_index"])
            for ctx in n["contexts"]:
                if ctx["start_index"] is not None:
                    update_range(n, ctx["start_index"])
                if ctx["end_index"] is not None:
                    update_range(n, ctx["end_index"])
    bubble(root_nodes)

    # 合并相邻同类 context
    def merge(nodes):
        for n in nodes:
            merge(n.get("children", []))
            ctxs = n.get("contexts", [])
            if len(ctxs) <= 1:
                continue
            merged = [ctxs[0].copy()]
            for ctx in ctxs[1:]:
                prev = merged[-1]
                if ctx["label"] == prev["label"]:
                    prev["context"] += "\n" + ctx["context"]
                    if ctx["start_index"] is not None and (prev["start_index"] is None or ctx["start_index"] < prev["start_index"]):
                        prev["start_index"] = ctx["start_index"]
                    if ctx["end_index"] is not None and (prev["end_index"] is None or ctx["end_index"] > prev["end_index"]):
                        prev["end_index"] = ctx["end_index"]
                else:
                    merged.append(ctx.copy())
            for i, ctx in enumerate(merged):
                ctx["seq"] = i + 1
            n["contexts"] = merged
    merge(root_nodes)

    return root_nodes


# ==================== 批量入口 ====================

def batch_parse(
    pdf_dir: str = None,
    output_root: str = None,
    limit: int = None,
    llm_api_url: str = None,
    llm_api_key: str = None,
    llm_model: str = None,
):
    """
    批量解析目录下所有 PDF。

    流程：MinerU 解析 → LLM 提取 TOC → TOC 骨架构建层级

    Args:
        pdf_dir: PDF 目录路径（默认 GSMA_PDF_DIR）
        output_root: 输出根目录（默认 OUTPUT_ROOT）
        limit: 限制处理文件数（None=全部，用于简单测试）
        llm_api_url: LLM API URL（用于提取 TOC，不传则从环境变量读取）
        llm_api_key: LLM API Key（用于提取 TOC，不传则从环境变量读取）
        llm_model: LLM 模型名（用于提取 TOC）
    """
    pdf_dir = Path(pdf_dir or GSMA_PDF_DIR)
    output_root = Path(output_root or OUTPUT_ROOT)
    output_root.mkdir(parents=True, exist_ok=True)

    # LLM 参数（从参数或环境变量获取）
    api_url = llm_api_url or os.getenv("OPENAI_BASE_URL", "")
    api_key = llm_api_key or os.getenv("OPENAI_API_KEY", "")
    model = llm_model or os.getenv("OPENAI_MODEL", "qwen-plus")
    use_llm = bool(api_url and api_key)

    # 扫描所有 PDF
    pdf_files = sorted(pdf_dir.rglob("*.pdf"))
    if limit:
        pdf_files = pdf_files[:limit]

    print("=" * 80)
    print(f"MinerU 4.0 批量解析（TOC 骨架方案）")
    print("=" * 80)
    print(f"PDF 目录: {pdf_dir}")
    print(f"输出目录: {output_root}")
    print(f"PDF 总数: {len(pdf_files)}" + (f"（限制前 {limit} 个）" if limit else ""))
    print(f"LLM TOC 提取: {'✅ ' + model if use_llm else '❌ 未配置（使用 prefix_map 兜底）'}")
    print()

    summary = []
    total_start = time.time()

    for i, pdf_path in enumerate(pdf_files):
        # 文档标识：用相对路径（去掉前缀和 .pdf 后缀）
        rel = pdf_path.relative_to(pdf_dir)
        doc_id = str(rel.with_suffix("")).replace("/", "_")
        doc_name = pdf_path.stem

        print(f"[{i+1}/{len(pdf_files)}] {doc_id} ({pdf_path.name})")

        # 每个文档的输出目录
        doc_output_dir = output_root / doc_id
        doc_output_dir.mkdir(parents=True, exist_ok=True)
        img_dir = doc_output_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        try:
            t0 = time.time()

            # Step 1: MinerU 解析 PDF
            blocks, img_count = parse_pdf_with_mineru(str(pdf_path), str(img_dir))

            # Step 2: 获取 TOC 数据
            toc_data = None
            toc_source = "none"
            if use_llm:
                try:
                    toc_data = extract_toc_from_pdf(str(pdf_path), api_url, api_key, model)
                    toc_source = "llm"
                except Exception as e:
                    print(f"  ⚠️ LLM TOC 提取失败: {e}，回退到 prefix_map")

            # Step 3: 构建层级
            if toc_data:
                # TOC 骨架方案（精确）
                skeleton = build_skeleton_tree(toc_data)
                offset = detect_page_offset(toc_data, blocks)
                hierarchy = assign_blocks_to_skeleton(skeleton, blocks, page_offset=offset)
            else:
                # prefix_map 兜底
                hierarchy = build_hierarchy(blocks)

            elapsed = time.time() - t0

            # 统计
            def count_nodes(ns):
                return sum(1 + count_nodes(n.get("children", [])) for n in ns)
            def count_ctx(ns):
                return sum(len(n.get("contexts", [])) + count_ctx(n.get("children", [])) for n in ns)

            n_nodes = count_nodes(hierarchy)
            n_ctx = count_ctx(hierarchy)

            # 保存 JSON
            json_path = doc_output_dir / "hierarchy.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(hierarchy, f, ensure_ascii=False, indent=2)

            # 保存 TOC 数据（如果有的话）
            if toc_data:
                toc_path = doc_output_dir / "toc.json"
                with open(toc_path, "w", encoding="utf-8") as f:
                    json.dump(toc_data, f, ensure_ascii=False, indent=2)

            print(f"  ✅ {elapsed:.1f}s | {len(blocks)} blocks | {n_nodes} nodes | {n_ctx} ctx | {img_count} imgs | toc={toc_source}")
            summary.append({
                "doc_id": doc_id, "pdf": str(rel), "status": "ok",
                "blocks": len(blocks), "nodes": n_nodes, "contexts": n_ctx,
                "images": img_count, "toc_source": toc_source,
                "time": round(elapsed, 1),
            })

        except Exception as e:
            elapsed = time.time() - t0
            print(f"  ❌ {elapsed:.1f}s | ERROR: {e}")
            summary.append({
                "doc_id": doc_id, "pdf": str(rel), "status": "error",
                "error": str(e), "time": round(elapsed, 1),
            })

    total_elapsed = time.time() - total_start

    # 保存汇总报告
    report = {
        "total_pdfs": len(pdf_files),
        "success": sum(1 for s in summary if s["status"] == "ok"),
        "failed": sum(1 for s in summary if s["status"] == "error"),
        "total_time": round(total_elapsed, 1),
        "details": summary,
    }
    report_path = output_root / "batch_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 80)
    print(f"批量解析完成: {report['success']}/{report['total_pdfs']} 成功, "
          f"{report['failed']} 失败, 总耗时 {total_elapsed:.1f}s")
    print(f"汇总报告: {report_path}")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MinerU 批量解析 PDF（TOC 骨架方案）")
    parser.add_argument("--dir", type=str, default=GSMA_PDF_DIR, help="PDF 目录路径")
    parser.add_argument("--output", type=str, default=OUTPUT_ROOT, help="输出根目录")
    parser.add_argument("--limit", type=int, default=None, help="限制处理文件数（用于测试）")
    parser.add_argument("--llm-url", type=str, default=None, help="LLM API URL（不传则从环境变量 OPENAI_BASE_URL 读取）")
    parser.add_argument("--llm-key", type=str, default=None, help="LLM API Key（不传则从环境变量 OPENAI_API_KEY 读取）")
    parser.add_argument("--llm-model", type=str, default=None, help="LLM 模型名（不传则从环境变量 OPENAI_MODEL 读取）")
    args = parser.parse_args()
    batch_parse(
        pdf_dir=args.dir,
        output_root=args.output,
        limit=args.limit,
        llm_api_url=args.llm_url,
        llm_api_key=args.llm_key,
        llm_model=args.llm_model,
    )
