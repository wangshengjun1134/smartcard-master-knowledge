"""
TOC 骨架结构重建器 — 共享模块

用 TOC 目录数据作为层级真值（骨架），解析引擎（MinerU / Docling）的 blocks 只提供内容。
三步：页码对齐 → 骨架分配 block 区间 → 标题 block 去留判定。
"""

import re
from collections import Counter


# ==================== SGP.41 TOC 数据 ====================

SGP41_TOC = [
    {"level": 1, "number": "1", "title": "Introduction", "page": 4},
    {"level": 2, "number": "1.1", "title": "Overview", "page": 4},
    {"level": 2, "number": "1.2", "title": "Scope", "page": 4},
    {"level": 2, "number": "1.3", "title": "Intended Audience", "page": 4},
    {"level": 2, "number": "1.4", "title": "Definition of Terms", "page": 5},
    {"level": 2, "number": "1.5", "title": "Abbreviations", "page": 5},
    {"level": 2, "number": "1.6", "title": "References", "page": 6},
    {"level": 2, "number": "1.7", "title": "Conventions", "page": 6},

    {"level": 1, "number": "2", "title": "Roles", "page": 7},
    {"level": 2, "number": "2.1", "title": "Mobile Service Provider, Operator", "page": 7},
    {"level": 2, "number": "2.2", "title": "eUICC Manufacturer, Device Manufacturer", "page": 7},

    {"level": 1, "number": "3", "title": "Architecture", "page": 7},
    {"level": 2, "number": "3.1", "title": "Architecture Diagram", "page": 7},
    {"level": 2, "number": "3.2", "title": "Architecture Elements", "page": 7},
    {"level": 3, "number": "3.2.1", "title": "SM-DPf", "page": 7},
    {"level": 3, "number": "3.2.2", "title": "Device Manufacturer", "page": 8},
    {"level": 3, "number": "3.2.3", "title": "FPA", "page": 9},
    {"level": 2, "number": "3.3", "title": "eUICC Architecture", "page": 9},
    {"level": 3, "number": "3.3.1", "title": "eUICC Architecture Overview", "page": 9},
    {"level": 2, "number": "3.4", "title": "Interfaces", "page": 10},
    {"level": 3, "number": "3.4.1", "title": "Operator – SM-DPf (ES2f)", "page": 10},
    {"level": 3, "number": "3.4.2", "title": "SM-DPf – Device Manufacturer (Esbpp)", "page": 10},
    {"level": 3, "number": "3.4.3", "title": "Device Manufacturer – FPA (Esfac)", "page": 11},
    {"level": 3, "number": "3.4.4", "title": "FPA – FPA Services (ES10f)", "page": 11},
    {"level": 3, "number": "3.4.5", "title": "SM-DPf – eUICC (ES8f)", "page": 11},
    {"level": 3, "number": "3.4.6", "title": "eSIM CA – EUM / SM-DPf (Esci)", "page": 11},
    {"level": 3, "number": "3.4.7", "title": "EUM – eUICC (Eseum)", "page": 11},
    {"level": 3, "number": "3.4.8", "title": "EUM – SM-DPf (Esed1)", "page": 11},
    {"level": 3, "number": "3.4.9", "title": "EUM – Device Manufacturer (Esed2)", "page": 12},

    {"level": 1, "number": "4", "title": "Requirements", "page": 12},
    {"level": 2, "number": "4.1", "title": "Functional Requirements", "page": 12},
    {"level": 3, "number": "4.1.1", "title": "General Functional Requirements", "page": 12},
    {"level": 3, "number": "4.1.2", "title": "eUICC Functional Requirements", "page": 12},
    {"level": 3, "number": "4.1.3", "title": "SM-DPf Functional Requirements", "page": 13},
    {"level": 3, "number": "4.1.4", "title": "Device Manufacturer Functional Requirements", "page": 13},
    {"level": 2, "number": "4.2", "title": "Security Requirements", "page": 13},
    {"level": 3, "number": "4.2.1", "title": "General Security Requirements", "page": 13},
    {"level": 3, "number": "4.2.2", "title": "SM-DPf Security Requirements", "page": 14},
    {"level": 3, "number": "4.2.3", "title": "EUM Security Requirements", "page": 14},

    {"level": 1, "number": "5", "title": "Procedures", "page": 14},
    {"level": 2, "number": "5.1", "title": "In-Factory Profile Provisioning Procedure using BPPs for Consumer and IoT", "page": 14},
    {"level": 2, "number": "5.2", "title": "In-Factory Profile Provisioning Procedure for M2M", "page": 17},

    {"level": 1, "number": "Annex A", "title": "Use Cases (Informative)", "page": 18},
    {"level": 2, "number": "A.1", "title": "Consumer Devices Use Case", "page": 18},
    {"level": 2, "number": "A.2", "title": "IoT Devices Use Case", "page": 18},
    {"level": 2, "number": "A.3", "title": "On-demand Profile loading during the Device Production Process - Use Case", "page": 18},
    {"level": 2, "number": "A.4", "title": "Device Inventory Management Use Case", "page": 19},

    {"level": 1, "number": "Annex B", "title": "Threats and Risks (Informative)", "page": 19},
    {"level": 2, "number": "B.1", "title": "Malicious or compromised IFPP entity", "page": 19},
    {"level": 2, "number": "B.2", "title": "Cryptographic Related Risks", "page": 19},
    {"level": 2, "number": "B.3", "title": "Quality of Service", "page": 19},
    {"level": 2, "number": "B.4", "title": "Non-human or Unpredictable", "page": 20},

    {"level": 1, "number": "Annex C", "title": "In-factory provisioning flow (Informative)", "page": 20},

    {"level": 1, "number": "Annex D", "title": "Document Management", "page": 22},
    {"level": 2, "number": "D.1", "title": "Document History", "page": 22},
    {"level": 2, "number": "D.2", "title": "Other Information", "page": 26},
]


# ==================== 工具函数 ====================

def _normalize_title(title: str) -> str:
    """归一化标题文本，用于模糊匹配（容忍 OCR 误差、特殊字符差异）"""
    t = title.strip().lower()
    # 统一各类破折号/连字符
    t = re.sub(r'[\u2013\u2014\u2012\u2015\ufe58\ufe63\uff0d]', '-', t)
    # 压缩空白
    t = re.sub(r'\s+', ' ', t)
    return t


# ==================== 核心算法 ====================

def build_skeleton_tree(toc_entries: list) -> list:
    """
    从扁平 TOC 列表构建层级树。

    输入: [{"level": 1, "number": "1", "title": "Introduction", "page": 4}, ...]
    输出: 层级树节点列表，每个节点含:
        title, number, level, page, parent_id, node_id,
        contexts, summary, children
    """
    root_nodes = []
    level_stack = []  # (level, node) 栈，用于查找父级
    level_counters = {}

    def next_node_id(level: int) -> str:
        level_counters[level] = level_counters.get(level, 0) + 1
        return f"l{level}-{level_counters[level]}"

    for entry in toc_entries:
        level = entry["level"]
        number = entry.get("number", "")
        title = f"{number} {entry['title']}" if number else entry["title"]

        # 截断栈到 level-1，找到父级
        while level_stack and level_stack[-1][0] >= level:
            level_stack.pop()

        parent_id = level_stack[-1][1]["node_id"] if level_stack else ""

        node = {
            "title": title,
            "number": number,
            "level": level,
            "page": entry["page"],
            "node_id": next_node_id(level),
            "parent_id": parent_id,
            "start_index": None,
            "end_index": None,
            "contexts": [],
            "summary": "",
            "children": [],
        }

        if level_stack:
            level_stack[-1][1]["children"].append(node)
        else:
            root_nodes.append(node)

        level_stack.append((level, node))

    return root_nodes


def detect_page_offset(toc_entries: list, blocks: list, max_offset: int = 10) -> int:
    """
    检测 TOC 印刷页码与 block 物理页码的偏移量。

    取 TOC 中 3~5 个章节标题，在 blocks 里找文本匹配的 paragraph_title，
    算 physical - printed 的差值，取众数作为全局偏移。

    返回: offset（physical_page = toc_page + offset）
    """
    offsets = []
    # 取前 10 个 level=1 或 level=2 的 TOC 条目做采样
    samples = [e for e in toc_entries if e["level"] <= 2][:10]

    for entry in samples:
        toc_key = _normalize_title(f"{entry['number']} {entry['title']}")
        for block in blocks:
            if block.get("type") not in ("paragraph_title", "title"):
                continue
            block_text = block.get("text", "")
            block_key = _normalize_title(block_text)
            if not block_key or not toc_key:
                continue
            # 匹配：完全相等 或 一方包含另一方
            if block_key == toc_key or toc_key in block_key or block_key in toc_key:
                block_page = block.get("page_idx", 0) + 1  # 转 1-based
                offset = block_page - entry["page"]
                if abs(offset) <= max_offset:
                    offsets.append(offset)
                break

    if not offsets:
        return 0
    return Counter(offsets).most_common(1)[0][0]


def _build_title_map(skeleton_nodes: list) -> dict:
    """构建归一化标题 → 骨架节点的映射表（递归遍历所有层级）"""
    title_map = {}

    def _walk(nodes):
        for node in nodes:
            key = _normalize_title(node["title"])
            if key:
                title_map[key] = node
            _walk(node["children"])

    _walk(skeleton_nodes)
    return title_map


def assign_blocks_to_skeleton(skeleton_nodes: list, blocks: list, page_offset: int = 0) -> list:
    """
    将解析引擎的 blocks 分配到骨架节点中。

    规则：
    1. 标题 block 匹配某 TOC 条目 → 切换当前节点（标题由骨架提供，不重复添加 context）
    2. 标题 block 匹配不上 → 降级为 context，挂到当前节点
    3. 非标题 block → 作为 context 挂到当前节点
    4. TOC 条目在正文中无对应标题 block → 骨架节点照常创建，内容由页码区间自然流入
    5. 页码范围兜底：即使标题没匹配上，block 的页码也能帮助找到正确的骨架节点

    返回: 更新后的骨架树（含 contexts、页码范围）
    """
    # 扁平化骨架节点（文档顺序）
    flat_skeleton = []

    def _flatten(nodes):
        for node in nodes:
            flat_skeleton.append(node)
            _flatten(node["children"])

    _flatten(skeleton_nodes)

    # 预计算每个骨架节点的期望页码范围
    # 同页的多个条目共享同一个范围：[shared_page, next_distinct_page - 1]
    # 例：4.1.1(p12) 和 4.1.2(p12) 共享 [12, 12]（下一个不同页是 p13）
    distinct_pages = sorted(set(sk["page"] for sk in flat_skeleton))
    page_to_range = {}
    for i, dp in enumerate(distinct_pages):
        end = distinct_pages[i + 1] - 1 if i + 1 < len(distinct_pages) else 9999
        page_to_range[dp] = (dp, end)

    for sk in flat_skeleton:
        start, end = page_to_range[sk["page"]]
        sk["_expected_start"] = start
        sk["_expected_end"] = end

    def _find_node_by_page(page: int, start_idx: int = 0) -> tuple:
        """根据页码找到对应的骨架节点，返回 (node, index)"""
        for j in range(start_idx, len(flat_skeleton)):
            sk = flat_skeleton[j]
            if sk["_expected_start"] <= page <= sk["_expected_end"]:
                return sk, j
        return None, -1

    current_node = None
    skeleton_idx = 0

    for block in blocks:
        block_type = block.get("type", "")
        page = block.get("page_idx", 0) + 1 + page_offset  # 1-based + offset
        is_title = block_type in ("paragraph_title", "title")

        if is_title:
            title_text = block.get("text", "").strip()
            title_key = _normalize_title(title_text)

            if not title_key:
                continue

            # 检查是否匹配当前节点（标题重复出现，跳过）
            if current_node and _normalize_title(current_node["title"]) == title_key:
                continue

            # 检查是否匹配后续骨架节点（向前查找，限制页码合理性）
            matched = False
            for j in range(skeleton_idx + 1, len(flat_skeleton)):
                sk = flat_skeleton[j]
                if _normalize_title(sk["title"]) == title_key:
                    # 页码合理性检查：block 页码 >= 骨架节点页码 - 容差
                    if page >= sk["page"] - 2:
                        current_node = sk
                        skeleton_idx = j
                        matched = True
                        break
                    # 如果页码太超前，停止查找
                    if sk["page"] > page + 3:
                        break

            if matched:
                # 标题由骨架提供，不添加 context
                _update_page_range(current_node, page)
                continue
            else:
                # 未匹配的标题 → 降级为 context
                if current_node:
                    _add_context(current_node, "text", title_text, page)
                    _update_page_range(current_node, page)
                continue

        # 非标题 block → 添加到当前节点的 contexts
        if current_node is None:
            # 还没有匹配到任何骨架节点，尝试按页码找到第一个节点
            node_by_page, idx = _find_node_by_page(page)
            if node_by_page:
                current_node = node_by_page
                skeleton_idx = idx
            else:
                continue  # 前言区内容，跳过

        # 页码范围兜底：如果 block 页码超出当前节点的期望范围，按页码重新查找
        if page > current_node.get("_expected_end", 9999):
            node_by_page, idx = _find_node_by_page(page, skeleton_idx + 1)
            if node_by_page:
                current_node = node_by_page
                skeleton_idx = idx

        label, text = _extract_block_content(block)
        if text:
            _add_context(current_node, label, text, page)
            _update_page_range(current_node, page)
        elif label in ("picture", "image", "table", "drawing", "link"):
            # 非文本 block：保留 metadata，添加到当前节点
            seq = len(current_node["contexts"]) + 1
            ctx = {
                "seq": seq,
                "label": label,
                "context": "",
                "start_index": page,
                "end_index": page,
            }
            if "metadata" in block:
                ctx["metadata"] = block["metadata"]
            current_node["contexts"].append(ctx)
            _update_page_range(current_node, page)

    # 后处理：冒泡页码范围（从子节点到父节点）
    _finalize_page_ranges(skeleton_nodes)

    # 后处理：合并相邻同类 context
    _merge_consecutive_contexts(skeleton_nodes)

    return skeleton_nodes


# ==================== 内部辅助函数 ====================

def _add_context(node: dict, label: str, text: str, page: int):
    """添加 context 到节点，seq 在当前节点的 contexts 内从 1 递增"""
    seq = len(node["contexts"]) + 1
    node["contexts"].append({
        "seq": seq,
        "label": label,
        "context": text,
        "start_index": page,
        "end_index": page,
    })


def _update_page_range(node: dict, page: int):
    """更新节点的页码范围"""
    if page is None:
        return
    if node["start_index"] is None or page < node["start_index"]:
        node["start_index"] = page
    if node["end_index"] is None or page > node["end_index"]:
        node["end_index"] = page


def _extract_block_content(block: dict) -> tuple:
    """从 block 中提取 (label, text)，子类可覆盖以适配不同引擎"""
    block_type = block.get("type", "")
    if block_type == "image":
        return "image", block.get("img_path", "")
    elif block_type == "picture":
        return "picture", ""
    elif block_type == "table":
        return "table", block.get("text", "")
    elif block_type == "drawing":
        return "drawing", ""
    elif block_type == "link":
        return "link", ""
    else:
        return "text", block.get("text", "")


def _finalize_page_ranges(nodes: list):
    """从子节点和 contexts 向上冒泡页码范围"""
    for node in nodes:
        if node["children"]:
            _finalize_page_ranges(node["children"])
            for child in node["children"]:
                if child["start_index"] is not None:
                    _update_page_range(node, child["start_index"])
                if child["end_index"] is not None:
                    _update_page_range(node, child["end_index"])
        for ctx in node["contexts"]:
            if ctx["start_index"] is not None:
                _update_page_range(node, ctx["start_index"])
            if ctx["end_index"] is not None:
                _update_page_range(node, ctx["end_index"])


def _merge_consecutive_contexts(nodes: list):
    """合并同一节点内相邻且 label 相同的 context（跨页同类内容合并为一条）"""
    for node in nodes:
        _merge_consecutive_contexts(node.get("children", []))
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
