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
│       └── database.py     # 数据库 (SQLite)
├── tests/              # 测试代码
├── pyproject.toml      # 项目配置
└── README.md           # 项目说明
```

## 快速开始

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

```bash
# 启动 FastAPI 服务
uvicorn smartcard_kb.app:app --reload --host 0.0.0.0 --port 8000
```

服务启动后访问:
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 运行测试

```bash
pytest
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

## License

MIT
