# RAG 检索接口设计（v2）

> 状态：设计稿（2026-10-11）
> 端点：`POST /api/v1/rag/search`
> 目标：为 Agent 提供范围可控、可过滤、可裁剪的检索入口。

---

## 1. 概述

本设计替代现有 `POST /api/search`。核心思路：

1. **范围过滤降维**：`scope` 类条件（系列 / 版本 / 语言）先经 `doc_info`（约 127 行）解析出 `document_id` 集合，再用它过滤 `doc_chunks`（约 27 万行）——**不做 join**，两次简单查询即可。
2. **页面过滤零 join**：`page_id` 直接复用 `doc_chunks.page_nos`，无需 `doc_items`。
3. **内容过滤保留在 chunk 级**：`label`（item 级条件）预留定义但 v1 不实现，因为它无法降维到文档级（详见 §5.3）。
4. **检索管线分层**：`vector` / `keyword` / `hybrid`，`hybrid` 采用两路召回 + RRF 融合后再重排。

---

## 2. 接口定义

### 2.1 请求

```json
{
  "query": "What are the requirements for Profile Isolation?",

  "scope": {
    "series_id": ["SGP.27"],
    "document_id": [],
    "revision": [],
    "version_policy": "latest"
  },

  "retrieval": {
    "retrieval_type": "hybrid",
    "top_k": 50,
    "rerank_enabled": true,
    "rerank_top_k": 10,
    "similarity_threshold": null,
    "search_profile": "default"
  },

  "filters": {
    "page_id": [],
    "heading_path": null,
    "label": [],
    "language": null
  },

  "options": {
    "include_content": true,
    "include_metadata": true,
    "include_citations": true
  }
}
```

### 2.2 响应

```json
{
  "query": "What are the requirements for Profile Isolation?",
  "total": 10,
  "reranked": true,
  "profile": "default",
  "timing_ms": { "retrieval": 120, "rerank": 8000, "total": 8150 },
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "score": 4.5299,
      "score_stage": "rerank",
      "content": "……",
      "metadata": {
        "headings": ["4", "4.2", "4.2.18"],
        "heading_path": "Requirements > 4.2.18 Test Cases > ...",
        "page_nos": [180],
        "token_count": 512,
        "chunk_token_limit": 512,
        "chunk_tokenizer": "bge-m3"
      },
      "citation": {
        "document_name": "SGP.27-...pdf",
        "document_code": "SGP.27-v1.0",
        "series_id": "SGP.27",
        "revision": "1.0",
        "page_nos": [180],
        "linked_item_ids": ["uuid-1", "uuid-2"]
      }
    }
  ]
}
```

- `include_content=false` → 省略 `content`
- `include_metadata=false` → 省略 `metadata`
- `include_citations=false` → 省略 `citation`
- **投影只影响响应内容，不改变结果数量与顺序**

---

## 3. 字段与数据库映射

### 3.1 scope

| 接口字段 | 数据库字段 | 支持度 | 说明 |
|----------|-----------|--------|------|
| `series_id` | `doc_info.series_id` | ✅ | 127/127 已填充 |
| `document_id` | `doc_info.id` / `doc_chunks.document_id` | ✅ | 直接命中 chunk 主字段 |
| `revision` | `doc_info.revision` | ✅ | 127/127 已填充 |
| `version_policy` | 无对应字段 | ⚠️ | 需版本选择逻辑，见 §6 |

### 3.2 retrieval

| 接口字段 | 说明 |
|----------|------|
| `retrieval_type` | `vector` / `keyword` / `hybrid` |
| `top_k` | 初步召回数量 |
| `rerank_enabled` | 是否启用重排 |
| `rerank_top_k` | 重排后保留数量，须 ≤ `top_k` |
| `similarity_threshold` | **仅作用于向量阶段**（余弦相似度 0~1） |
| `search_profile` | 服务端预设配置名 |

> `similarity_threshold` 与重排分数（cross-encoder logit，如 4.53）量纲不同，**不可混用**。若需限制重排结果，另加 `rerank_threshold`（本版预留，默认不启用）。

### 3.3 filters

| 接口字段 | 数据库字段 | 支持度 | 说明 |
|----------|-----------|--------|------|
| `page_id` | `doc_chunks.page_nos`（复用） | ✅ | 无需 `doc_items`，见 §5.2 |
| `heading_path` | `doc_chunks.heading_path` | ✅ | chunk 字段，直接匹配 |
| `label` | `doc_items.label` | 🔒 预留 | v1 不实现，见 §5.3 |
| `language` | `doc_info.language` | ✅ | 经 scope 降维，见 §5.1 |

### 3.4 options

| 接口字段 | 说明 |
|----------|------|
| `include_content` | 是否返回 chunk 正文 |
| `include_metadata` | 是否返回元数据 |
| `include_citations` | 是否返回来源引用 |

---

## 4. 检索管线

```
① 校验（互斥 / 范围 / 默认规则）
② 解析 scope → document_ids（doc_info）
③ 构建 chunk 级过滤（document_id / page_nos / heading_path）
④ 候选召回
     ├── vector : HNSW (embedding_vec <=> q)
     ├── keyword: tsvector / BM25
     └── hybrid : vector + keyword 两路召回 → RRF 融合
⑤ 重排（cross-encoder，rerank_top_k）
⑥ 响应投影（options）
```

### 4.1 vector

```sql
SELECT id, document_id, chunk_index, text, headings, heading_path,
       linked_item_ids, page_nos, token_count, chunk_token_limit, tokenizer,
       1 - (embedding_vec <=> :q_vec) AS score
FROM doc_chunks
WHERE embedding_vec IS NOT NULL
  AND document_id = ANY(:document_ids)          -- 有 scope 时
  AND page_nos && :page_ints                    -- 有 page_id 时
  AND heading_path ILIKE :heading_pattern        -- 有 heading_path 时
  AND 1 - (embedding_vec <=> :q_vec) >= :similarity_threshold
ORDER BY embedding_vec <=> :q_vec
LIMIT :top_k;
```

### 4.2 keyword

`doc_chunks` 增加 `text_search tsvector` 生成列 + GIN 索引：

```sql
WHERE text_search @@ plainto_tsquery(:query)
ORDER BY ts_rank(text_search, plainto_tsquery(:query)) DESC
LIMIT :top_k;
```

> 中文需 `zhparser` 或 `pg_jieba`；否则退化为 `pg_trgm` 相似度。

### 4.3 hybrid（RRF 融合）

```
vector_hits  = vector(top_k)
keyword_hits = keyword(top_k)

score(chunk) = Σ 1 / (k + rank_i(chunk)),  k = 60
fused = 按融合分排序 → 截断 top_k
```

> **现状修正**：当前实现 `search_type in ("vector", "hybrid")` 走同一分支，`hybrid` 实际等价于纯向量，需按上述修正。

### 4.4 rerank

- 输入：融合后的 `top_k` 候选
- 输出：cross-encoder 打分 → 截断 `rerank_top_k`
- 若 `rerank_enabled=false` 或重排模型不可用，则直接返回融合结果

---

## 5. 过滤策略（核心：不 join）

### 5.1 scope 降维（doc_info → document_ids）

`series_id` / `revision` / `language` / `version_policy` 全部在 `doc_info` 上：

```sql
-- 第一步：小表过滤，得到文档集合
SELECT id FROM doc_info
WHERE (:series_ids IS NULL OR series_id = ANY(:series_ids))
  AND (:revisions   IS NULL OR revision  = ANY(:revisions))
  AND (:language    IS NULL OR language  = :language);

-- 第二步：大表用 document_id 过滤（走 idx_doc_chunks_document_id）
SELECT ... FROM doc_chunks WHERE document_id = ANY(:document_ids) ...
```

- `doc_info` 仅约 127 行，第一步极快
- `doc_chunks.document_id` 已有 btree 索引
- 结果可在服务端缓存（映射变动不频繁）

> 备选：直接用 `document_id IN (SELECT id FROM doc_info WHERE ...)`，Postgres 会优化为 hashed subplan，同样不产生昂贵 join。

### 5.2 page_id（复用 page_nos，零 join）

`doc_chunks.page_nos` 已是物理页整数数组，直接用：

```sql
WHERE page_nos && ARRAY[19, 20]   -- 接口的 ["19","20"] 转 int
```

不需要访问 `doc_items`。

### 5.3 label（预留，v1 不实现）

`label` 是 **item 级**条件，语义上**不能降维到文档级**：一个文档同时包含 `text` 和 `table`，`label=table` 只应命中含表格的 chunk，不能把该文档所有 chunk 都算命中。

因此它必须停留在 **chunk 级**：

```sql
-- 第一步：拿到符合条件的 item_id（限定在 scope 内）
SELECT id FROM doc_items
WHERE label = ANY(:labels) AND document_id = ANY(:document_ids);

-- 第二步：chunk 级集合交集
SELECT ... FROM doc_chunks
WHERE linked_item_ids && :item_ids;   -- jsonb 数组重叠
```

**本版决定**：契约中**保留 `label` 字段定义**，但 v1 不实现（接口收到非空 `label` 时返回 400 或忽略并告警，见 §8）。未来实现时有两条路径：

- 方案 A：给 `linked_item_ids` 建 GIN 索引，用 `&&` 过滤
- 方案 B（推荐）：分块时把来源类型集合冗余为 `doc_chunks.item_types text[]`，直接 `item_types && ARRAY['table']`

### 5.4 heading_path

`doc_chunks.heading_path` 是 `" > "` 拼接的文本，直接匹配（等值或前缀 / ILIKE）。

> 注意：当前章节号并非结构化字段，`subtree` 精确匹配能力有限；结构化章节号列入后续优化。

---

## 6. version_policy

| 值 | 行为 | 前置条件 |
|----|------|----------|
| `latest` | 每个匹配 `series_id` 取最新 revision 的文档 | 需版本号解析，见下 |
| `exact` | 只检索 `revision IN (...)` 指定版本 | `revision` 必填 |
| `selected` | 检索指定的多个版本 | `revision` 必填 |
| `all` | 不按版本过滤 | — |

### `latest` 的实现约束（重要）

实查数据：`doc_info.publication_date`、`effective_date` **127 行全部为空**，无法按日期判断最新版本。`revision` 是**不规范字符串**：

```
SGP.23: 1.0, 1.1, 1.3, 1.5-1, 1.7, 1.8, 1.9, 1.11, ... 1.16
```

- 字典序会出错：`"1.16" < "1.3"`
- 存在带后缀的 `1.15-1`

**因此**：`latest` 必须把 `revision` 解析为**数字元组**再比较，并对 `1.15-1` 这类后缀定义明确规则。`exact` / `selected` 用 `revision IN (...)`，不受此问题影响。

> 若日后回填 `effective_date`，可改为按日期判定。

---

## 7. 性能与 HNSW 调优

`document_id = ANY(...) ORDER BY embedding_vec <=> :q LIMIT :k` 属于**带过滤的向量检索**，需注意：

- 当前 `hnsw.ef_search = 40`（默认），过滤过严会**召回不足**
- pgvector 0.8.7 支持迭代扫描：

```sql
SET LOCAL hnsw.ef_search = 100;
-- 或
SET LOCAL hnsw.iterative_scan = relaxed_order;   -- 迭代直到凑够 k 条
```

按候选规模选择策略：

| 场景 | 策略 |
|------|------|
| scope 收窄到**单文档** | 直接 `WHERE document_id = :id ORDER BY embedding_vec <=> :q`（走 btree，候选小，可能快于 HNSW） |
| scope 收窄到**少量文档**（如 < 5000 chunk） | 直接扫描这些文档的 chunk + 距离排序 |
| **无 scope / 大量文档** | HNSW + 提高 `ef_search` / `iterative_scan` |

### 其他性能修正

- **删除 `search()` 中的全表预加载**：当前先 `query_chunks()` 把 27 万行读进内存仅用于判空，向量/关键词路径都不需要，必须移除。
- 关键词检索**下推数据库**，废弃现有的内存朴素分词打分。

---

## 8. 校验规则

| 规则 | 处理 |
|------|------|
| `document_id` 与 `revision` 同时非空 | 400（互斥，避免歧义） |
| `series_id` 为空且 `version_policy=latest` | 允许跨系列，但每个系列仍只取最新版本 |
| `rerank_top_k > top_k` | 400 |
| `retrieval_type` 非法值 | 400 |
| `label` 非空（v1 未实现） | 400 并提示"暂不支持 label 过滤"，或忽略并在响应告警 |
| `options.*` | 不参与过滤与排序，仅投影 |

---

## 9. 预留与未实现

| 项 | 状态 | 说明 |
|----|------|------|
| `filters.label` | 🔒 预留 | 契约保留字段，v1 不实现；实现需 chunk 级关联或冗余 `item_types` |
| `retrieval.search_profile` | 🔒 预留 | 需 profile → 默认参数映射表 |
| `retrieval.rerank_threshold` | 🔒 预留 | 若需限制重排结果时启用 |
| `filters.heading_path` 的结构化匹配 | 🔒 预留 | 需结构化章节号（`section_id` / `section_path`） |
| 文档状态（`doc_status`） | 🔒 预留 | `doc_info` 无此列；当前只用 `version_policy` 表达版本选择 |
| `spec_id` 规范注册表 | 🔒 预留 | 当前用 `series_id` 即可，无需名称映射 |

---

## 10. 分阶段落地

| 阶段 | 内容 | 是否改表 |
|------|------|----------|
| **P0** | 修正 hybrid（真 RRF）、删除全表预加载、keyword 下推 DB、参数校验、拆分阈值语义 | 需加 `text_search` 列 + GIN |
| **P1** | scope 降维（series/revision/language → document_ids）、`page_id` 复用 `page_nos`、`heading_path` 过滤、`options` 投影、`version_policy`（exact/selected/latest 解析） | 否 |
| **P2** | chunk 冗余 `item_types`（为 `label` 铺路）、结构化章节号 | 是 |
| **P3** | `search_profile` 配置、`doc_status`、`spec_id` 注册表 | 视需求 |

---

## 附录：现有数据库结构参考

### doc_chunks（检索主体，约 27 万行）

`id, document_id, chunk_index, text, headings(jsonb), heading_path, linked_item_ids(jsonb),
page_nos(jsonb), token_count, is_rag_enabled, embedding_vec, embedder, chunk_token_limit, tokenizer`

索引：`document_id`(btree)、`is_rag_enabled`(btree)、`embedding_vec`(HNSW, cosine, m=16/ef_construction=64)

### doc_info（文档元数据，约 127 行）

`id, document_code, title, series_id, file_name, file_path, revision, language, ...`
（`publication_date` / `effective_date` 当前全为空）

### doc_items（结构化项）

`id, document_id, page_id(text), label, text, order_index, metadata, content, self_ref, ...`

### 关键环境

- pgvector `0.8.7`（支持 `hnsw.iterative_scan`）
- `hnsw.ef_search = 40`（默认）
