#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eSIM规范PDF批量下载脚本
从CSV文件中读取URL，并发下载所有有效的PDF/DOCX/ZIP文件
"""

import csv
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# 配置
CSV_FILE = r"C:\Users\DELL\WorkBuddy\智能卡\standards\手动下载eSIM规范\GSMA_eSIM规范清单.csv"
DOWNLOAD_DIR = r"C:\Users\DELL\WorkBuddy\智能卡\standards\手动下载eSIM规范"
MAX_WORKERS = 10  # 并发下载线程数
TIMEOUT = 60  # 超时时间（秒）
RETRY_COUNT = 3  # 重试次数


def create_session():
    """创建带有重试机制的requests session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=RETRY_COUNT,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    return session


def extract_urls_from_field(field_value):
    """从CSV字段中提取所有URL（支持多URL，用换行或逗号分隔）"""
    if not field_value or not isinstance(field_value, str):
        return []
    
    # 清理字段值：去除引号、空白等
    field_value = field_value.strip().strip('"').strip("'")
    
    # 使用正则表达式提取所有URL
    url_pattern = re.compile(r'https?://[^\s"\']+')
    urls = url_pattern.findall(field_value)
    
    return urls


def is_valid_download_url(url):
    """检查URL是否为有效的下载链接（PDF/DOCX/ZIP等文件）"""
    if not url:
        return False
    
    # 支持的扩展名
    valid_extensions = ['.pdf', '.docx', '.zip', '.asn1']
    
    parsed = urlparse(url)
    path = parsed.path.lower()
    
    # 检查是否为GSMA官方域名
    if 'gsma.com' not in parsed.netloc:
        return False
    
    # 检查文件扩展名
    for ext in valid_extensions:
        if path.endswith(ext):
            return True
    
    return False


def get_filename_from_url(url):
    """从URL中提取文件名"""
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    
    # 清理文件名
    filename = filename.strip()
    if not filename:
        return None
    
    return filename


def check_file_exists(filename):
    """检查文件是否已下载"""
    if not filename:
        return False
    
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    return os.path.exists(filepath)


def download_file(session, url, skip_existing=True):
    """下载单个文件"""
    try:
        filename = get_filename_from_url(url)
        if not filename:
            return False, url, "无法提取文件名"
        
        # 检查是否已存在
        if skip_existing and check_file_exists(filename):
            return True, url, f"已存在，跳过: {filename}"
        
        # 检查URL是否有效
        if not is_valid_download_url(url):
            return False, url, "无效的下载URL"
        
        # 发送HEAD请求检查文件
        head_response = session.head(url, timeout=TIMEOUT, allow_redirects=True)
        if head_response.status_code != 200:
            # 尝试GET请求
            response = session.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
            if response.status_code != 200:
                return False, url, f"HTTP {response.status_code}"
            
            # 下载文件
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(filepath)
            size_mb = file_size / (1024 * 1024)
            return True, url, f"下载成功: {filename} ({size_mb:.2f} MB)"
        
        # HEAD请求成功，下载文件
        response = session.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
        if response.status_code == 200:
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(filepath)
            size_mb = file_size / (1024 * 1024)
            return True, url, f"下载成功: {filename} ({size_mb:.2f} MB)"
        else:
            return False, url, f"HTTP {response.status_code}"
    
    except requests.exceptions.Timeout:
        return False, url, "下载超时"
    except requests.exceptions.ConnectionError as e:
        return False, url, f"连接错误: {str(e)[:50]}"
    except Exception as e:
        return False, url, f"错误: {str(e)[:50]}"


def read_csv_and_extract_urls(csv_file):
    """读取CSV文件，提取所有下载URL"""
    urls_to_download = []
    
    print(f"正在读取CSV文件: {csv_file}")
    
    try:
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, start=2):
                spec_name = row.get('Spec', '').strip()
                title = row.get('Title', '').strip()
                version = row.get('Version', '').strip()
                
                # 从DownloadUrl列提取URL
                download_url = row.get('DownloadUrl', '').strip()
                if download_url:
                    urls = extract_urls_from_field(download_url)
                    for url in urls:
                        urls_to_download.append({
                            'spec': spec_name,
                            'title': title,
                            'version': version,
                            'url': url,
                            'source': 'DownloadUrl'
                        })
                
                # 从"文件直链(解析后)"列提取URL
                direct_url = row.get('文件直链(解析后)', '').strip()
                if direct_url:
                    urls = extract_urls_from_field(direct_url)
                    for url in urls:
                        urls_to_download.append({
                            'spec': spec_name,
                            'title': title,
                            'version': version,
                            'url': url,
                            'source': '文件直链(解析后)'
                        })
    
    except FileNotFoundError:
        print(f"错误: CSV文件不存在: {csv_file}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 读取CSV文件失败: {e}")
        sys.exit(1)
    
    print(f"共提取到 {len(urls_to_download)} 个URL")
    return urls_to_download


def main():
    """主函数"""
    print("=" * 60)
    print("eSIM规范PDF批量下载工具")
    print("=" * 60)
    print(f"下载目录: {DOWNLOAD_DIR}")
    print(f"并发线程数: {MAX_WORKERS}")
    print(f"超时时间: {TIMEOUT}秒")
    print(f"重试次数: {RETRY_COUNT}")
    print("=" * 60)
    
    # 确保下载目录存在
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # 读取CSV并提取URL
    all_urls = read_csv_and_extract_urls(CSV_FILE)
    
    # 过滤有效的下载URL
    valid_urls = [item for item in all_urls if is_valid_download_url(item['url'])]
    print(f"有效下载URL: {len(valid_urls)} 个")
    
    if not valid_urls:
        print("没有找到有效的下载URL")
        return
    
    # 创建session
    session = create_session()
    
    # 并发下载
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    print("\n开始下载...")
    print("-" * 60)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {
            executor.submit(download_file, session, item['url']): item
            for item in valid_urls
        }
        
        for future in as_completed(future_to_url):
            item = future_to_url[future]
            try:
                success, url, message = future.result()
                
                if success:
                    if "跳过" in message:
                        skip_count += 1
                        print(f"[跳过] {message}")
                    else:
                        success_count += 1
                        print(f"[成功] {message}")
                else:
                    fail_count += 1
                    print(f"[失败] {item['spec']} {item['version']} - {message}")
                    print(f"       URL: {url}")
                
            except Exception as e:
                fail_count += 1
                print(f"[异常] {item['spec']} {item['version']} - {str(e)}")
    
    # 统计结果
    print("\n" + "=" * 60)
    print("下载完成!")
    print(f"成功: {success_count} 个")
    print(f"跳过: {skip_count} 个")
    print(f"失败: {fail_count} 个")
    print(f"总计: {len(valid_urls)} 个")
    print("=" * 60)


if __name__ == "__main__":
    main()
