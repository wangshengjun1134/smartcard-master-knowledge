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
)
from smartcard_kb.docs_compile.pdf_parser import PDFParser

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
    获取文档树（基于 specs 目录结构）
    """
    import os
    from pathlib import Path

    specs_dir = Path("specs")
    if not specs_dir.exists():
        return {"tree": [], "files": []}

    # 扫描 specs 目录获取所有 PDF 文件
    pdf_files = []
    for root, dirs, files in os.walk(specs_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                full_path = Path(root) / file
                relative_path = full_path.relative_to(specs_dir)
                pdf_files.append({
                    "path": str(relative_path),
                    "name": file,
                    "directory": str(relative_path.parent) if str(relative_path.parent) != "." else "",
                })

    # 获取数据库中的文档信息
    all_docs = query_document_info()
    doc_map = {doc.get("file_name"): doc for doc in all_docs}

    # 构建树形结构
    def build_tree(files):
        tree = {}
        for file_info in files:
            parts = file_info["directory"].split("/") if file_info["directory"] else []
            current = tree
            for part in parts:
                if part not in current:
                    current[part] = {"_dirs": {}, "_files": []}
                current = current[part]["_dirs"]

            # 添加文件
            parent = tree
            for part in parts:
                parent = parent[part]["_dirs"] if part in parent else tree

            # 找到正确的父节点
            if parts:
                node = tree
                for part in parts[:-1]:
                    node = node[part]["_dirs"]
                parent_node = node[parts[-1]] if parts[-1] in node else None
                if parent_node:
                    parent_node["_files"].append(file_info)
                else:
                    # 创建新节点
                    node[parts[-1]] = {"_dirs": {}, "_files": [file_info]}
            else:
                if "_files" not in tree:
                    tree["_files"] = []
                tree["_files"].append(file_info)

        return tree

    tree = build_tree(pdf_files)

    # 转换为前端可用的格式
    def tree_to_nodes(tree_node, path=""):
        nodes = []

        # 添加目录
        dirs = tree_node.get("_dirs", {})
        for dir_name in sorted(dirs.keys()):
            dir_path = f"{path}/{dir_name}" if path else dir_name
            dir_node = dirs[dir_name]
            children = tree_to_nodes(dir_node, dir_path)
            file_count = sum(1 for c in children if c.get("type") == "file")
            nodes.append({
                "id": dir_path,
                "label": dir_name,
                "type": "directory",
                "count": file_count,
                "children": children,
            })

        # 添加文件
        files = tree_node.get("_files", [])
        for file_info in sorted(files, key=lambda x: x["name"]):
            file_name = file_info["name"]
            doc_info = doc_map.get(file_name)
            nodes.append({
                "id": file_info["path"],
                "label": file_name,
                "type": "file",
                "document": doc_info,
                "path": file_info["path"],
            })

        return nodes

    tree_nodes = tree_to_nodes(tree)

    return {
        "tree": tree_nodes,
        "files": pdf_files,
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
async def upload_and_parse_document(
    file: UploadFile = File(...),
    document_code: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    series_id: Optional[str] = Form(None),
    issuer: Optional[str] = Form(None),
    language: Optional[str] = Form("en"),
    parse_pages: Optional[str] = Form(None),
):
    """
    上传 PDF 文件并自动解析

    - **file**: PDF 文件
    - **document_code**: 文档编号（可选）
    - **title**: 文档标题（可选）
    - **series_id**: 系列 ID（可选）
    - **issuer**: 发布机构（可选）
    - **language**: 语言（默认 en）
    - **parse_pages**: 解析页码范围，如 "1-10"（可选，默认全部）
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
        "processing_status": "processing",
        "processing_started_at": datetime.now().isoformat(),
    }

    insert_document_info(doc_data)

    # 解析 PDF
    try:
        # 解析页码范围
        page_range = None
        if parse_pages:
            parts = parse_pages.split("-")
            if len(parts) == 2:
                page_range = (int(parts[0]), int(parts[1]))

        parser = PDFParser(do_ocr=True)
        items = parser.parse_pdf(
            pdf_path=str(file_path),
            document_id=doc_id,
            page_range=page_range,
            output_dir="output/pictures"
        )

        # 更新统计信息
        stats = get_document_stats(doc_id)
        type_counts = {
            "item_count": len(items),
            "text_count": stats.get("text", 0),
            "title_count": stats.get("section_header", 0),
            "table_count": stats.get("table", 0),
            "picture_count": stats.get("picture", 0),
            "formula_count": stats.get("formula", 0),
        }
        update_document_info_stats(doc_id, type_counts)

        # 更新文档信息
        doc_data["page_count"] = len(set(i["page_id"] for i in items))
        doc_data["processing_status"] = "completed"
        doc_data["processing_finished_at"] = datetime.now().isoformat()
        insert_document_info(doc_data)

    except Exception as e:
        # 更新错误状态
        doc_data["processing_status"] = "failed"
        doc_data["processing_error"] = str(e)
        doc_data["processing_finished_at"] = datetime.now().isoformat()
        insert_document_info(doc_data)
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

    # 返回更新后的文档信息
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
