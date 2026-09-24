# 数据库表结构文档

## 概述

本文档描述 SmartCard Master Knowledge Base 项目的数据库表结构。项目使用 SQLite 作为关系型数据库，存储 PDF 文档的结构化提取结果。

**数据库文件路径**: `data/knowledge.db`

---

## document_item 表

存储 PDF 文档解析后的每个结构化项（DocItem）。

### 表结构

| 字段               | 类型        | 约束                  | 描述                                                              |
| ---------------- | --------- | ------------------- | --------------------------------------------------------------- |
| `id`             | TEXT      | PRIMARY KEY         | DocItem 唯一 ID（UUID）                                            |
| `document_id`    | TEXT      | NOT NULL, INDEX     | 所属文档 ID                                                         |
| `page_id`        | TEXT      | NOT NULL, INDEX     | 所属 PDF 页面 ID                                                     |
| `parent_id`      | TEXT      | 可空                  | 父级 DocItem ID，用于建立文档层级关系                                        |
| `label`          | TEXT      | NOT NULL, INDEX     | Docling 的 `DocItemLabel` 类型，例如 `text`、`title`、`table`、`picture` |
| `text`           | TEXT      | 可空                  | 当前 DocItem 的主要文本内容，用于全文搜索和后续 RAG                                |
| `order_index`    | INTEGER   | NOT NULL            | 当前 DocItem 在文档中的顺序                                              |
| `bbox`           | TEXT/JSON | 可空                  | DocItem 在 PDF 页面中的边界框坐标（JSON 格式）                                  |
| `metadata`       | TEXT/JSON | 可空                  | 通用元数据，例如章节、标题层级、来源等（JSON 格式）                                    |
| `content`        | TEXT/JSON | 可空                  | 当前类型特有的结构化内容（JSON 格式）                                           |
| `is_rag_enabled` | BOOLEAN   | DEFAULT 1, INDEX    | 是否允许该 DocItem 参与 RAG（1=启用，0=禁用）                                  |
| `raw_json`       | TEXT/JSON | 可空                  | Docling 原始 DocItem 数据，便于后续重新处理（JSON 格式）                          |
| `created_at`     | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 数据创建时间                                                          |
| `updated_at`     | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 数据最后更新时间                                                        |

### 索引

| 索引名称                                    | 字段                  | 类型   |
| --------------------------------------- | ------------------- | ---- |
| `idx_document_item_document_id`         | `document_id`       | 普通索引 |
| `idx_document_item_page_id`             | `page_id`           | 普通索引 |
| `idx_document_item_label`               | `label`             | 普通索引 |
| `idx_document_item_is_rag_enabled`      | `is_rag_enabled`    | 普通索引 |

### label 字段可选值

| 值                   | 描述     |
| ------------------ | ------ |
| `text`             | 普通文本   |
| `section_header`   | 标题     |
| `table`            | 表格     |
| `picture`          | 图片     |
| `formula`          | 公式     |
| `document_index`   | 文档索引   |
| `list_item`        | 列表项    |
| `code`             | 代码     |
| `checkbox_selected` | 已选中复选框 |
| `checkbox_unselected` | 未选中复选框 |
| `caption`          | 标题说明   |
| `page_header`      | 页眉     |
| `page_footer`      | 页脚     |
| `footnote`         | 脚注     |
| `tier_1_title`     | 一级标题   |
| `tier_2_title`     | 二级标题   |
| `tier_3_title`     | 三级标题   |
| `tier_4_title`     | 四级标题   |
| `tier_5_title`     | 五级标题   |

> 注：以上为 Docling 支持的完整 DocItemLabel 类型，当前已实现提取器的类型包括：`text`、`section_header`、`table`、`picture`、`formula`、`document_index`、`list_item`。

### JSON 字段示例

#### bbox（边界框坐标）

```json
{
  "l": 72.0,
  "t": 100.5,
  "r": 540.0,
  "b": 150.3
}
```

- `l`: left（左边界）
- `t`: top（上边界）
- `r`: right（右边界）
- `b`: bottom（下边界）

#### metadata（元数据）

```json
{
  "level": 2,
  "heading_path": ["1. 概述", "1.1 系统架构"],
  "caption": "表1-1 系统组件列表"
}
```

- `level`: 标题层级（1-5）
- `heading_path`: 父级标题路径
- `caption`: 图片/表格的标题说明

#### content（类型特有内容）

**图片类型示例：**

```json
{
  "image_path": "output/pictures/picture_0001.png"
}
```

**表格类型示例：**

```json
{
  "rows": 5,
  "columns": 3,
  "has_header": true
}
```

#### raw_json（原始数据）

```json
{
  "label": "text",
  "text": "这是文档中的一段文本内容。",
  "level": 1
}
```

---

## DDL（数据定义语言）

### 建表语句

```sql
CREATE TABLE IF NOT EXISTS document_item (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    page_id TEXT NOT NULL,
    parent_id TEXT,
    label TEXT NOT NULL,
    text TEXT,
    order_index INTEGER NOT NULL,
    bbox TEXT,
    metadata TEXT,
    content TEXT,
    is_rag_enabled BOOLEAN DEFAULT FALSE,
    raw_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 索引创建语句

```sql
-- 按文档 ID 查询索引
CREATE INDEX IF NOT EXISTS idx_document_item_document_id 
ON document_item(document_id);

-- 按页面 ID 查询索引
CREATE INDEX IF NOT EXISTS idx_document_item_page_id 
ON document_item(page_id);

-- 按 DocItemLabel 类型查询索引
CREATE INDEX IF NOT EXISTS idx_document_item_label 
ON document_item(label);

-- 按 RAG 启用状态查询索引
CREATE INDEX IF NOT EXISTS idx_document_item_is_rag_enabled 
ON document_item(is_rag_enabled);
```

---

## DML（数据操作语言）

### INSERT（插入）

#### 插入单条记录

```sql
INSERT INTO document_item (
    id, document_id, page_id, parent_id, label, text,
    order_index, bbox, metadata, content, is_rag_enabled,
    raw_json, created_at, updated_at
) VALUES (
    'uuid-001', 'spec_001', 'spec_001_page_1', NULL, 'text',
    '这是一段文本内容', 1,
    '{"l": 72.0, "t": 100.5, "r": 540.0, "b": 150.3}',
    '{"level": 1, "heading_path": ["1. 概述"]}',
    NULL, 1,
    '{"label": "text", "text": "这是一段文本内容"}',
    datetime('now'), datetime('now')
);
```

#### 批量插入

```sql
INSERT INTO document_item (
    id, document_id, page_id, parent_id, label, text,
    order_index, bbox, metadata, content, is_rag_enabled,
    raw_json
) VALUES
    ('uuid-001', 'spec_001', 'spec_001_page_1', NULL, 'section_header', '1. 概述', 1, NULL, '{"level": 1}', NULL, 1, NULL),
    ('uuid-002', 'spec_001', 'spec_001_page_1', 'uuid-001', 'text', '这是第一段内容', 2, NULL, '{"level": 1}', NULL, 1, NULL),
    ('uuid-003', 'spec_001', 'spec_001_page_1', 'uuid-001', 'table', '| 列1 | 列2 |', 3, NULL, '{"level": 1}', NULL, 1, NULL);
```

#### INSERT OR REPLACE（插入或替换）

```sql
INSERT OR REPLACE INTO document_item (
    id, document_id, page_id, label, text, order_index, is_rag_enabled
) VALUES (
    'uuid-001', 'spec_001', 'spec_001_page_1', 'text',
    '更新后的文本内容', 1, 1
);
```

---

### SELECT（查询）

#### 查询指定文档的所有 item

```sql
SELECT * FROM document_item 
WHERE document_id = 'spec_001' 
ORDER BY order_index;
```

#### 查询指定文档的特定类型 item

```sql
-- 查询所有表格
SELECT * FROM document_item 
WHERE document_id = 'spec_001' AND label = 'table' 
ORDER BY order_index;

-- 查询所有标题
SELECT * FROM document_item 
WHERE document_id = 'spec_001' AND label = 'section_header' 
ORDER BY order_index;
```

#### 查询启用 RAG 的文本项

```sql
SELECT id, document_id, text, metadata 
FROM document_item 
WHERE document_id = 'spec_001' 
  AND is_rag_enabled = 1 
  AND label IN ('text', 'section_header', 'table')
ORDER BY order_index;
```

#### 查询指定页面的所有 item

```sql
SELECT * FROM document_item 
WHERE page_id = 'spec_001_page_1' 
ORDER BY order_index;
```

#### 查询带层级关系的 item

```sql
-- 查询父级标题及其子项
SELECT 
    parent.text AS parent_text,
    child.id, child.label, child.text, child.order_index
FROM document_item AS child
LEFT JOIN document_item AS parent 
    ON child.parent_id = parent.id
WHERE child.document_id = 'spec_001'
ORDER BY child.order_index;
```

#### 统计查询

```sql
-- 统计文档中各类型的 item 数量
SELECT label, COUNT(*) AS count 
FROM document_item 
WHERE document_id = 'spec_001' 
GROUP BY label;

-- 统计文档的总页数
SELECT COUNT(DISTINCT page_id) AS page_count 
FROM document_item 
WHERE document_id = 'spec_001';

-- 统计启用 RAG 的 item 数量
SELECT 
    label, 
    COUNT(*) AS count,
    SUM(is_rag_enabled) AS rag_enabled_count
FROM document_item 
WHERE document_id = 'spec_001' 
GROUP BY label;
```

#### 全文搜索

```sql
-- 使用 LIKE 进行简单全文搜索
SELECT * FROM document_item 
WHERE document_id = 'spec_001' 
  AND text IS NOT NULL
  AND text LIKE '%关键词%'
ORDER BY order_index;

-- 搜索多个关键词（OR 逻辑）
SELECT * FROM document_item 
WHERE document_id = 'spec_001' 
  AND text IS NOT NULL
  AND (text LIKE '%关键词1%' OR text LIKE '%关键词2%')
ORDER BY order_index;
```

---

### UPDATE（更新）

#### 更新 is_rag_enabled 状态

```sql
-- 禁用图片类型的 RAG
UPDATE document_item 
SET is_rag_enabled = 0, updated_at = datetime('now')
WHERE document_id = 'spec_001' AND label = 'picture';

-- 启用特定 item 的 RAG
UPDATE document_item 
SET is_rag_enabled = 1, updated_at = datetime('now')
WHERE id = 'uuid-001';
```

#### 更新 parent_id 建立层级关系

```sql
UPDATE document_item 
SET parent_id = 'uuid-parent-001', updated_at = datetime('now')
WHERE document_id = 'spec_001' 
  AND page_id = 'spec_001_page_1'
  AND order_index BETWEEN 2 AND 5;
```

#### 更新文本内容

```sql
UPDATE document_item 
SET text = '更新后的文本内容', updated_at = datetime('now')
WHERE id = 'uuid-001';
```

---

### DELETE（删除）

#### 删除指定文档的所有 item

```sql
DELETE FROM document_item 
WHERE document_id = 'spec_001';
```

#### 删除指定页面的所有 item

```sql
DELETE FROM document_item 
WHERE document_id = 'spec_001' 
  AND page_id = 'spec_001_page_1';
```

#### 删除特定类型的 item

```sql
-- 删除所有图片类型
DELETE FROM document_item 
WHERE document_id = 'spec_001' AND label = 'picture';
```

#### 删除空文本的 item

```sql
DELETE FROM document_item 
WHERE document_id = 'spec_001' 
  AND (text IS NULL OR text = '');
```

---

## 使用示例

### Python 代码示例

#### 初始化数据库

```python
from smartcard_kb.docs_compile import init_database

init_database()
```

#### 插入单条记录

```python
from smartcard_kb.docs_compile import insert_document_item

item = {
    "id": "uuid-here",
    "document_id": "spec_001",
    "page_id": "spec_001_page_1",
    "parent_id": None,
    "label": "text",
    "text": "这是一段文本内容",
    "order_index": 1,
    "bbox": {"l": 72.0, "t": 100.5, "r": 540.0, "b": 150.3},
    "metadata": {"level": 1},
    "content": None,
    "is_rag_enabled": True,
    "raw_json": {"label": "text", "text": "这是一段文本内容"},
}

insert_document_item(item)
```

#### 批量插入

```python
from smartcard_kb.docs_compile import insert_document_items

items = [item1, item2, item3]
insert_document_items(items)
```

#### 查询记录

```python
from smartcard_kb.docs_compile import query_document_items

# 查询指定文档的所有 item
items = query_document_items(document_id="spec_001")

# 查询指定文档的所有表格
tables = query_document_items(document_id="spec_001", label="table")

# 查询启用 RAG 的文本项
rag_items = query_document_items(
    document_id="spec_001",
    is_rag_enabled=True,
    label="text"
)

# 查询指定页面的所有 item
page_items = query_document_items(page_id="spec_001_page_1")
```

#### 删除记录

```python
from smartcard_kb.docs_compile import delete_document_items_by_document

count = delete_document_items_by_document(document_id="spec_001")
print(f"删除了 {count} 条记录")
```

---

## 设计说明

### 为什么所有类型都存储在同一张表？

1. **简化查询**: 按文档或页面查询时，不需要 JOIN 多张表
2. **统一索引**: 所有 item 共享相同的索引策略
3. **灵活性**: 新增 DocItemLabel 类型不需要修改表结构
4. **兼容性**: 与 Docling 的数据模型保持一致

### is_rag_enabled 字段的作用

控制哪些 DocItem 参与 RAG（检索增强生成）流程：

- **图片类型** (`picture`): 默认 `False`，因为图片本身不是文本内容
- **文本类型** (`text`, `section_header`, `table` 等): 默认 `True`
- 可根据业务需求动态调整

### parent_id 字段的使用

用于建立文档的层级关系（如章节-段落关系）：

```
document_id: spec_001
├── id: uuid-1, label: section_header, text: "1. 概述", parent_id: NULL
│   ├── id: uuid-2, label: text, text: "...", parent_id: uuid-1
│   └── id: uuid-3, label: table, text: "...", parent_id: uuid-1
└── id: uuid-4, label: section_header, text: "2. 详细设计", parent_id: NULL
    └── id: uuid-5, label: text, text: "...", parent_id: uuid-4
```

---

## 扩展计划

以下 DocItemLabel 类型的提取器尚未实现，已预留接口：

- `code` - 代码块提取器
- `checkbox_selected` / `checkbox_unselected` - 复选框提取器
- `caption` - 标题说明提取器
- `page_header` / `page_footer` - 页眉页脚提取器
- `footnote` - 脚注提取器
- `tier_1_title` ~ `tier_5_title` - 多级标题提取器

扩展方法：在 `extractors.py` 中继承 `DocItemExtractor` 基类并注册到 `extractors` 字典。
