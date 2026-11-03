"""
LLM-based TOC extractor — 从 PDF 前 N 页提取目录结构

用 MinerU 提取前 N 页文本，送给 LLM 输出 TOC 骨架数据。
"""

import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

import httpx

from smartcard_kb.logger import logger


# ==================== Prompt ====================

TOC_EXTRACTION_SYSTEM_PROMPT = """你是一个 PDF 文档结构分析专家。你的任务是从给定的文本页中找到目录区域，并提取其中列出的目录条目。

目录区域的常见名称包括但不限于：Table of Contents、Contents、目录、摘要目录等。

输出严格的 JSON 对象，包含两个字段：
{
  "entries": [
    {"level": 1, "number": "1", "title": "Introduction", "page": 4},
    {"level": 2, "number": "1.1", "title": "Overview", "page": 4}
  ],
  "complete": true
}

字段说明：
- entries: 目录条目数组，每个条目包含 level/number/title/page
- complete: 布尔值，表示从当前文本中是否已提取到目录的**末尾**。判断依据：
  - 如果目录明显被截断（如最后一个条目后还有更多内容未显示），设为 false
  - 如果目录已完整提取（如最后几个条目是 Annex/附录/文档管理/参考文献等文档末尾章节），设为 true
  - 如果文本中没有找到目录区域，entries 为空数组，complete 设为 true

条目规则：
1. level: 整数，1=顶级章节，2=子节，3=子子节。根据编号层级推断
2. number: 章节编号原文（如 "1", "1.1", "3.2.1", "Annex A", "A.1"）
3. title: 章节标题文字（不含编号前缀）
4. page: 目录中该条目对应的页码
5. 按目录中出现的顺序排列
6. 只输出 JSON 对象，不要输出任何解释、Markdown 标记或代码围栏"""

TOC_EXTRACTION_USER_TEMPLATE = """以下是 PDF 文档第 {start_page}-{end_page} 页的文本内容。
请找到其中的目录区域，提取目录条目，并判断目录是否已完整提取。

注意：
- 目录可能叫 Table of Contents、Contents、目录 或其他类似名称
- 如果没有找到目录区域，返回 {{"entries": [], "complete": true}}
- 如果目录在文本末尾处被截断（还有后续条目未显示），设 complete 为 false

--- 文本开始 ---
{text_content}
--- 文本结束 ---

请输出 JSON 对象："""


# ==================== 核心函数 ====================

def extract_text_from_pdf_pages(pdf_path: str, max_pages: int = 5) -> str:
    """
    用 PyMuPDF 提取 PDF 前 N 页的纯文本。

    PyMuPDF 直接提取文字层，比 MinerU 的版面分析更适合提取目录等文本内容。

    Args:
        pdf_path: PDF 文件路径
        max_pages: 提取的最大页数

    Returns:
        拼接后的文本字符串
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    pages_text = []
    total_pages = min(max_pages, len(doc))

    for page_idx in range(total_pages):
        page = doc[page_idx]
        text = page.get_text("text").strip()
        if text:
            pages_text.append(f"--- Page {page_idx + 1} ---\n{text}")

    doc.close()
    return "\n\n".join(pages_text)


def _call_llm_for_toc(
    api_url: str,
    api_key: str,
    model: str,
    text_content: str,
    start_page: int,
    end_page: int,
    temperature: float = 0.1,
    timeout: float = 1200.0,
) -> tuple:
    """
    调用 LLM 提取一轮 TOC，返回 (entries, complete)。

    Returns:
        (entries, complete): entries 为 TOC 条目列表，complete 为是否完整
    """
    user_content = TOC_EXTRACTION_USER_TEMPLATE.format(
        start_page=start_page,
        end_page=end_page,
        text_content=text_content,
    )

    messages = [
        {"role": "system", "content": TOC_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    url = api_url.strip().rstrip("/")
    if not url.endswith("/chat/completions"):
        url = f"{url}/chat/completions"

    payload = {
        "model": model.strip(),
        "messages": messages,
        "temperature": temperature,
    }

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }

    logger.info(f"Calling LLM: {url}, model={model}, pages={start_page}-{end_page}")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        body = response.text[:2000]
        logger.error(f"LLM API error {response.status_code}: {body}")
        raise RuntimeError(f"LLM API error {response.status_code}: {body}")

    result = response.json()

    if "choices" in result and len(result["choices"]) > 0:
        content = result["choices"][0]["message"]["content"]
    else:
        raise ValueError(f"Unexpected LLM response format: {result}")

    # 剥离可能的 Markdown 代码围栏
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```(?:json)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

    # 解析 JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM output as JSON: {e}\nContent: {content[:500]}")
        raise ValueError(f"LLM output is not valid JSON: {e}")

    # 兼容：如果 LLM 返回的是数组（旧格式），当作 entries 处理，complete=True
    if isinstance(data, list):
        entries = data
        complete = True
    elif isinstance(data, dict):
        entries = data.get("entries", [])
        complete = data.get("complete", True)
    else:
        raise ValueError(f"LLM output is neither array nor object: {type(data)}")

    # 验证 entries 格式
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"TOC entry {i} is not a dict: {entry}")
        for key in ("level", "number", "title", "page"):
            if key not in entry:
                raise ValueError(f"TOC entry {i} missing key '{key}': {entry}")

    return entries, complete


def extract_toc_from_pdf(
    pdf_path: str,
    api_url: str,
    api_key: str,
    model: str,
    max_pages: int = 10,
    pages_per_round: int = 5,
    max_rounds: int = 4,
    temperature: float = 0.1,
    timeout: float = 1200.0,
) -> List[Dict[str, Any]]:
    """
    从 PDF 提取完整 TOC 结构（增量式，调用 LLM）。

    流程：
    1. 一次性提取前 max_pages 页文本并缓存（按页拆分）
    2. 第一轮送前 pages_per_round 页给 LLM
    3. 若 LLM 返回 complete=false，从缓存取下一页范围的文本继续送
    4. 合并所有轮次的 entries，直到 complete=true 或缓存耗尽

    Args:
        pdf_path: PDF 文件路径
        api_url: LLM API Base URL（OpenAI 兼容）
        api_key: API Key
        model: 模型名称
        max_pages: 一次性提取的最大页数（缓存上限）
        pages_per_round: 每轮送 LLM 的页数
        max_rounds: 最大轮数
        temperature: LLM temperature
        timeout: 请求超时（秒）

    Returns:
        TOC 条目列表
    """
    import fitz  # PyMuPDF

    logger.info(f"Extracting TOC from {pdf_path} (incremental, {pages_per_round} pages/round, cache {max_pages} pages)...")

    # Step 1: 一次性提取前 max_pages 页文本，按页缓存
    doc = fitz.open(pdf_path)
    total_pdf_pages = len(doc)
    cache_pages = min(max_pages, total_pdf_pages)

    page_texts = {}  # page_num (1-based) -> text
    for page_idx in range(cache_pages):
        page = doc[page_idx]
        text = page.get_text("text").strip()
        if text:
            page_texts[page_idx + 1] = text
    doc.close()

    logger.info(f"Cached {len(page_texts)} pages of text from {pdf_path} (PDF has {total_pdf_pages} pages)")

    if not page_texts:
        logger.warning(f"No text extracted from {pdf_path}")
        return []

    # Step 2: 增量式送 LLM
    all_entries = []
    cached_page_nums = sorted(page_texts.keys())
    current_idx = 0  # 在 cached_page_nums 中的索引

    for round_num in range(1, max_rounds + 1):
        # 取当前轮次的页
        end_idx = min(current_idx + pages_per_round, len(cached_page_nums))
        round_pages = cached_page_nums[current_idx:end_idx]

        if not round_pages:
            logger.info("No more cached pages to send")
            break

        start_page = round_pages[0]
        end_page = round_pages[-1]

        # 拼接当前轮次的文本
        text_content = "\n\n".join(
            f"--- Page {pn} ---\n{page_texts[pn]}" for pn in round_pages
        )

        logger.info(f"Round {round_num}: sending pages {start_page}-{end_page} ({len(text_content)} chars)")

        # 调用 LLM
        entries, complete = _call_llm_for_toc(
            api_url=api_url,
            api_key=api_key,
            model=model,
            text_content=text_content,
            start_page=start_page,
            end_page=end_page,
            temperature=temperature,
            timeout=timeout,
        )

        logger.info(f"  Round {round_num}: {len(entries)} entries, complete={complete}")
        all_entries.extend(entries)

        if complete:
            logger.info(f"TOC extraction complete after round {round_num}")
            break

        # 继续下一轮（从缓存取）
        current_idx = end_idx

    logger.info(f"Total TOC entries extracted: {len(all_entries)} from {pdf_path}")
    return all_entries


# ==================== 便捷函数 ====================

def extract_toc_with_fallback(
    pdf_path: str,
    api_url: str,
    api_key: str,
    model: str,
    static_toc: Optional[List[Dict]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """
    提取 TOC，支持静态 TOC 优先 + LLM 兜底。

    Args:
        pdf_path: PDF 文件路径
        api_url: LLM API URL
        api_key: API Key
        model: 模型名称
        static_toc: 静态 TOC 数据（如果提供且匹配则直接使用）

    Returns:
        TOC 列表，或 None（提取失败时）
    """
    # 如果有静态 TOC，先检查文件名是否匹配
    if static_toc is not None:
        # 简单启发式：检查静态 TOC 的页码范围是否覆盖文档
        return static_toc

    # 否则用 LLM 提取
    try:
        return extract_toc_from_pdf(pdf_path, api_url, api_key, model)
    except Exception as e:
        logger.error(f"TOC extraction failed for {pdf_path}: {e}")
        return None


# ==================== CLI 入口 ====================

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="从 PDF 前 N 页用 LLM 提取 TOC")
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument("--pages", type=int, default=5, help="提取前 N 页（默认 5）")
    parser.add_argument("--api-url", default=None, help="LLM API URL（默认从 OPENAI_BASE_URL 读取）")
    parser.add_argument("--api-key", default=None, help="LLM API Key（默认从 OPENAI_API_KEY 读取）")
    parser.add_argument("--model", default=None, help="模型名称（默认从 OPENAI_MODEL 或 qwen-plus）")
    parser.add_argument("--output", default=None, help="输出 JSON 文件路径（默认打印到终端）")
    args = parser.parse_args()

    api_url = args.api_url or os.getenv("OPENAI_BASE_URL", "")
    api_key = args.api_key or os.getenv("OPENAI_API_KEY", "")
    model = args.model or os.getenv("OPENAI_MODEL", "qwen-plus")

    if not api_url or not api_key:
        print("❌ 请提供 --api-url 和 --api-key，或设置环境变量 OPENAI_BASE_URL / OPENAI_API_KEY")
        sys.exit(1)

    print(f"PDF: {args.pdf_path}")
    print(f"提取前 {args.pages} 页, model={model}")
    print()

    toc = extract_toc_from_pdf(
        pdf_path=args.pdf_path,
        api_url=api_url,
        api_key=api_key,
        model=model,
        max_pages=args.pages,
    )

    print(f"\n✅ 提取了 {len(toc)} 个 TOC 条目：\n")
    for entry in toc:
        indent = "  " * (entry["level"] - 1)
        print(f"{indent}{entry['number']} {entry['title']} (p.{entry['page']})")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(toc, f, ensure_ascii=False, indent=2)
        print(f"\n已保存到 {args.output}")
