"""文档 Item API 接口"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel

from smartcard_kb.docs_compile.database import (
    query_document_items,
    update_item_textualization,
    query_items_needing_textualization,
)
from smartcard_kb.docs_compile.textualize import (
    textualize_item,
    textualize_all_items,
    create_vlm_backend,
)

router = APIRouter(prefix="/api/docs", tags=["文档 Item 管理"])


# ==================== Pydantic 模型 ====================


class DocItemResponse(BaseModel):
    """文档 Item 响应"""
    id: str
    document_id: str
    page_id: str
    parent_id: Optional[str] = None
    label: str
    text: Optional[str] = None
    order_index: int
    bbox: Optional[dict] = None
    metadata: Optional[dict] = None
    content: Optional[dict] = None
    is_rag_enabled: bool = True
    textualization: Optional[str] = None
    raw_json: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class TextualizeRequest(BaseModel):
    """文本化请求"""
    document_id: Optional[str] = None
    label: Optional[str] = None
    vlm_backend_type: str = "openai"
    vlm_api_key: Optional[str] = None
    vlm_base_url: Optional[str] = None
    vlm_model: str = "qwen-vl-max"
    dry_run: bool = False


class TextualizeResponse(BaseModel):
    """文本化响应"""
    success: bool
    message: str
    stats: dict


# ==================== API 接口 ====================


@router.get("/{document_id}/items", response_model=List[DocItemResponse])
def list_document_items(
    document_id: str,
    page_id: Optional[str] = None,
    label: Optional[str] = None,
    is_rag_enabled: Optional[bool] = None,
    order_by: str = "order_index",
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """
    获取文档的 item 列表

    - **document_id**: 文档 ID
    - **page_id**: 页面 ID（可选）
    - **label**: 类型（可选）
    - **is_rag_enabled**: 是否启用 RAG（可选）
    - **order_by**: 排序字段（默认 order_index）
    - **limit**: 返回数量限制（默认 100，最大 1000）
    - **offset**: 偏移量（默认 0）
    """
    items = query_document_items(
        document_id=document_id,
        page_id=page_id,
        label=label,
        is_rag_enabled=is_rag_enabled,
        order_by=order_by,
    )

    # 分页
    return items[offset:offset + limit]


@router.get("/{document_id}/items/stats")
def get_item_statistics(document_id: str):
    """
    获取文档 item 统计信息

    - **document_id**: 文档 ID
    """
    items = query_document_items(document_id=document_id)

    # 按类型统计
    type_stats = {}
    for item in items:
        label = item.get("label", "unknown")
        type_stats[label] = type_stats.get(label, 0) + 1

    # 文本化统计
    textualized = sum(1 for i in items if i.get("textualization"))
    needs_textualization = len(items) - textualized

    return {
        "document_id": document_id,
        "total_items": len(items),
        "textualized": textualized,
        "needs_textualization": needs_textualization,
        "type_distribution": type_stats,
    }


@router.get("/{document_id}/items/needs-textualization")
def get_items_needing_textualization(
    document_id: str,
    label: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
):
    """
    获取需要文本化的 item 列表

    - **document_id**: 文档 ID
    - **label**: 类型（可选）
    - **limit**: 返回数量限制
    """
    items = query_items_needing_textualization(
        document_id=document_id,
        label=label,
        limit=limit,
    )

    return {
        "total": len(items),
        "items": items,
    }


@router.get("/{document_id}/items/{item_id}", response_model=DocItemResponse)
def get_document_item(document_id: str, item_id: str):
    """获取单个文档 item"""
    items = query_document_items(document_id=document_id)
    item = next((i for i in items if i["id"] == item_id), None)

    if not item:
        raise HTTPException(status_code=404, detail="Item 不存在")

    return item


@router.post("/{document_id}/items/textualize", response_model=TextualizeResponse)
def textualize_items(request: TextualizeRequest):
    """
    文本化文档 item

    - **document_id**: 文档 ID
    - **label**: 类型（可选，None 表示所有类型）
    - **vlm_backend_type**: VLM 后端类型（openai / local）
    - **vlm_api_key**: VLM API Key
    - **vlm_base_url**: VLM API 基础 URL
    - **vlm_model**: VLM 模型名称
    - **dry_run**: 是否只查询不更新
    """
    # 创建 VLM 后端
    vlm_backend = None
    if request.vlm_api_key:
        vlm_backend = create_vlm_backend(
            backend_type=request.vlm_backend_type,
            api_key=request.vlm_api_key,
            base_url=request.vlm_base_url,
            model=request.vlm_model,
        )

    # 执行文本化
    stats = textualize_all_items(
        document_id=request.document_id,
        label=request.label,
        vlm_backend=vlm_backend,
        dry_run=request.dry_run,
    )

    return TextualizeResponse(
        success=True,
        message=f"文本化处理完成" if not request.dry_run else "文本化预览完成",
        stats=stats,
    )


@router.post("/items/{item_id}/textualize", response_model=DocItemResponse)
def textualize_single_item(
    item_id: str,
    document_id: str = Query(...),
    vlm_backend_type: str = "openai",
    vlm_api_key: Optional[str] = None,
    vlm_base_url: Optional[str] = None,
    vlm_model: str = "qwen-vl-max",
):
    """
    文本化单个 item

    - **item_id**: Item ID
    - **document_id**: 文档 ID
    - **vlm_backend_type**: VLM 后端类型
    - **vlm_api_key**: VLM API Key
    - **vlm_base_url**: VLM API 基础 URL
    - **vlm_model**: VLM 模型名称
    """
    # 查询 item
    items = query_document_items(document_id=document_id)
    item = next((i for i in items if i["id"] == item_id), None)

    if not item:
        raise HTTPException(status_code=404, detail="Item 不存在")

    # 创建 VLM 后端
    vlm_backend = None
    if vlm_api_key:
        vlm_backend = create_vlm_backend(
            backend_type=vlm_backend_type,
            api_key=vlm_api_key,
            base_url=vlm_base_url,
            model=vlm_model,
        )

    # 文本化
    result = textualize_item(item, vlm_backend)

    if result is not None:
        update_item_textualization(item_id, result)

        # 返回更新后的 item
        items = query_document_items(document_id=document_id)
        updated_item = next((i for i in items if i["id"] == item_id), None)
        return updated_item
    else:
        raise HTTPException(status_code=500, detail="文本化失败")
