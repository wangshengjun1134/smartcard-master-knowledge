"""
MinIO 客户端 — 主存储 + specs/ 本地缓存（cache-aside 模式）

上传 → MinIO（主存储），DB 存 object_key
读取 → resolve_file(object_key) → 检查 specs/ 本地缓存
                                   ├─ 命中 → 返回本地路径
                                   └─ 未命中 → 从 MinIO 下载到 specs/ → 返回本地路径
"""

from pathlib import Path
from typing import Optional

from minio import Minio

from smartcard_kb.config import settings
from smartcard_kb.logger import logger

_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """获取 MinIO 客户端单例"""
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        # 确保 bucket 存在
        if not _client.bucket_exists(settings.minio_bucket):
            _client.make_bucket(settings.minio_bucket)
            logger.info(f"Created MinIO bucket: {settings.minio_bucket}")
    return _client


def upload_file(local_path: str, object_key: str) -> str:
    """
    上传本地文件到 MinIO

    :param local_path: 本地文件路径
    :param object_key: MinIO 对象键（如 '03-management/gsma/SGP.23/v1.16.pdf'）
    :return: object_key
    """
    client = get_minio_client()
    client.fput_object(
        settings.minio_bucket,
        object_key,
        local_path,
    )
    logger.info(f"Uploaded to MinIO: {object_key}")
    return object_key


def resolve_file(object_key: str) -> str:
    """
    解析文件路径 — cache-aside 模式

    1. 如果 object_key 是本地已存在的路径（向后兼容），直接返回
    2. 检查 specs/ 缓存目录是否已有该文件
    3. 缓存未命中 → 从 MinIO 下载到 specs/ → 返回本地路径

    :param object_key: MinIO 对象键 或 本地路径（向后兼容）
    :return: 本地文件路径（可直接用 fitz.open() 打开）
    """
    # 向后兼容：如果 object_key 是本地已存在的路径，直接返回
    local_path = Path(object_key)
    if local_path.is_absolute() and local_path.exists():
        return str(local_path)

    # 检查 specs/ 缓存
    cache_dir = Path(settings.specs_cache_dir)
    cached_path = cache_dir / object_key

    if cached_path.exists():
        logger.debug(f"Cache hit: {object_key}")
        return str(cached_path)

    # 缓存未命中 → 从 MinIO 下载
    logger.info(f"Cache miss, downloading from MinIO: {object_key}")
    client = get_minio_client()

    # 确保本地缓存目录存在
    cached_path.parent.mkdir(parents=True, exist_ok=True)

    client.fget_object(
        settings.minio_bucket,
        object_key,
        str(cached_path),
    )

    logger.info(f"Downloaded and cached: {object_key} → {cached_path}")
    return str(cached_path)
