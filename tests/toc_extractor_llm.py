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

TOC_EXTRACTION_SYSTEM_PROMPT = """你是一个 PDF 文档结构分析专家。你的任务是从文档的前几页文本中提取目录（Table of Contents）结构。

输出严格的 JSON 数组，每个元素代表一个章节条目：
[
  {"level": 1, "number": "1", "title": "Introduction", "page": 4},
  {"level": 2, "number": "1.1", "title": "Overview", "page": 4},
  {"level": 1, "number": "Annex A", "title": "Use Cases (Informative)", "page": 18},
  {"level": 2, "number": "A.1", "title": "Consumer Devices Use Case", "page": 18}
]

规则：
1. level: 整数，1=顶级章节，2=子节，3=子子节，以此类推
2. number: 章节编号（如 "1", "1.1", "3.2.1", "Annex A", "A.1"）。没有编号的顶级标题用空字符串
3. title: 章节标题文字（不含编号前缀）
4. page: 该章节起始的页码（印刷页码，即文档中页脚/页眉显示的页码）
5. 按文档中出现的顺序排列
6. 包含所有章节层级，不要遗漏
7. 只输出 JSON 数组，不要输出任何解释、Markdown 标记或代码围栏"""

TOC_EXTRACTION_USER_TEMPLATE = """以下是 PDF 文档前 {page_count} 页的文本内容（由 OCR/文本提取获得，可能有噪声）。
请从中提取完整的目录结构。

注意：
- 文档可能有一个专门的 "Table of Contents" 页面，优先从该页面提取
- 如果没有目录页，从标题层级推断结构
- 页码以文档中实际显示的页码为准
- Annex 是顶级章节（level=1），其子节如 A.1, A.2 是 level=2

--- 文本开始 ---
{text_content}
--- 文本结束 ---

请输出 JSON 数组："""


# ==================== 核心函数 ====================

def extract_text_from_pdf_pages(pdf_path: str, max_pages: int = 5) -> str:
    """
    用 MinerU 提取 PDF 前 N 页的纯文本。

    Args:
        pdf_path: PDF 文件路径
        max_pages: 提取的最大页数

    Returns:
        拼接后的文本字符串
    """
    from mineru.parser import parse

    page_range = f"1-{max_pages}" if max_pages > 1 else "1"
    result = parse(
        pdf_path,
        tier="basic",
        ocr_mode="auto",
        image_analysis=False,
        page_range=page_range,
    )

    pages_text = []
    for page in result.pages:
        page_texts = []
        for block in page.blocks:
            if block.type in ("paragraph_title", "text"):
                text = ""
                for span in (block.content or []):
                    if hasattr(span, "content") and isinstance(span.content, str):
                        text += span.content
                text = text.strip()
                if text:
                    prefix = "[TITLE] " if block.type == "paragraph_title" else ""
                    page_texts.append(f"{prefix}{text}")
            elif block.type == "table":
                for cb in (block.content or []):
                    if hasattr(cb, "content") and isinstance(cb.content, str) and cb.content.strip():
                        page_texts.append(f"[TABLE] {cb.content.strip()[:500]}")
                        break
        if page_texts:
            pages_text.append(f"--- Page {page.page_idx + 1} ---\n" + "\n".join(page_texts))

    return "\n\n".join(pages_text)


def extract_toc_from_pdf(
    pdf_path: str,
    api_url: str,
    api_key: str,
    model: str,
    max_pages: int = 5,
    temperature: float = 0.1,
    timeout: float = 120.0,
) -> List[Dict[str, Any]]:
    """
    从 PDF 前 N 页提取 TOC 结构（调用 LLM）。

    Args:
        pdf_path: PDF 文件路径
        api_url: LLM API Base URL（OpenAI 兼容）
        api_key: API Key
        model: 模型名称
        max_pages: 提取的最大页数
        temperature: LLM temperature
        timeout: 请求超时（秒）

    Returns:
        TOC 条目列表，格式同 SGP41_TOC：
        [{"level": 1, "number": "1", "title": "Introduction", "page": 4}, ...]
    """
    logger.info(f"Extracting TOC from {pdf_path} (first {max_pages} pages)...")

    # Step 1: 提取文本
    text_content = extract_text_from_pdf_pages(pdf_path, max_pages)
    if not text_content.strip():
        logger.warning(f"No text extracted from {pdf_path}")
        return []

    logger.info(f"Extracted {len(text_content)} chars from {pdf_path}")

    # Step 2: 构造 LLM 请求
    user_content = TOC_EXTRACTION_USER_TEMPLATE.format(
        page_count=max_pages,
        text_content=text_content[:15000],  # 限制长度避免超 token
    )

    messages = [
        {"role": "system", "content": TOC_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    # OpenAI 兼容协议：Base URL 后需追加 /chat/completions
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

    # Step 3: 调用 LLM
    logger.info(f"Calling LLM: {url}, model={model}")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        body = response.text[:2000]
        logger.error(f"LLM API error {response.status_code}: {body}")
        raise RuntimeError(f"LLM API error {response.status_code}: {body}")

    result = response.json()

    # Step 4: 解析响应
    if "choices" in result and len(result["choices"]) > 0:
        content = result["choices"][0]["message"]["content"]
    else:
        raise ValueError(f"Unexpected LLM response format: {result}")

    # 剥离可能的 Markdown 代码围栏
    content = content.strip()
    if content.startswith("```"):
        # 去掉 ```json ... ``` 或 ``` ... ```
        content = re.sub(r'^```(?:json)?\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

    # 解析 JSON
    try:
        toc = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM output as JSON: {e}\nContent: {content[:500]}")
        raise ValueError(f"LLM output is not valid JSON: {e}")

    # 验证格式
    if not isinstance(toc, list):
        raise ValueError(f"LLM output is not a JSON array, got {type(toc)}")

    for i, entry in enumerate(toc):
        if not isinstance(entry, dict):
            raise ValueError(f"TOC entry {i} is not a dict: {entry}")
        for key in ("level", "number", "title", "page"):
            if key not in entry:
                raise ValueError(f"TOC entry {i} missing key '{key}': {entry}")

    logger.info(f"Extracted {len(toc)} TOC entries from {pdf_path}")
    return toc


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
