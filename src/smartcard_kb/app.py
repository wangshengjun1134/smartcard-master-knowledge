"""FastAPI 应用入口"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from smartcard_kb.config import settings
from smartcard_kb.docs_compile.database import init_database
from smartcard_kb.apis import docs_info_router, docs_items_router

# 设置 Docling 模型路径
if settings.docling_models_path:
    os.environ["DOCLING_MODELS_PATH"] = settings.docling_models_path

# 初始化数据库
init_database()

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


@app.get("/")
async def root():
    """根路径"""
    return {"message": "SmartCard Master Knowledge Base API"}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
