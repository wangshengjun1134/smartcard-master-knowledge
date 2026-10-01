"""下载 BGE-Reranker 模型缺失的 Git LFS 文件"""

import os
import sys

MODEL_PATH = r"D:\softdata\workspaces\ai-models\bge-reranker-v2-m3"

# 需要下载的文件列表（使用镜像源）
MIRROR_BASE = "https://hf-mirror.com"
FILES_TO_DOWNLOAD = {
    "tokenizer.json": f"{MIRROR_BASE}/BAAI/bge-reranker-v2-m3/resolve/main/tokenizer.json",
    "sentencepiece.bpe.model": f"{MIRROR_BASE}/BAAI/bge-reranker-v2-m3/resolve/main/sentencepiece.bpe.model",
}


def check_lfs_files():
    """检查哪些文件是 LFS 指针"""
    missing = []
    for filename in FILES_TO_DOWNLOAD:
        filepath = os.path.join(MODEL_PATH, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read(100)
                if 'git-lfs' in content:
                    missing.append(filename)
        else:
            missing.append(filename)
    return missing


def download_file(url: str, save_path: str):
    """下载文件"""
    import urllib.request
    
    print(f"正在下载: {url}")
    print(f"保存到: {save_path}")
    
    try:
        urllib.request.urlretrieve(url, save_path)
        print(f"✓ 下载完成: {save_path}")
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        return False
    return True


def main():
    print("=" * 60)
    print("BGE-Reranker 模型 LFS 文件下载工具")
    print("=" * 60)
    print(f"\n模型路径: {MODEL_PATH}\n")
    
    missing = check_lfs_files()
    
    if not missing:
        print("✓ 所有文件已完整，无需下载")
        return
    
    print(f"发现 {len(missing)} 个缺失的文件:")
    for f in missing:
        print(f"  - {f}")
    print()
    
    # 尝试下载
    success_count = 0
    for filename in missing:
        url = FILES_TO_DOWNLOAD[filename]
        save_path = os.path.join(MODEL_PATH, filename)
        
        if download_file(url, save_path):
            success_count += 1
    
    print(f"\n下载完成: {success_count}/{len(missing)} 个文件成功")
    
    if success_count == len(missing):
        print("\n✓ 所有文件已下载，现在可以正常使用重排功能了！")
    else:
        print("\n✗ 部分文件下载失败，请检查网络连接后重试")
        print("\n备选方案:")
        print("1. 使用镜像源: set HF_ENDPOINT=https://hf-mirror.com")
        print("2. 手动下载后放入模型目录")


if __name__ == "__main__":
    main()
