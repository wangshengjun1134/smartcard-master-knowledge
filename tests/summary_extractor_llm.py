"""
Summary Extractor — 分层概要提取模块

核心思路：
1. 从最底层章节（叶子节点）开始，读取其 items 内容提交给 LLM 提取概要
2. 自底向上逐层处理父节点，将子节点概要 + 自身 items 一起提交给 LLM
3. 每个节点提取 256/512/1024 三种长度的概要
"""

import json
import re
from typing import List, Dict, Any, Optional

import httpx

from smartcard_kb.logger import logger


# ==================== Prompt ====================

SUMMARY_EXTRACTOR_SYSTEM_PROMPT = """你是一个文档概要提取专家。你的任务是根据提供的章节内容，生成准确、简洁的概要。

**输入数据：**

1. **章节标题**：当前章节的完整标题（含编号）
2. **章节层级**：当前章节在文档结构中的层级（1=一级, 2=二级...）
3. **章节内容**：当前章节范围内的所有 doc_items 内容（包括文本、表格描述、图片描述等）
4. **子节点概要**（可选）：如果当前章节有子章节，会提供子章节的概要信息

**任务要求：**

1. 仔细阅读章节内容，提取核心信息和关键要点
2. 如果有子节点概要，需要综合子节点概要和自身内容，生成更高层次的概括
3. 输出指定长度的概要（目标字符数：256/512/1024）

**概要编写规则：**

- 使用第三人称，避免"本节"、"本章"等指示词
- 保留关键术语、编号、表格/图片引用
- 按内容逻辑组织，而非简单罗列
- 语言简洁、信息密度高
- 概要长度尽量接近目标字符数（允许 ±10% 偏差）

**输出格式：**

输出严格的 JSON 对象：
```json
{
  "summary": "概要内容文本"
}
```

**注意事项：**

- 只输出 JSON 对象，不要输出任何解释、Markdown 标记或代码围栏
- 如果内容为空或无法提取，返回空字符串"""


SUMMARY_EXTRACTOR_USER_TEMPLATE = """请为以下章节提取概要。

**章节信息：**
- 标题：{title}
- 层级：{level}
- 目标概要长度：约 {target_length} 字符

**章节内容：**
{content}

{children_summaries_section}

请输出约 {target_length} 字符的概要，严格遵循 JSON 格式输出。"""


CHILDREN_SUMMARIES_TEMPLATE = """**子章节概要（供参考）：**
{children_text}

请综合以上子章节概要和当前章节内容，生成更高层次的概括。"""


# ==================== LLM 调用 ====================

def _call_llm_for_summary(
    api_url: str,
    api_key: str,
    model: str,
    title: str,
    level: int,
    content: str,
    children_summaries: List[Dict[str, Any]] = None,
    target_length: int = 512,
    temperature: float = 0.3,
    timeout: float = 300.0,
) -> str:
    """
    调用 LLM 提取单个章节的概要。

    Args:
        api_url: LLM API URL
        api_key: API Key
        model: 模型名称
        title: 章节标题
        level: 章节层级
        content: 章节内容文本
        children_summaries: 子节点概要列表，每个包含 title 和 summary
        target_length: 目标概要长度（256/512/1024）
        temperature: 温度参数
        timeout: 请求超时（秒）

    Returns:
        提取的概要文本
    """
    # 构建子节点概要部分
    children_section = ""
    if children_summaries:
        children_lines = []
        for child in children_summaries:
            child_title = child.get("title", "")
            child_summary = child.get("summary", "")
            if child_summary:
                children_lines.append(f"- {child_title}: {child_summary}")
        if children_lines:
            children_section = CHILDREN_SUMMARIES_TEMPLATE.format(
                children_text="\n".join(children_lines)
            )

    # 构建用户消息
    user_content = SUMMARY_EXTRACTOR_USER_TEMPLATE.format(
        title=title,
        level=level,
        target_length=target_length,
        content=content if content else "(无内容)",
        children_summaries_section=children_section,
    )

    # 构建请求
    url = api_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SUMMARY_EXTRACTOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": target_length * 2,  # 留一些余量
    }

    # 📤 打印请求内容
    logger.info("=" * 80)
    logger.info("📤 LLM Request for Summary Extraction")
    logger.info("=" * 80)
    logger.info(f"URL: {url}")
    logger.info(f"Model: {model.strip()}")
    logger.info(f"Temperature: {temperature}")
    logger.info(f"Target length: {target_length} chars")
    logger.info("-" * 80)
    logger.info(f"Title: {title}")
    logger.info(f"Level: {level}")
    logger.info(f"Content length: {len(content)} chars")
    if children_summaries:
        logger.info(f"Children summaries: {len(children_summaries)}")
    logger.info("-" * 80)
    logger.info("User Content:")
    logger.info(user_content[:2000] + "..." if len(user_content) > 2000 else user_content)
    logger.info("=" * 80)

    logger.info(f"Calling LLM for summary: {url}, model={model}, target_length={target_length}")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        body = response.text[:2000]
        logger.error(f"LLM API error {response.status_code}: {body}")
        raise RuntimeError(f"LLM API error {response.status_code}: {body}")

    result = response.json()

    # 📥 打印响应内容
    logger.info("=" * 80)
    logger.info("📥 LLM Response for Summary Extraction")
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
        logger.info(content)
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

    summary = data.get("summary", "")
    return summary


# ==================== 核心函数 ====================

def extract_summary_with_llm(
    title: str,
    level: int,
    content: str,
    children_summaries: List[Dict[str, Any]] = None,
    api_url: str = "",
    api_key: str = "",
    model: str = "",
    temperature: float = 0.3,
    timeout: float = 300.0,
) -> Dict[str, str]:
    """
    提取单个章节的三种长度概要。

    Args:
        title: 章节标题
        level: 章节层级
        content: 章节内容文本
        children_summaries: 子节点概要列表，每个包含 title 和 summary
        api_url: LLM API URL
        api_key: API Key
        model: 模型名称
        temperature: 温度参数
        timeout: 请求超时（秒）

    Returns:
        dict: {"summary_256": "...", "summary_512": "...", "summary_1024": "..."}
    """
    result = {}

    # 依次提取三种长度的概要
    for target_length in [256, 512, 1024]:
        try:
            summary = _call_llm_for_summary(
                api_url=api_url,
                api_key=api_key,
                model=model,
                title=title,
                level=level,
                content=content,
                children_summaries=children_summaries,
                target_length=target_length,
                temperature=temperature,
                timeout=timeout,
            )
            result[f"summary_{target_length}"] = summary
            logger.info(f"Summary extracted for '{title}' (target={target_length}): {len(summary)} chars")
        except Exception as e:
            logger.error(f"Failed to extract summary_{target_length} for '{title}': {e}")
            result[f"summary_{target_length}"] = ""

    return result
