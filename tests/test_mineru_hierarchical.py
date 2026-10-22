"""测试 MinerU 4.0 + TOC 骨架方案进行 PDF 层级解析"""

import sys
import json
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from toc_skeleton import SGP41_TOC, build_skeleton_tree, detect_page_offset, assign_blocks_to_skeleton


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


def parse_pdf_with_mineru(pdf_path: str, page_range: str = "", image_output_dir: str = "tests/output/pictures") -> list:
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

    # 确保图片输出目录存在
    Path(image_output_dir).mkdir(parents=True, exist_ok=True)

    result = parse(
        pdf_path,
        tier="basic",
        ocr_mode="auto",
        image_analysis=False,
        page_range=page_range,
    )

    # 导出图片到指定目录（MinerU 4.0 图片以 base64 存储，需解码保存）
    import base64
    image_count = 0
    for page in result.pages:
        page_idx = page.page_idx
        for block in page.blocks:
            if block.type == "image":
                for content_block in (block.content or []):
                    if not hasattr(content_block, "type") or content_block.type != "image_body":
                        continue
                    # 优先用 image_path（文件路径），其次用 image_base64（base64 数据）
                    saved_path = ""
                    if hasattr(content_block, "image_path") and content_block.image_path:
                        src = Path(content_block.image_path)
                        if src.exists():
                            import shutil
                            dst = Path(image_output_dir) / f"page{page_idx+1}_img{image_count+1}{src.suffix}"
                            shutil.copy2(str(src), str(dst))
                            saved_path = str(dst)
                    elif hasattr(content_block, "image_base64") and content_block.image_base64:
                        img_data = base64.b64decode(content_block.image_base64)
                        # MinerU 4.0 的 base64 数据可能包含未知头部，需跳过找到实际图片数据
                        # 按优先级检测常见图片格式的 magic bytes
                        jpeg_offset = img_data.find(b'\xff\xd8\xff')
                        png_offset = img_data.find(b'\x89PNG\r\n\x1a\n')

                        if jpeg_offset >= 0 and (png_offset < 0 or jpeg_offset <= png_offset):
                            img_data = img_data[jpeg_offset:]
                            ext = ".jpg"
                        elif png_offset >= 0:
                            img_data = img_data[png_offset:]
                            ext = ".png"
                        else:
                            ext = ".png"  # fallback，可能无法打开

                        dst = Path(image_output_dir) / f"page{page_idx+1}_img{image_count+1}{ext}"
                        dst.write_bytes(img_data)
                        saved_path = str(dst)
                    if saved_path:
                        content_block.image_path = saved_path
                        image_count += 1

    print(f"  导出 {image_count} 张图片到 {image_output_dir}")

    # 将 ParseResult 转换为扁平 block 列表
    blocks = []
    for page in result.pages:
        page_idx = page.page_idx
        for block in page.blocks:
            block_type = block.type

            if block_type == "paragraph_title":
                text = _extract_text_from_content(block.content)
                level = getattr(block, "level", 0)
                blocks.append({
                    "type": "title",
                    "text": text,
                    "page_idx": page_idx,
                    "level": level,
                })

            elif block_type == "text":
                text = _extract_text_from_content(block.content)
                if text:
                    blocks.append({
                        "type": "text",
                        "text": text,
                        "page_idx": page_idx,
                    })

            elif block_type == "image":
                img_path = _extract_image_path(block)
                blocks.append({
                    "type": "image",
                    "img_path": img_path,
                    "page_idx": page_idx,
                })

            elif block_type == "table":
                table_text = _extract_table_text(block)
                if table_text:
                    blocks.append({
                        "type": "table",
                        "text": table_text,
                        "page_idx": page_idx,
                    })

    print(f"MinerU 4.0 解析完成，共 {len(blocks)} 个 block")
    return blocks


# ==================== 测试入口 ====================

def test_mineru_hierarchical():
    """使用 MinerU 4.0 + TOC 骨架方案解析 PDF 并输出层级 JSON"""

    pdf_path = "specs/03-management-provisioning/gsma/SGP.41/SGP.41-eSIM-IFPP-Architecture-and-Requirements-v1.0.pdf"
    output_json_path = "tests/output/sgp41_mineru_hierarchical_full.json"

    print("=" * 80)
    print("MinerU 4.0 + TOC 骨架方案 PDF 层级解析测试")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print()

    if not Path(pdf_path).exists():
        print(f"❌ 文件不存在: {pdf_path}")
        return

    # 第 1 步：MinerU 解析 PDF，提取 blocks
    print("步骤 1: MinerU 4.0 解析 PDF...")
    blocks = parse_pdf_with_mineru(pdf_path)
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
    print(f"  - MinerU block 数: {len(blocks)}")
    print(f"  - 页码偏移: {offset}")
    print("=" * 80)


def _iter_nodes(nodes: list):
    """递归遍历所有节点（扁平迭代器）"""
    for node in nodes:
        yield node
        yield from _iter_nodes(node.get("children", []))


if __name__ == "__main__":
    test_mineru_hierarchical()
