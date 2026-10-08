"""FastAPI 应用入口"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smartcard_kb.logger import logger
from smartcard_kb.config import settings, MODELS_DIR
from smartcard_kb.apis import docs_info_router, docs_items_router, docs_processing_router, search_router

# 设置 Docling 模型路径（使用相对路径，支持 Linux 和 Windows）
os.environ["DOCLING_MODELS_PATH"] = str(MODELS_DIR / "docling-models")

# 设置 HuggingFace 镜像源（解决网络不可达问题）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

app = FastAPI(
    title="SmartCard Master Knowledge Base",
    description="智能卡标准规范知识库 - RAG 服务",
    version="0.1.0",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(docs_info_router)
app.include_router(docs_items_router)
app.include_router(docs_processing_router)
app.include_router(search_router)


@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    from smartcard_kb.docs_compile.database import init_database
    try:
        init_database()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败（请检查 PostgreSQL 是否运行）: {e}")


@app.get("/")
async def root():
    """根路径"""
    return {"message": "SmartCard Master Knowledge Base API"}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
