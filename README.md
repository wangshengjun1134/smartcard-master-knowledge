# SmartCard Master Knowledge Base

智能卡标准规范知识库 - 涵盖从基础标准到应用规范的完整技术栈。

## 项目结构

```
smartcard-master-knowledge/
├── specs/              # 规范文档目录
├── src/                # Python 源代码
│   └── smartcard_kb/   # 主包
│       ├── app.py          # FastAPI 应用
│       ├── config.py       # 配置管理
│       ├── document.py     # 文档处理 (docling)
│       ├── vector_store.py # 向量存储 (Qdrant)
│       └── database.py     # 数据库 (PostgreSQL)
├── web/                # Next.js 前端
│   ├── app/            # 页面路由
│   ├── components/     # UI 组件
│   ├── lib/            # 工具函数和 API 客户端
│   └── types/          # TypeScript 类型定义
├── tests/              # 测试代码
├── pyproject.toml      # 项目配置
└── README.md           # 项目说明
```

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 18 (带 pgvector 扩展)

### 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 安装开发依赖
pip install -e ".[dev]"
```

### 配置环境

```bash
# 复制环境配置文件
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac

# 编辑 .env 文件，配置必要的参数
```

### 启动服务

#### 1. 启动后端服务 (FastAPI)

```bash
# 启动 FastAPI 服务 (端口 8000)
uvicorn smartcard_kb.app:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后访问:
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- 文档列表 API: http://localhost:8000/api/docs
- 文档树 API: http://localhost:8000/api/docs/tree

#### 2. 启动前端服务 (Next.js)

```bash
# 进入前端目录
cd web

# 安装依赖 (首次运行)
npm install

# 启动开发服务器 (端口 3000)
npm run dev
```

前端服务启动后访问: http://localhost:3000

### 完整启动流程

**Windows:**
```cmd
# 终端 1 - 启动后端
uvicorn smartcard_kb.app:app --host 0.0.0.0 --port 8000 --reload

# 终端 2 - 启动前端
cd web
npm run dev
```

**Linux/Mac:**
```bash
# 终端 1 - 启动后端
uvicorn smartcard_kb.app:app --host 0.0.0.0 --port 8000 --reload

# 终端 2 - 启动前端
cd web
npm run dev
```

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_pdf_parse.py
pytest tests/test_textualize.py
pytest tests/parse_and_verify.py

# 创建测试数据
python tests/create_test_data.py
```

### 代码格式化

```bash
ruff format .
ruff check . --fix
```

### 类型检查

```bash
mypy src/
```

## 开发

### 安装 pre-commit hooks

```bash
pre-commit install
```

### API 接口说明

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/docs` | 获取文档列表（支持分页） |
| GET | `/api/docs/tree` | 获取文档树（基于 specs 目录结构） |
| GET | `/api/docs/{id}` | 获取单个文档信息 |
| POST | `/api/docs` | 创建文档信息 |
| PUT | `/api/docs/{id}` | 更新文档信息 |
| DELETE | `/api/docs/{id}` | 删除文档及关联 item |
| POST | `/api/docs/upload` | 上传 PDF 并自动解析 |
| GET | `/api/docs/{id}/items` | 获取文档 item 列表 |
| GET | `/api/docs/{id}/items/stats` | 获取 item 统计信息 |
| POST | `/api/docs/{id}/items/textualize` | 批量文本化 item |

### 数据库管理

```bash
# 连接 PostgreSQL
docker exec -it postgres-pgvector psql -U postgres -d smartcard_master_knowledge

# 查看文档列表
SELECT id, document_code, title, processing_status, item_count FROM document_info;

# 查看 item 统计
SELECT label, COUNT(*) FROM document_item GROUP BY label;
```

## License

MIT
