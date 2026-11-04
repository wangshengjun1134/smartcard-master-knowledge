"""
MinIO 存储完整流程测试

测试覆盖：
1. MinIO 连接 + bucket 创建
2. upload_file() 上传本地文件到 MinIO
3. resolve_file() 缓存未命中 → 从 MinIO 下载 → 缓存到 specs/
4. resolve_file() 缓存命中 → 直接返回本地路径
5. resolve_file() 向后兼容 → 本地绝对路径直接返回
6. 端到端：上传 → 删除本地缓存 → resolve 重新下载 → 内容一致

用法：
    cd /home/buff/workspaces/smartcard/smartcard-master-knowledge
    source venv/bin/activate
    python tests/test_minio_storage.py
"""

import os
import sys
import tempfile
import hashlib
from pathlib import Path

# 确保 src 在 sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from smartcard_kb.config import settings
from smartcard_kb.storage.minio_client import get_minio_client, upload_file, resolve_file


def file_md5(path: str) -> str:
    """计算文件 MD5"""
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def test_1_minio_connection():
    """测试 1: MinIO 连接 + bucket"""
    print("\n" + "=" * 60)
    print("测试 1: MinIO 连接 + bucket 检查")
    print("=" * 60)

    client = get_minio_client()
    print(f"  Endpoint: {settings.minio_endpoint}")
    print(f"  Bucket:   {settings.minio_bucket}")

    exists = client.bucket_exists(settings.minio_bucket)
    print(f"  Bucket 存在: {exists}")
    assert exists, f"Bucket '{settings.minio_bucket}' 不存在"
    print("  ✅ 连接正常")


def test_2_upload_file():
    """测试 2: 上传本地文件到 MinIO"""
    print("\n" + "=" * 60)
    print("测试 2: upload_file() 上传到 MinIO")
    print("=" * 60)

    # 创建临时测试文件
    test_content = b"MinIO storage test content - " + os.urandom(1024).hex().encode()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(test_content)
        tmp_path = tmp.name

    try:
        object_key = "test/storage_test.txt"
        result = upload_file(tmp_path, object_key)
        print(f"  上传: {tmp_path} → {object_key}")
        assert result == object_key

        # 验证 MinIO 中文件存在
        client = get_minio_client()
        stat = client.stat_object(settings.minio_bucket, object_key)
        print(f"  MinIO 对象大小: {stat.size} bytes")
        assert stat.size == len(test_content)
        print("  ✅ 上传成功")
    finally:
        os.unlink(tmp_path)

    return object_key, test_content


def test_3_resolve_cache_miss(object_key: str, expected_content: bytes):
    """测试 3: resolve_file() 缓存未命中 → 从 MinIO 下载"""
    print("\n" + "=" * 60)
    print("测试 3: resolve_file() 缓存未命中 → 下载")
    print("=" * 60)

    # 确保缓存不存在
    cache_path = Path(settings.specs_cache_dir) / object_key
    if cache_path.exists():
        cache_path.unlink()
        print(f"  已清除缓存: {cache_path}")

    # 首次 resolve → 应从 MinIO 下载
    resolved = resolve_file(object_key)
    print(f"  resolve_file('{object_key}') → {resolved}")

    assert Path(resolved).exists(), f"解析后的文件不存在: {resolved}"
    assert resolved == str(cache_path), f"路径不匹配: {resolved} != {cache_path}"

    # 验证内容一致
    with open(resolved, "rb") as f:
        actual = f.read()
    assert actual == expected_content, "文件内容不一致"
    print(f"  内容 MD5: {hashlib.md5(actual).hexdigest()}")
    print("  ✅ 缓存未命中 → 下载成功")


def test_4_resolve_cache_hit(object_key: str, expected_content: bytes):
    """测试 4: resolve_file() 缓存命中 → 直接返回"""
    print("\n" + "=" * 60)
    print("测试 4: resolve_file() 缓存命中 → 直接返回")
    print("=" * 60)

    cache_path = Path(settings.specs_cache_dir) / object_key
    assert cache_path.exists(), "缓存文件应存在（上一步已下载）"

    # 记录缓存文件的修改时间
    mtime_before = cache_path.stat().st_mtime

    # 再次 resolve → 应命中缓存，不重新下载
    import time
    time.sleep(0.1)  # 确保如果有下载会发生 mtime 变化
    resolved = resolve_file(object_key)
    print(f"  resolve_file('{object_key}') → {resolved}")

    mtime_after = cache_path.stat().st_mtime
    assert mtime_before == mtime_after, "缓存文件被重新下载（mtime 变化）"

    # 验证内容
    with open(resolved, "rb") as f:
        actual = f.read()
    assert actual == expected_content
    print("  ✅ 缓存命中 → 未重新下载")


def test_5_backward_compat_local_path():
    """测试 5: resolve_file() 向后兼容本地绝对路径"""
    print("\n" + "=" * 60)
    print("测试 5: resolve_file() 向后兼容本地路径")
    print("=" * 60)

    # 创建本地临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", dir="/tmp") as tmp:
        tmp.write(b"local path test")
        local_path = tmp.name

    try:
        resolved = resolve_file(local_path)
        print(f"  resolve_file('{local_path}') → {resolved}")
        assert resolved == local_path, "本地路径应原样返回"
        print("  ✅ 向后兼容 → 本地路径直接返回")
    finally:
        os.unlink(local_path)


def test_6_e2e_re_download(object_key: str, expected_content: bytes):
    """测试 6: 端到端 — 删除缓存后重新下载"""
    print("\n" + "=" * 60)
    print("测试 6: 端到端 — 删缓存 → 重新下载 → 内容一致")
    print("=" * 60)

    # 删除缓存
    cache_path = Path(settings.specs_cache_dir) / object_key
    if cache_path.exists():
        cache_path.unlink()
        print(f"  已删除缓存: {cache_path}")

    # 重新 resolve → 应从 MinIO 重新下载
    resolved = resolve_file(object_key)
    print(f"  resolve_file('{object_key}') → {resolved}")

    with open(resolved, "rb") as f:
        actual = f.read()
    assert actual == expected_content, "重新下载后内容不一致"
    print(f"  内容 MD5: {hashlib.md5(actual).hexdigest()}")
    print("  ✅ 端到端验证通过")


def test_7_cleanup(object_key: str):
    """测试 7: 清理测试数据"""
    print("\n" + "=" * 60)
    print("测试 7: 清理测试数据")
    print("=" * 60)

    client = get_minio_client()

    # 删除 MinIO 对象
    try:
        client.remove_object(settings.minio_bucket, object_key)
        print(f"  已删除 MinIO 对象: {object_key}")
    except Exception as e:
        print(f"  删除 MinIO 对象失败: {e}")

    # 删除本地缓存
    cache_path = Path(settings.specs_cache_dir) / object_key
    if cache_path.exists():
        cache_path.unlink()
        print(f"  已删除本地缓存: {cache_path}")

    print("  ✅ 清理完成")


def main():
    print("MinIO 存储完整流程测试")
    print(f"MinIO: {settings.minio_endpoint}, bucket: {settings.minio_bucket}")
    print(f"本地缓存: {settings.specs_cache_dir}")

    try:
        test_1_minio_connection()
        object_key, content = test_2_upload_file()
        test_3_resolve_cache_miss(object_key, content)
        test_4_resolve_cache_hit(object_key, content)
        test_5_backward_compat_local_path()
        test_6_e2e_re_download(object_key, content)
        test_7_cleanup(object_key)

        print("\n" + "=" * 60)
        print("🎉 全部 7 个测试通过！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
