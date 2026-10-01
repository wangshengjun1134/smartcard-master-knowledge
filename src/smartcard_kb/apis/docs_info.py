"""文档信息 API 接口"""

from typing import Optional, List
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field

from smartcard_kb.docs_compile.database import (
    insert_document_info,
    query_document_info,
    update_document_info_stats,
    delete_document_info,
    get_document_stats,
    query_chunks,
)

router = APIRouter(prefix="/api/docs", tags=["文档管理"])


# ==================== Pydantic 模型 ====================


class DocumentInfoCreate(BaseModel):
    """创建文档信息请求"""
    document_code: Optional[str] = None
    title: Optional[str] = None
    series_id: Optional[str] = None
    file_name: str
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    file_format: Optional[str] = "pdf"
    page_count: Optional[int] = None
    revision: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    issuer: Optional[str] = None
    language: Optional[str] = None
    source_type: Optional[str] = "upload"
    parser: Optional[str] = "docling"
    parser_version: Optional[str] = None
    metadata: Optional[dict] = None


class DocumentInfoUpdate(BaseModel):
    """更新文档信息请求"""
    document_code: Optional[str] = None
    title: Optional[str] = None
    series_id: Optional[str] = None
    revision: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    issuer: Optional[str] = None
    language: Optional[str] = None
    metadata: Optional[dict] = None


class DocumentInfoResponse(BaseModel):
    """文档信息响应"""
    id: str
    document_code: Optional[str] = None
    title: Optional[str] = None
    series_id: Optional[str] = None
    file_name: str
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    file_format: Optional[str] = None
    page_count: Optional[int] = None
    revision: Optional[str] = None
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    issuer: Optional[str] = None
    language: Optional[str] = None
    source_type: Optional[str] = None
    parser: Optional[str] = None
    parser_version: Optional[str] = None
    processing_status: Optional[str] = None
    processing_started_at: Optional[str] = None
    processing_finished_at: Optional[str] = None
    processing_error: Optional[str] = None
    item_count: int = 0
    text_count: int = 0
    title_count: int = 0
    table_count: int = 0
    picture_count: int = 0
    formula_count: int = 0
    metadata: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class ApiResponse(BaseModel):
    """通用 API 响应"""
    success: bool
    message: str
    data: Optional[dict] = None


class PaginatedResponse(BaseModel):
    """分页响应"""
    items: List[DocumentInfoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ChunkInfoResponse(BaseModel):
    """Chunk 信息响应"""
    id: str
    document_id: str
    chunk_index: int
    text: str
    headings: Optional[list] = None
    heading_path: Optional[str] = None
    linked_item_ids: Optional[list] = None
    page_nos: Optional[list] = None
    token_count: Optional[int] = None
    is_rag_enabled: bool = True
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class PaginatedChunksResponse(BaseModel):
    """Chunk 分页响应"""
    items: List[ChunkInfoResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ==================== API 接口 ====================


@router.get("", response_model=PaginatedResponse)
def list_documents(
    document_code: Optional[str] = None,
    series_id: Optional[str] = None,
    processing_status: Optional[str] = None,
    file_hash: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """
    获取文档列表（支持分页）

    - **document_code**: 文档编号（可选）
    - **series_id**: 系列 ID（可选）
    - **processing_status**: 处理状态（可选）
    - **file_hash**: 文件哈希（可选）
    - **page**: 页码（默认 1）
    - **page_size**: 每页数量（默认 20，最大 100）
    """
    all_docs = query_document_info(
        document_code=document_code,
        series_id=series_id,
        processing_status=processing_status,
        file_hash=file_hash,
    )

    total = len(all_docs)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    start = (page - 1) * page_size
    end = start + page_size
    items = all_docs[start:end]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/tree")
def get_document_tree():
    """
    获取文档树（基于 specs 目录结构，显示所有目录包括空目录）
    """
    import os
    from pathlib import Path

    # 使用项目根目录的 specs 路径
    # __file__ = src/smartcard_kb/apis/docs_info.py
    # .parent = src/smartcard_kb/apis
    # .parent.parent = src/smartcard_kb
    # .parent.parent.parent = project_root (smartcard-master-knowledge)
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent.parent
    specs_dir = project_root / "specs"
    
    if not specs_dir.exists():
        return {"tree": [], "stats": {"directories": 0, "files": 0}}

    # 获取数据库中的文档信息
    all_docs = query_document_info()
    doc_map = {doc.get("file_name"): doc for doc in all_docs}

    # 扫描目录结构（包括空目录）
    def scan_directory(dir_path: Path, relative_path: str = "") -> dict:
        """递归扫描目录，返回树形结构"""
        node = {
            "id": relative_path if relative_path else "root",
            "label": dir_path.name if relative_path else "specs",
            "type": "directory",
            "path": relative_path,
            "children": [],
        }

        # 获取目录下的所有条目
        try:
            entries = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            return node

        for entry in entries:
            entry_relative = f"{relative_path}/{entry.name}" if relative_path else entry.name

            if entry.is_dir():
                # 递归扫描子目录
                child_node = scan_directory(entry, entry_relative)
                node["children"].append(child_node)
            elif entry.is_file() and entry.suffix.lower() == '.pdf':
                # 添加 PDF 文件节点
                file_name = entry.name
                doc_info = doc_map.get(file_name)
                file_node = {
                    "id": entry_relative,
                    "label": file_name,
                    "type": "file",
                    "path": entry_relative,
                    "document": doc_info,
                }
                node["children"].append(file_node)

        # 统计文件数量
        def count_files(n):
            if n["type"] == "file":
                return 1
            return sum(count_files(c) for c in n.get("children", []))

        node["count"] = count_files(node)

        return node

    tree = scan_directory(specs_dir)

    # 移除空子目录（可选：保持树结构简洁）
    def remove_empty_dirs(node):
        if node["type"] == "directory":
            node["children"] = [remove_empty_dirs(c) for c in node["children"]]
            # 如果目录为空且没有子目录，可以考虑移除（但这里保留以显示结构）
        return node

    tree = remove_empty_dirs(tree)

    # 统计信息
    def count_all(node):
        dirs = 1 if node["type"] == "directory" else 0
        files = 1 if node["type"] == "file" else 0
        for child in node.get("children", []):
            d, f = count_all(child)
            dirs += d
            files += f
        return dirs, files

    total_dirs, total_files = count_all(tree)

    return {
        "tree": tree,
        "stats": {
            "directories": total_dirs,
            "files": total_files,
        },
    }


@router.get("/{document_id}", response_model=DocumentInfoResponse)
def get_document(document_id: str):
    """获取单个文档信息"""
    docs = query_document_info(document_id=document_id)
    if not docs:
        raise HTTPException(status_code=404, detail="文档不存在")
    return docs[0]


@router.post("", response_model=DocumentInfoResponse)
def create_document(doc: DocumentInfoCreate):
    """
    创建文档信息

    注意：实际文件上传和解析请使用 `/upload` 接口
    """
    import uuid

    doc_id = str(uuid.uuid4())
    doc_data = doc.model_dump()
    doc_data["id"] = doc_id
    doc_data["processing_status"] = "pending"

    insert_document_info(doc_data)

    docs = query_document_info(document_id=doc_id)
    return docs[0]


@router.put("/{document_id}", response_model=DocumentInfoResponse)
def update_document(document_id: str, doc: DocumentInfoUpdate):
    """更新文档信息"""
    # 先查询是否存在
    existing = query_document_info(document_id=document_id)
    if not existing:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 更新数据
    update_data = doc.model_dump(exclude_unset=True)
    update_data["id"] = document_id

    insert_document_info(update_data)

    docs = query_document_info(document_id=document_id)
    return docs[0]


@router.delete("/{document_id}", response_model=ApiResponse)
def delete_document(document_id: str):
    """删除文档及其关联的所有 item"""
    existing = query_document_info(document_id=document_id)
    if not existing:
        raise HTTPException(status_code=404, detail="文档不存在")

    deleted = delete_document_info(document_id)
    if deleted == 0:
        raise HTTPException(status_code=500, detail="删除失败")

    return ApiResponse(success=True, message=f"已删除文档 {document_id}")


@router.post("/upload", response_model=DocumentInfoResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_code: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    series_id: Optional[str] = Form(None),
    issuer: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
):
    """
    上传 PDF 文件并保存文档信息

    - **file**: PDF 文件
    - **document_code**: 文档编号（可选）
    - **title**: 文档标题（可选）
    - **series_id**: 系列 ID（可选）
    - **issuer**: 发布机构（可选）
    - **language**: 语言（默认 en）
    """
    import uuid
    import hashlib

    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")

    # 读取文件
    file_content = await file.read()
    file_size = len(file_content)

    # 计算文件哈希
    file_hash = hashlib.sha256(file_content).hexdigest()

    # 检查是否已存在相同文件
    existing = query_document_info(file_hash=file_hash)
    if existing:
        return existing[0]

    # 保存文件
    specs_dir = Path("specs")
    specs_dir.mkdir(parents=True, exist_ok=True)
    file_path = specs_dir / file.filename
    file_path.write_bytes(file_content)

    # 生成文档 ID
    doc_id = str(uuid.uuid4())

    # 创建文档信息
    doc_data = {
        "id": doc_id,
        "document_code": document_code,
        "title": title,
        "series_id": series_id,
        "file_name": file.filename,
        "file_path": str(file_path),
        "file_hash": file_hash,
        "file_size": file_size,
        "file_format": "pdf",
        "issuer": issuer,
        "language": language,
        "source_type": "upload",
        "parser": "docling",
        "processing_status": "uploaded",
        "processing_started_at": datetime.now().isoformat(),
    }

    insert_document_info(doc_data)

    # 返回文档信息
    docs = query_document_info(document_id=doc_id)
    return docs[0]


@router.get("/{document_id}/stats")
def get_document_statistics(document_id: str):
    """获取文档统计信息"""
    docs = query_document_info(document_id=document_id)
    if not docs:
        raise HTTPException(status_code=404, detail="文档不存在")

    stats = get_document_stats(document_id)
    return {
        "document_id": document_id,
        "item_counts_by_type": stats,
        "total_items": sum(stats.values()),
    }


@router.get("/{document_id}/chunks", response_model=PaginatedChunksResponse)
def list_document_chunks(
    document_id: str,
    is_rag_enabled: Optional[bool] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取文档的 Chunk 列表（支持分页）"""
    # 检查文档是否存在
    docs = query_document_info(document_id=document_id)
    if not docs:
        raise HTTPException(status_code=404, detail="文档不存在")

    all_chunks = query_chunks(
        document_id=document_id,
        is_rag_enabled=is_rag_enabled,
        order_by="chunk_index",
    )

    total = len(all_chunks)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    start = (page - 1) * page_size
    end = start + page_size
    items = all_chunks[start:end]

    return PaginatedChunksResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
