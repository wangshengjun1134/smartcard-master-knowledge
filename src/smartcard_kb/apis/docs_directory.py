"""目录管理 API"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from smartcard_kb.logger import logger
from smartcard_kb.docs_compile.database import (
    query_directory_tree,
    query_all_directories,
    create_directory,
    update_directory,
    delete_directory,
    query_directory_by_id,
)

router = APIRouter(prefix="/api/directory", tags=["directory"])


class DirectoryCreate(BaseModel):
    parent_id: int = 0
    name: str
    description: str = ""


class DirectoryUpdate(BaseModel):
    parent_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None


class DirectoryNode(BaseModel):
    id: int
    parent_id: int
    name: str
    path: str
    level: int
    sort_order: int
    description: Optional[str] = None
    children: List["DirectoryNode"] = []


@router.get("/tree")
def get_directory_tree():
    """
    获取完整目录树（递归构建）
    """
    all_dirs = query_all_directories()
    if not all_dirs:
        return []

    # 构建 id -> node 映射
    node_map = {}
    for d in all_dirs:
        node_map[d["id"]] = {
            "id": d["id"],
            "parent_id": d["parent_id"],
            "name": d["name"],
            "path": d["path"],
            "level": d["level"],
            "sort_order": d["sort_order"],
            "description": d.get("description", ""),
            "children": [],
        }

    # 构建树：将子节点挂到父节点下
    roots = []
    for node in node_map.values():
        pid = node["parent_id"]
        if pid == 0 or pid not in node_map:
            roots.append(node)
        else:
            node_map[pid]["children"].append(node)

    # 按 sort_order 排序 children
    def sort_children(nodes):
        nodes.sort(key=lambda n: (n["sort_order"], n["id"]))
        for n in nodes:
            sort_children(n["children"])

    sort_children(roots)
    return roots


@router.get("")
def list_directories(parent_id: int = 0):
    """
    列出指定父目录下的直接子目录
    """
    return query_directory_tree(parent_id)


@router.post("")
def add_directory(req: DirectoryCreate):
    """
    新增目录
    """
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="目录名称不能为空")

    # 检查父目录是否存在（parent_id > 0 时）
    if req.parent_id > 0:
        parent = query_directory_by_id(req.parent_id)
        if not parent:
            raise HTTPException(status_code=400, detail=f"父目录 {req.parent_id} 不存在")
        parent_path = parent["path"]
        level = parent["level"] + 1
    else:
        parent_path = ""
        level = 1

    # 先创建获取 id，再更新 path
    new_dir = create_directory(
        parent_id=req.parent_id,
        name=req.name.strip(),
        path="__pending__",
        level=level,
        description=req.description,
    )

    # 构建物化路径
    mat_path = f"{parent_path}{new_dir['id']}/"
    update_directory(new_dir["id"], {"path": mat_path})

    logger.info(f"Created directory: {req.name} (id={new_dir['id']}, path={mat_path})")
    return query_directory_by_id(new_dir["id"])


@router.put("/{directory_id}")
def modify_directory(directory_id: int, req: DirectoryUpdate):
    """
    修改目录
    """
    existing = query_directory_by_id(directory_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"目录 {directory_id} 不存在")

    updates = {}
    if req.name is not None:
        if not req.name.strip():
            raise HTTPException(status_code=400, detail="目录名称不能为空")
        updates["name"] = req.name.strip()
    if req.parent_id is not None:
        updates["parent_id"] = req.parent_id
    if req.description is not None:
        updates["description"] = req.description
    if req.sort_order is not None:
        updates["sort_order"] = req.sort_order

    if not updates:
        return existing

    result = update_directory(directory_id, updates)
    logger.info(f"Updated directory {directory_id}: {updates}")
    return result


@router.delete("/{directory_id}")
def remove_directory(directory_id: int):
    """
    软删除目录（同时删除所有子目录）
    """
    existing = query_directory_by_id(directory_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"目录 {directory_id} 不存在")

    success = delete_directory(directory_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    logger.info(f"Deleted directory {directory_id}: {existing['name']}")
    return {"success": True, "message": f"已删除目录: {existing['name']}"}
