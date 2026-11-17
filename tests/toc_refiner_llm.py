"""
TOC Refiner — 结合 doc_items 标题 + PDF 目录文本，用 LLM 推理生成准确目录树

核心思路：
1. 从 doc_items 查询所有 section_header（已有标题数据）
2. 从 PDF 前 10 页提取目录文本
3. 将两部分数据一起提交给 LLM 推理，输出完整准确的目录层级
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

import httpx

from smartcard_kb.logger import logger


# ==================== Prompt ====================

TOC_REFINER_SYSTEM_PROMPT = """你是一个 PDF 文档结构分析专家。你的任务是综合两部分数据，输出完整准确的文档目录结构。

**输入数据：**

1. **PDF 目录页文本**：从 PDF 前 10 页提取的目录区域文本，包含章节编号、标题和页码
2. **doc_items 标题列表**：文档解析引擎已提取的所有标题，按 order_index 排序，包含标题文本和所在页码

**任务要求：**

1. 分析 PDF 目录页文本，提取目录条目（编号、标题、页码）
2. 对比 doc_items 标题列表，发现目录中未体现但实际存在的深层级标题
   - 例如：目录只有 "2.1.1 xxx"，但 doc_items 中存在 "2.1.1.1 yyy" 和 "2.1.1.2 zzz"
3. 输出完整准确的目录树，包括：
   - 目录中明确列出的条目
   - 内容中存在但目录未列出的深层级条目

**层级推断规则：**

- level 根据编号层级推断：
  - "1" → level 1
  - "1.1" → level 2
  - "1.1.1" → level 3
  - "Annex A" → level 1
  - "A.1" → level 2
- 如果编号不明确，根据标题在列表中的位置和上下文推断

**输出格式：**

输出严格的 JSON 对象：
```json
{
  "entries": [
    {
      "title": "1 Introduction",
      "level": 1,
      "page": 10,
      "item_index": 5
    },
    {
      "title": "1.1 Overview",
      "level": 2,
      "page": 12,
      "item_index": 8
    }
  ]
}
```

字段说明：
- title: 完整标题（含编号，如 "1.2.3 xxx"）
- level: 层级（1=一级, 2=二级...）
- page: 该章节起始页码（1-based）
- item_index: 对应 doc_items 中的 order_index（用于确定 start_item_index）

**注意事项：**

- entries 按文档中出现的顺序排列
- 只输出 JSON 对象，不要输出任何解释、Markdown 标记或代码围栏
- 如果 PDF 目录页文本为空或无法解析，仅基于 doc_items 标题列表推断"""

TOC_REFINER_USER_TEMPLATE = """以下是 PDF 文档的目录页文本和 doc_items 标题列表。

--- PDF 目录页文本（第 {start_page}-{end_page} 页）---
{toc_text}
--- 目录页文本结束 ---

--- doc_items 标题列表（共 {item_count} 个标题，按 order_index 排序）---
{items_text}
--- 标题列表结束 ---

请综合两部分数据，输出完整准确的目录结构。"""


# ==================== 数据提取 ====================

def extract_toc_text_from_pdf(pdf_path: str, max_pages: int = 10) -> Tuple[str, int, int]:
    """
    用 PyMuPDF 提取 PDF 前 N 页的纯文本（用于目录提取）。

    Args:
        pdf_path: PDF 文件路径
        max_pages: 提取的最大页数

    Returns:
        (text_content, start_page, end_page): 拼接后的文本、起始页、结束页（1-based）
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    total_pages = min(max_pages, len(doc))

    pages_text = []
    for page_idx in range(total_pages):
        page = doc[page_idx]
        text = page.get_text("text").strip()
        if text:
            pages_text.append(f"--- Page {page_idx + 1} ---\n{text}")

    doc.close()

    text_content = "\n\n".join(pages_text)
    return text_content, 1, total_pages


def format_doc_items_headers(items: List[Dict[str, Any]], max_items: int = 500) -> str:
    """
    格式化 doc_items 标题列表，用于 LLM 输入。

    Args:
        items: doc_items 列表，每个条目包含 order_index, text, page_id
        max_items: 最多返回的条目数（防止 token 超限）

    Returns:
        格式化后的文本
    """
    lines = []
    for item in items[:max_items]:
        order_index = item.get("order_index", "")
        text = item.get("text", "").strip()
        page_id = item.get("page_id", "")
        # 从 page_id 提取页码（格式如 "page_001" 或 "1"）
        page_match = re.search(r'(\d+)', str(page_id))
        page_num = int(page_match.group(1)) if page_match else ""
        lines.append(f"[{order_index}] p.{page_num} {text}")

    if len(items) > max_items:
        lines.append(f"... (还有 {len(items) - max_items} 个标题未显示)")

    return "\n".join(lines)


# ==================== LLM 调用 ====================

def _call_llm_for_refined_toc(
    api_url: str,
    api_key: str,
    model: str,
    toc_text: str,
    items_text: str,
    start_page: int,
    end_page: int,
    item_count: int,
    temperature: float = 0.1,
    timeout: float = 1200.0,
) -> List[Dict[str, Any]]:
    """
    调用 LLM 推理生成准确目录树。

    Returns:
        entries 列表，每个条目包含 title, level, page, item_index
    """
    user_content = TOC_REFINER_USER_TEMPLATE.format(
        start_page=start_page,
        end_page=end_page,
        toc_text=toc_text or "(无目录页文本)",
        items_text=items_text,
        item_count=item_count,
    )

    messages = [
        {"role": "system", "content": TOC_REFINER_SYSTEM_PROMPT},
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

    # 📤 打印请求内容
    logger.info("=" * 80)
    logger.info("📤 LLM Request for TOC Refiner")
    logger.info("=" * 80)
    logger.info(f"URL: {url}")
    logger.info(f"Model: {model.strip()}")
    logger.info(f"Temperature: {temperature}")
    logger.info(f"Timeout: {timeout}s")
    logger.info("-" * 80)
    logger.info("System Prompt:")
    logger.info(TOC_REFINER_SYSTEM_PROMPT[:500] + "..." if len(TOC_REFINER_SYSTEM_PROMPT) > 500 else TOC_REFINER_SYSTEM_PROMPT)
    logger.info("-" * 80)
    logger.info("User Content:")
    logger.info(user_content[:2000] + "..." if len(user_content) > 2000 else user_content)
    logger.info("=" * 80)

    logger.info(f"Calling LLM for refined TOC: {url}, model={model}")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        body = response.text[:2000]
        logger.error(f"LLM API error {response.status_code}: {body}")
        raise RuntimeError(f"LLM API error {response.status_code}: {body}")

    result = response.json()

    # 📥 打印响应内容
    logger.info("=" * 80)
    logger.info("📥 LLM Response for TOC Refiner")
    logger.info("=" * 80)
    if "choices" in result and len(result["choices"]) > 0:
        choice = result["choices"][0]
        logger.info(f"Response ID: {result.get('id', 'N/A')}")
        logger.info(f"Model: {result.get('model', 'N/A')}")
        if "usage" in result:
            usage = result["usage"]
            logger.info(f"Token Usage: prompt={usage.get('prompt_tokens', 0)}, completion={usage.get('completion_tokens', 0)}, total={usage.get('total_tokens', 0)}")
        logger.info("-" * 80)
        logger.info("Response Content:")
        content = choice["message"]["content"]
        logger.info(content[:3000] + "..." if len(content) > 3000 else content)
    else:
        logger.info(f"Unexpected response format: {result}")
    logger.info("=" * 80)

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

    # 提取 entries
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("entries", [])
    else:
        raise ValueError(f"LLM output is neither array nor object: {type(data)}")

    # 验证 entries 格式
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"TOC entry {i} is not a dict: {entry}")
        for key in ("title", "level", "page", "item_index"):
            if key not in entry:
                raise ValueError(f"TOC entry {i} missing key '{key}': {entry}")

    return entries


# ==================== 核心函数 ====================

def refine_toc_with_llm(
    pdf_path: str,
    doc_items: List[Dict[str, Any]],
    api_url: str,
    api_key: str,
    model: str,
    max_pages: int = 10,
    max_items: int = 500,
    temperature: float = 0.1,
    timeout: float = 1200.0,
) -> List[Dict[str, Any]]:
    """
    结合 PDF 目录文本和 doc_items 标题，用 LLM 推理生成准确目录树。

    Args:
        pdf_path: PDF 文件路径
        doc_items: doc_items 表中的 section_header 条目列表
        api_url: LLM API URL
        api_key: LLM API Key
        model: LLM 模型名称
        max_pages: 从 PDF 提取的最大页数（用于目录文本）
        max_items: 最多送入 LLM 的标题数
        temperature: LLM temperature
        timeout: 请求超时（秒）

    Returns:
        entries 列表，每个条目包含 title, level, page, item_index
    """
    logger.info(f"Refining TOC for {pdf_path} with {len(doc_items)} doc_items")

    # Step 1: 提取 PDF 目录页文本
    toc_text, start_page, end_page = extract_toc_text_from_pdf(pdf_path, max_pages)
    logger.info(f"Extracted TOC text from pages {start_page}-{end_page} ({len(toc_text)} chars)")

    # Step 2: 格式化 doc_items 标题
    items_text = format_doc_items_headers(doc_items, max_items)
    logger.info(f"Formatted {len(doc_items)} doc_items headers")

    # Step 3: 调用 LLM 推理
    entries = _call_llm_for_refined_toc(
        api_url=api_url,
        api_key=api_key,
        model=model,
        toc_text=toc_text,
        items_text=items_text,
        start_page=start_page,
        end_page=end_page,
        item_count=len(doc_items),
        temperature=temperature,
        timeout=timeout,
    )

    logger.info(f"LLM returned {len(entries)} refined TOC entries")
    return entries


# ==================== CLI 入口 ====================

if __name__ == "__main__":
    import argparse
    import os
    import sys
    import psycopg2
    import psycopg2.extras

    parser = argparse.ArgumentParser(description="结合 doc_items + PDF 目录，用 LLM 推理生成准确目录树")
    parser.add_argument("pdf_path", help="PDF 文件路径")
    parser.add_argument("--document-id", required=True, help="文档 ID（用于查询 doc_items）")
    parser.add_argument("--pages", type=int, default=10, help="从 PDF 提取前 N 页（默认 10）")
    parser.add_argument("--max-items", type=int, default=500, help="最多送入 LLM 的标题数（默认 500）")
    parser.add_argument("--api-url", default=None, help="LLM API URL")
    parser.add_argument("--api-key", default=None, help="LLM API Key")
    parser.add_argument("--model", default=None, help="模型名称")
    parser.add_argument("--output", default=None, help="输出 JSON 文件路径")
    args = parser.parse_args()

    api_url = args.api_url or os.getenv("OPENAI_BASE_URL", "")
    api_key = args.api_key or os.getenv("OPENAI_API_KEY", "")
    model = args.model or os.getenv("OPENAI_MODEL", "qwen-plus")

    if not api_url or not api_key:
        print("❌ 请提供 --api-url 和 --api-key，或设置环境变量 OPENAI_BASE_URL / OPENAI_API_KEY")
        sys.exit(1)

    # 查询 doc_items
    from smartcard_kb.config import settings
    conn = psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(
        """
        SELECT order_index, text, page_id, metadata
        FROM doc_items
        WHERE document_id = %s AND label = 'section_header'
        ORDER BY order_index
        """,
        (args.document_id,),
    )
    doc_items = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    print(f"PDF: {args.pdf_path}")
    print(f"Document ID: {args.document_id}")
    print(f"doc_items: {len(doc_items)} section_headers")

    # 调用 LLM 推理
    entries = refine_toc_with_llm(
        pdf_path=args.pdf_path,
        doc_items=doc_items,
        api_url=api_url,
        api_key=api_key,
        model=model,
        max_pages=args.pages,
        max_items=args.max_items,
    )

    print(f"\n✅ Refined TOC entries: {len(entries)}")

    # 输出
    output_json = json.dumps(entries, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"Saved to {args.output}")
    else:
        print(output_json)
