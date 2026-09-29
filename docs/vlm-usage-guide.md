# VLM 图片描述功能使用指南

## 概述

VLM（Vision Language Model）图片描述功能可以自动为 PDF 中的图片生成文字描述，使图片内容能够参与 RAG 检索。

## 功能特性

- ✅ 支持 API 方式（OpenAI 兼容接口，如 DashScope）
- ✅ 支持本地模型方式（Qwen3-VL）
- ✅ 默认不启用 VLM（需显式配置）
- ✅ 图片描述存储在 `metadata.vlm_description` 字段
- ✅ VLM 失败时自动降级（不影响解析流程）

## 配置方式

### 方式一：使用 API（推荐）

在 `.env` 文件中配置：

```bash
# VLM 配置
VLM_BACKEND_TYPE=openai
VLM_OPENAI_API_KEY=sk-your-api-key-here
VLM_OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VLM_OPENAI_MODEL=qwen-vl-max
```

### 方式二：使用本地模型

在 `.env` 文件中配置：

```bash
# VLM 配置
VLM_BACKEND_TYPE=local
VLM_LOCAL_MODEL_PATH=D:/softdata/workspaces/ai-models/Qwen3-VL-8B-Instruct
```

## 代码示例

### 示例 1：使用 API 后端

```python
import os
from src.smartcard_kb.docs_compile.pdf_parser import PDFParser

# 从环境变量读取配置
vlm_config = {
    "backend_type": os.getenv("VLM_BACKEND_TYPE", "openai"),
    "openai_api_key": os.getenv("VLM_OPENAI_API_KEY", ""),
    "openai_base_url": os.getenv("VLM_OPENAI_BASE_URL", ""),
    "openai_model": os.getenv("VLM_OPENAI_MODEL", "qwen-vl-max"),
}

# 初始化解析器（启用 VLM）
parser = PDFParser(
    do_ocr=True,
    max_tokens=512,
    tokenizer_name="BAAI/bge-m3",
    vlm_config=vlm_config,
)

# 解析 PDF
result = parser.parse_pdf(
    pdf_path="specs/example.pdf",
    document_id="example_doc",
    output_dir="output/pictures",
)

# 获取图片的 VLM 描述
items = result["items"]
for item in items:
    if item["label"] == "picture":
        metadata = item.get("metadata", {})
        vlm_desc = metadata.get("vlm_description", "未生成")
        print(f"图片描述: {vlm_desc}")
```

### 示例 2：使用本地模型

```python
from src.smartcard_kb.docs_compile.pdf_parser import PDFParser

vlm_config = {
    "backend_type": "local",
    "local_model_path": "D:/softdata/workspaces/ai-models/Qwen3-VL-8B-Instruct",
}

parser = PDFParser(
    do_ocr=True,
    vlm_config=vlm_config,
)

result = parser.parse_pdf(
    pdf_path="specs/example.pdf",
    document_id="example_doc",
)
```

### 示例 3：自定义 VLM 后端

```python
from src.smartcard_kb.docs_compile.pdf_parser import PDFParser
from src.smartcard_kb.llms.openai import OpenAICompatibleBackend

# 手动创建后端实例
backend = OpenAICompatibleBackend(
    api_key="your-api-key",
    base_url="https://your-api.com/v1",
    model="your-model",
)

parser = PDFParser(
    do_ocr=True,
    vlm_backend=backend,
)
```

### 示例 4：不启用 VLM（默认行为）

```python
from src.smartcard_kb.docs_compile.pdf_parser import PDFParser

# 不传递 vlm_config 或 vlm_backend
parser = PDFParser(
    do_ocr=True,
    max_tokens=512,
    tokenizer_name="BAAI/bge-m3",
)

# 图片只保存文件，不生成描述
result = parser.parse_pdf(
    pdf_path="specs/example.pdf",
    document_id="example_doc",
)
```

## 数据处理流程

### 图片处理流程

```
PDF 图片
  ├── 保存图片文件 → output/pictures/picture_0001.png
  ├── 提取 caption（图注）→ metadata.caption
  └── VLM 生成描述 → metadata.vlm_description
```

### 数据库存储

图片 item 的 `metadata` 字段包含：

```json
{
  "caption": "图 1-1 系统架构图",
  "vlm_description": "这是一张系统架构图，展示了...",
  "level": 2
}
```

### Chunks 中的图片处理

- 图片本身不作为文本块参与分块
- 只有 `caption` 和 `vlm_description` 会作为文本参与 RAG 检索
- 通过 `linked_item_ids` 可以回溯到原始图片

## 性能考虑

### API 方式

- 每张图片需要一次 API 调用
- 建议设置合理的超时时间（默认 120 秒）
- 注意 API 调用频率限制

### 本地模型方式

- 需要加载模型到内存（约 16GB VRAM）
- 每张图片处理时间约 2-5 秒
- 适合批量处理大量图片

## 测试验证

### 运行集成测试

```bash
python tests/test_vlm_integration.py
```

### 运行完整测试

```bash
# 仅解析前 5 页
python tests/test_vlm_description.py
```

## 注意事项

1. **VLM 失败降级**：如果 VLM 调用失败，会自动跳过，不影响其他 item 的提取
2. **图片尺寸**：默认缩放倍数为 2.0，可通过 `images_scale` 调整
3. **Token 限制**：默认最大生成 512 tokens，可通过 `max_new_tokens` 调整
4. **提示词定制**：可通过 `_generate_vlm_description` 的 `prompt` 参数定制提示词

## 常见问题

### Q: 如何禁用 VLM？

A: 不传递 `vlm_config` 或 `vlm_backend` 参数即可。

### Q: VLM 描述生成失败怎么办？

A: 检查：
1. API Key 是否正确
2. 网络连接是否正常
3. 模型是否可用
4. 查看控制台警告信息

### Q: 如何自定义提示词？

A: 修改 `_generate_vlm_description` 方法的 `prompt` 参数：

```python
description = self._generate_vlm_description(
    image=image,
    item=item,
    doc=doc,
    prompt="请用简洁的语言描述这张图片的内容。",
)
```

### Q: 本地模型加载失败？

A: 检查：
1. 模型路径是否正确
2. 是否安装了 `transformers` 和 `torch`
3. 是否有足够的显存

## 相关文件

- `src/smartcard_kb/docs_compile/pdf_parser.py` - 主解析器
- `src/smartcard_kb/llms/base.py` - VLM 后端抽象基类
- `src/smartcard_kb/llms/openai.py` - OpenAI 兼容后端
- `src/smartcard_kb/llms/local.py` - 本地模型后端
- `src/smartcard_kb/llms/config.py` - VLM 配置
- `tests/test_vlm_integration.py` - 集成测试
- `tests/test_vlm_description.py` - 完整功能测试
