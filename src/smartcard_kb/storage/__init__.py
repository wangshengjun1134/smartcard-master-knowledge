"""对象存储模块 — MinIO 主存储 + specs/ 本地缓存"""

from .minio_client import get_minio_client, upload_file, upload_image, resolve_file, resolve_image

__all__ = ["get_minio_client", "upload_file", "upload_image", "resolve_file", "resolve_image"]
