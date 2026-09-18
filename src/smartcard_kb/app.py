"""FastAPI 应用入口"""

from fastapi import FastAPI

app = FastAPI(
    title="SmartCard Master Knowledge Base",
    description="智能卡标准规范知识库 - RAG 服务",
    version="0.1.0",
)


@app.get("/")
async def root():
    """根路径"""
    return {"message": "SmartCard Master Knowledge Base API"}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
