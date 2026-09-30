# 重排模型下载说明

## 问题

`bge-reranker-v2-m3` 模型的 `tokenizer.json` 和 `sentencepiece.bpe.model` 文件是 Git LFS 指针文件，需要下载实际文件才能使用重排功能。

## 解决方案

### 方法 1：使用 HuggingFace CLI（推荐）

```bash
# 设置国内镜像（如果在国外可省略）
set HF_ENDPOINT=https://hf-mirror.com

# 下载模型
hf download BAAI/bge-reranker-v2-m3 --local-dir "D:\softdata\workspaces\ai-models\bge-reranker-v2-m3"
```

### 方法 2：使用 Git LFS

```bash
cd "D:\softdata\workspaces\ai-models\bge-reranker-v2-m3"
git lfs pull
```

### 方法 3：手动下载

1. 访问 https://huggingface.co/BAAI/bge-reranker-v2-m3
2. 下载以下文件：
   - `tokenizer.json` (17MB)
   - `sentencepiece.bpe.model` (5MB)
3. 替换 `D:\softdata\workspaces\ai-models\bge-reranker-v2-m3` 目录中的对应文件

## 验证

下载完成后，运行以下命令验证：

```bash
python tests/test_search_direct.py
```

如果看到 "SearchService 初始化成功"，说明模型加载成功。

## 注意

- 如果网络不通，系统会自动降级为纯向量检索（不使用重排）
- 重排功能仅在使用 `enable_rerank=true` 时才会生效
