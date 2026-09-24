# 数据库表结构文档

## 概述

本文档描述 SmartCard Master Knowledge Base 项目的数据库表结构。项目使用 PostgreSQL 作为关系型数据库，存储 PDF 文档的结构化提取结果。

**数据库名称**: `smartcard_master_knowledge`

项目包含以下两张核心表：

| 表名              | 描述                                       |
| ---------------- | ---------------------------------------- |
| `document_info`  | 存储文档元数据、解析状态和统计信息（文档级）                  |
| `document_item`  | 存储 PDF 解析后的每个结构化项（DocItem，段落/表格/图片级）     |

两张表通过 `document_info.id` ↔ `document_item.document_id` 关联。

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

## document_info 表

存储文档的元数据、解析状态和统计信息。与 `document_item` 表通过 `id` ↔ `document_id` 关联。

### 表结构

| 字段                          | 类型        | 约束                  | 描述                                                              |
| --------------------------- | --------- | ------------------- | --------------------------------------------------------------- |
| `id`                        | TEXT      | PRIMARY KEY         | 文档唯一 ID（UUID / ULID / NanoID）                                      |
| `document_code`             | TEXT      | 可空                  | 文档编号 / 标准编号，例如 `SGP-001`、`IEC-1234`                              |
| `title`                     | TEXT      | 可空                  | 文档标题，例如 `Safety Requirements for ...`                           |
| `series_id`                 | TEXT      | 可空                  | 文档系列 ID，用于关联同一标准的不同 revision                                   |
| `file_name`                 | TEXT      | NOT NULL            | 原始文件名，例如 `SGP-001-Rev-A.pdf`                                     |
| `file_path`                 | TEXT      | 可空                  | 原始文件路径（本地路径、对象存储路径等）                                        |
| `file_hash`                 | TEXT      | 可空                  | 文件 SHA256，用于判断文件是否发生变化、去重                                      |
| `file_size`                 | INTEGER   | 可空                  | 文件大小，单位：Byte                                                  |
| `file_format`               | TEXT      | 可空                  | 文件格式，例如 `pdf`、`docx`、`html`                                    |
| `page_count`                | INTEGER   | 可空                  | 页面数量                                                            |
| `revision`                  | TEXT      | 可空                  | 修订版本，例如 `A`、`B`、`C`、`Rev.1`                                 |
| `publication_date`          | TEXT      | 可空                  | 发布日期（ISO 8601 格式：`YYYY-MM-DD`）                                 |
| `effective_date`            | TEXT      | 可空                  | 生效日期                                                             |
| `issuer`                    | TEXT      | 可空                  | 发布机构 / 标准组织，例如 `GSMA`、`ISO`、`IEC`                            |
| `language`                  | TEXT      | 可空                  | 文档语言，例如 `en`、`zh-CN`、`zh-TW`                                  |
| `source_type`               | TEXT      | 可空                  | 文档来源类型，例如 `upload`、`url`、`api`、`scanner`、`manual`              |
| `parser`                    | TEXT      | 可空                  | 使用的解析器，例如 `docling`                                         |
| `parser_version`            | TEXT      | 可空                  | 解析器版本，例如 `2.50.0`                                           |
| `processing_status`         | TEXT      | 可空                  | 当前处理状态：`pending`、`processing`、`completed`、`failed`                 |
| `processing_started_at`     | TEXT      | 可空                  | 开始处理时间                                                          |
| `processing_finished_at`    | TEXT      | 可空                  | 处理完成时间                                                          |
| `processing_error`          | TEXT      | 可空                  | 解析失败时保存的错误信息                                                 |
| `item_count`                | INTEGER   | DEFAULT 0           | DocItem 总数量（缓存数据）                                               |
| `text_count`                | INTEGER   | DEFAULT 0           | 普通文本数量（缓存数据）                                                 |
| `title_count`               | INTEGER   | DEFAULT 0           | 标题数量（缓存数据）                                                    |
| `table_count`               | INTEGER   | DEFAULT 0           | 表格数量（缓存数据）                                                    |
| `picture_count`             | INTEGER   | DEFAULT 0           | 图片数量（缓存数据）                                                    |
| `formula_count`             | INTEGER   | DEFAULT 0           | 公式数量（缓存数据）                                                    |
| `metadata`                  | TEXT/JSON | 可空                  | 扩展元数据（JSON 格式）                                               |
| `created_at`                | TEXT      | DEFAULT CURRENT_TIMESTAMP | 数据创建时间                                                          |
| `updated_at`                | TEXT      | DEFAULT CURRENT_TIMESTAMP | 数据最后更新时间                                                        |

### 索引

| 索引名称                                    | 字段                  | 类型   |
| --------------------------------------- | ------------------- | ---- |
| `idx_document_info_document_code`       | `document_code`     | 普通索引 |
| `idx_document_info_series_id`           | `series_id`         | 普通索引 |
| `idx_document_info_processing_status`   | `processing_status` | 普通索引 |
| `idx_document_info_file_hash`           | `file_hash`         | 普通索引 |

### processing_status 字段可选值

| 值              | 描述    |
| -------------- | ------ |
| `pending`      | 等待处理  |
| `processing`   | 正在处理  |
| `completed`    | 处理完成  |
| `failed`       | 处理失败  |

### source_type 字段可选值

| 值          | 描述    |
| ---------- | ------ |
| `upload`   | 用户上传  |
| `url`      | URL 下载 |
| `api`      | API 同步 |
| `scanner`  | 扫描导入  |
| `manual`   | 手动录入  |

### JSON 字段示例

#### metadata（扩展元数据）

```json
{
  "author": "John Doe",
  "department": "Security Engineering",
  "source_url": "https://example.com/standards/SGP-001.pdf",
  "document_type": "standard",
  "keywords": ["eSIM", "Remote Provisioning", "Security"]
}
```

---

## DDL（数据定义语言）

### 建表语句

#### document_item 表

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

#### document_info 表

```sql
CREATE TABLE IF NOT EXISTS document_info (
    id TEXT PRIMARY KEY,
    document_code TEXT,
    title TEXT,
    series_id TEXT,
    file_name TEXT NOT NULL,
    file_path TEXT,
    file_hash TEXT,
    file_size INTEGER,
    file_format TEXT,
    page_count INTEGER,
    revision TEXT,
    publication_date TEXT,
    effective_date TEXT,
    issuer TEXT,
    language TEXT,
    source_type TEXT,
    parser TEXT,
    parser_version TEXT,
    processing_status TEXT,
    processing_started_at TEXT,
    processing_finished_at TEXT,
    processing_error TEXT,
    item_count INTEGER DEFAULT 0,
    text_count INTEGER DEFAULT 0,
    title_count INTEGER DEFAULT 0,
    table_count INTEGER DEFAULT 0,
    picture_count INTEGER DEFAULT 0,
    formula_count INTEGER DEFAULT 0,
    metadata TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 索引创建语句

#### document_item 表索引

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

#### document_info 表索引

```sql
-- 按文档编号查询索引
CREATE INDEX IF NOT EXISTS idx_document_info_document_code 
ON document_info(document_code);

-- 按系列 ID 查询索引
CREATE INDEX IF NOT EXISTS idx_document_info_series_id 
ON document_info(series_id);

-- 按处理状态查询索引
CREATE INDEX IF NOT EXISTS idx_document_info_processing_status 
ON document_info(processing_status);

-- 按文件哈希查询索引（用于去重）
CREATE INDEX IF NOT EXISTS idx_document_info_file_hash 
ON document_info(file_hash);
```

---

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
