"""批量处理所有 upload 状态的文档

处理流程：
1. Parse（解析）- 并行 5 个
2. VLM 增强（图片描述）- 串行（API 限流）
3. Chunk（分块）- 并行 5 个
4. Embedding（向量化）- 并行 5 个

特性：
- 失败记录原因并继续
- API 限流时暂停 1 小时
- 详细统计每个文档各阶段耗时
"""

import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional

# ==================== 配置 ====================

API_BASE_URL = "http://localhost:8000/api/docs"

# VLM 配置（使用后端 .env 中的配置，无需在此设置）
VLM_BACKEND_TYPE = "openai"
VLM_PROMPT = "Please describe this image in detail, including all technical details, chart data, process steps, etc. If it is a flowchart or architecture diagram, please explain the relationships between the components. Respond in English."
VLM_MAX_TOKENS = 512

# 分块配置
CHUNK_MAX_TOKENS = 512
CHUNK_TOKENIZER = "BAAI/bge-m3"

# Embedding 配置
EMBEDDING_BACKEND = "local"

# 输出目录
OUTPUT_DIR = "output/pictures"

# 并行度
MAX_WORKERS = 5

# 限流等待时间（秒）
RATE_LIMIT_WAIT = 3600  # 1 小时


class DocStats:
    """文档处理统计"""
    
    def __init__(self, doc_id: str, file_name: str):
        self.doc_id = doc_id
        self.file_name = file_name
        self.stages = {
            "parse": {"status": "pending", "time": 0, "error": None, "items": 0},
            "vlm": {"status": "pending", "time": 0, "error": None, "pictures": 0},
            "chunk": {"status": "pending", "time": 0, "error": None, "chunks": 0},
            "embedding": {"status": "pending", "time": 0, "error": None},
        }
    
    def mark_success(self, stage: str, **kwargs):
        self.stages[stage]["status"] = "success"
        self.stages[stage].update(kwargs)
    
    def mark_failed(self, stage: str, error: str):
        self.stages[stage]["status"] = "failed"
        self.stages[stage]["error"] = error
    
    def to_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "file_name": self.file_name,
            "stages": self.stages,
        }


class BatchProcessor:
    """批量文档处理器"""
    
    def __init__(self):
        self.stats: Dict[str, DocStats] = {}
        self.rate_limited = False
    
    def get_upload_documents(self) -> list:
        """获取所有 upload 状态的文档（通过 API）"""
        all_docs = []
        page = 1
        page_size = 100
        
        while True:
            response = requests.get(
                f"{API_BASE_URL}",
                params={
                    "page": page,
                    "page_size": page_size,
                    "processing_status": "embedded",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            
            items = data.get("items", [])
            if not items:
                break
            
            # 过滤出 upload 类型的文档
            upload_docs = [d for d in items if d.get("source_type") == "upload"]
            all_docs.extend(upload_docs)
            
            if page >= data.get("total_pages", 1):
                break
            page += 1
        
        return all_docs
    
    def call_api(self, url: str, data: dict, timeout: int = 300) -> Optional[dict]:
        """调用 API，处理限流"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data, timeout=timeout)
                if response.status_code == 429:  # 限流
                    print(f"  ⚠️  API 限流，等待 {RATE_LIMIT_WAIT//60} 分钟...")
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                response.raise_for_status()
                return response.json()
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"  ⚠️  请求超时，重试 {attempt + 1}/{max_retries}...")
                    time.sleep(30)
                    continue
                return None
            except requests.exceptions.ConnectionError as e:
                if "rate limit" in str(e).lower() or "429" in str(e):
                    print(f"  ⚠️  API 限流，等待 {RATE_LIMIT_WAIT//60} 分钟...")
                    time.sleep(RATE_LIMIT_WAIT)
                    continue
                raise
    
    def process_parse(self, doc: dict) -> DocStats:
        """处理解析阶段"""
        doc_id = doc["id"]
        file_name = doc["file_name"]
        file_path = doc["file_path"]
        
        stats = DocStats(doc_id, file_name)
        print(f"\n{'='*60}")
        print(f"📄 开始解析: {file_name}")
        print(f"{'='*60}")
        
        t0 = time.time()
        try:
            result = self.call_api(
                f"{API_BASE_URL}/process/parse",
                {
                    "pdf_path": file_path,
                    "document_id": doc_id,
                    "output_dir": OUTPUT_DIR,
                    "do_ocr": True,
                },
                timeout=600,
            )
            
            if result and result.get("success"):
                # 等待解析完成（轮询）
                self._wait_for_completion(doc_id, "parsing", timeout=1800)
                
                # 获取统计信息
                doc_stats = self._get_doc_stats(doc_id)
                elapsed = time.time() - t0
                stats.mark_success("parse", time=elapsed, items=doc_stats.get("item_count", 0))
                print(f"  ✅ 解析完成: {doc_stats.get('item_count', 0)} items, 耗时 {elapsed:.1f}s")
            else:
                elapsed = time.time() - t0
                stats.mark_failed("parse", error=str(result))
                print(f"  ❌ 解析失败: {result}")
        
        except Exception as e:
            elapsed = time.time() - t0
            stats.mark_failed("parse", error=str(e))
            print(f"  ❌ 解析异常: {e}")
        
        return stats
    
    def process_vlm(self, doc: dict) -> DocStats:
        """处理 VLM 增强阶段（串行）"""
        doc_id = doc["id"]
        file_name = doc["file_name"]
        
        stats = DocStats(doc_id, file_name)
        print(f"\n{'='*60}")
        print(f"🖼️  开始 VLM 增强: {file_name}")
        print(f"{'='*60}")
        
        t0 = time.time()
        try:
            result = self.call_api(
                f"{API_BASE_URL}/process/vlm",
                {
                    "document_id": doc_id,
                    "output_dir": OUTPUT_DIR,
                    "backend_type": VLM_BACKEND_TYPE,
                    "prompt": VLM_PROMPT,
                    "max_new_tokens": VLM_MAX_TOKENS,
                },
                timeout=300,
            )
            
            if result and result.get("success"):
                # 等待 VLM 完成
                self._wait_for_completion(doc_id, "vlm_processing", timeout=3600)
                
                # 获取统计信息
                doc_stats = self._get_doc_stats(doc_id)
                elapsed = time.time() - t0
                stats.mark_success("vlm", time=elapsed, pictures=doc_stats.get("picture_count", 0))
                print(f"  ✅ VLM 增强完成: {doc_stats.get('picture_count', 0)} pictures, 耗时 {elapsed:.1f}s")
            else:
                elapsed = time.time() - t0
                stats.mark_failed("vlm", error=str(result))
                print(f"  ❌ VLM 增强失败: {result}")
        
        except Exception as e:
            elapsed = time.time() - t0
            stats.mark_failed("vlm", error=str(e))
            print(f"  ❌ VLM 增强异常: {e}")
        
        return stats
    
    def process_chunk(self, doc: dict) -> DocStats:
        """处理分块阶段"""
        doc_id = doc["id"]
        file_name = doc["file_name"]
        file_path = doc["file_path"]
        
        stats = DocStats(doc_id, file_name)
        print(f"\n{'='*60}")
        print(f"🧩 开始分块: {file_name}")
        print(f"{'='*60}")
        
        t0 = time.time()
        try:
            result = self.call_api(
                f"{API_BASE_URL}/process/chunk",
                {
                    "pdf_path": file_path,
                    "document_id": doc_id,
                    "max_tokens": CHUNK_MAX_TOKENS,
                    "tokenizer_name": CHUNK_TOKENIZER,
                    "do_ocr": True,
                },
                timeout=300,
            )
            
            if result and result.get("success"):
                # 等待分块完成
                self._wait_for_completion(doc_id, "chunking", timeout=1800)
                
                # 获取统计信息
                doc_stats = self._get_doc_stats(doc_id)
                elapsed = time.time() - t0
                stats.mark_success("chunk", time=elapsed, chunks=doc_stats.get("item_count", 0))
                print(f"  ✅ 分块完成: 耗时 {elapsed:.1f}s")
            else:
                elapsed = time.time() - t0
                stats.mark_failed("chunk", error=str(result))
                print(f"  ❌ 分块失败: {result}")
        
        except Exception as e:
            elapsed = time.time() - t0
            stats.mark_failed("chunk", error=str(e))
            print(f"  ❌ 分块异常: {e}")
        
        return stats
    
    def process_embedding(self, doc: dict) -> DocStats:
        """处理 Embedding 阶段"""
        doc_id = doc["id"]
        file_name = doc["file_name"]
        
        stats = DocStats(doc_id, file_name)
        print(f"\n{'='*60}")
        print(f"🔢 开始 Embedding: {file_name}")
        print(f"{'='*60}")
        
        t0 = time.time()
        try:
            result = self.call_api(
                f"{API_BASE_URL}/process/embedding",
                {
                    "document_id": doc_id,
                    "backend_type": EMBEDDING_BACKEND,
                },
                timeout=300,
            )
            
            if result and result.get("success"):
                # 等待 Embedding 完成
                self._wait_for_completion(doc_id, "embedding", timeout=1800)
                
                elapsed = time.time() - t0
                stats.mark_success("embedding", time=elapsed)
                print(f"  ✅ Embedding 完成: 耗时 {elapsed:.1f}s")
            else:
                elapsed = time.time() - t0
                stats.mark_failed("embedding", error=str(result))
                print(f"  ❌ Embedding 失败: {result}")
        
        except Exception as e:
            elapsed = time.time() - t0
            stats.mark_failed("embedding", error=str(e))
            print(f"  ❌ Embedding 异常: {e}")
        
        return stats
    
    def _wait_for_completion(self, doc_id: str, target_status: str, timeout: int = 1800):
        """等待文档处理完成（通过 API 轮询）"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                response = requests.get(
                    f"{API_BASE_URL}/{doc_id}",
                    timeout=30,
                )
                response.raise_for_status()
                doc = response.json()
                
                status = doc.get("processing_status")
                if status in ("completed", "embedded", "chunked"):
                    return  # 完成
                elif status in ("failed", "parse_failed", "vlm_failed", "chunk_failed", "embedding_failed"):
                    raise Exception(f"处理失败: {status}")
            except requests.exceptions.RequestException as e:
                print(f"  ⚠️  查询状态失败: {e}")
            
            time.sleep(5)
        
        raise Exception(f"处理超时 ({timeout}s)")
    
    def _get_doc_stats(self, doc_id: str) -> dict:
        """获取文档统计信息（通过 API）"""
        try:
            response = requests.get(
                f"{API_BASE_URL}/{doc_id}",
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"  ⚠️  获取文档统计失败: {e}")
            return {}
    
    def process_document(self, doc: dict) -> DocStats:
        """处理单个文档的完整流程"""
        doc_id = doc["id"]
        file_name = doc["file_name"]
        
        print(f"\n{'#'*60}")
        print(f"📋 开始处理文档: {file_name} (ID: {doc_id})")
        print(f"{'#'*60}")
        
        # 1. Parse
        parse_stats = self.process_parse(doc)
        if parse_stats.stages["parse"]["status"] == "failed":
            return parse_stats  # 解析失败，跳过后续步骤
        
        # 2. VLM (串行)
        vlm_stats = self.process_vlm(doc)
        if vlm_stats.stages["vlm"]["status"] == "failed":
            # VLM 失败不阻断后续流程
            print(f"  ⚠️  VLM 增强失败，继续后续流程...")
        
        # 合并统计
        parse_stats.stages.update(vlm_stats.stages)
        
        # 3. Chunk
        chunk_stats = self.process_chunk(doc)
        if chunk_stats.stages["chunk"]["status"] == "failed":
            return parse_stats  # 分块失败，跳过 embedding
        
        parse_stats.stages.update(chunk_stats.stages)
        
        # 4. Embedding
        embedding_stats = self.process_embedding(doc)
        parse_stats.stages.update(embedding_stats.stages)
        
        return parse_stats
    
    def run(self):
        """运行批量处理"""
        print("="*60)
        print("🚀 批量文档处理开始")
        print("="*60)
        print(f"API 地址: {API_BASE_URL}")
        print(f"并行度: {MAX_WORKERS}")
        print(f"VLM 后端: {VLM_BACKEND_TYPE} (使用后端 .env 配置)")
        print(f"Embedding 后端: {EMBEDDING_BACKEND} (使用后端 .env 配置)")
        print(f"输出目录: {OUTPUT_DIR}")
        print()
        
        # 获取待处理文档
        docs = self.get_upload_documents()
        if not docs:
            print("✅ 没有待处理的文档")
            return
        
        print(f"找到 {len(docs)} 个待处理文档\n")
        
        total_start = time.time()
        
        # 第一阶段：并行 Parse
        print("\n" + "="*60)
        print("📊 阶段 1/4: 并行解析 (Parse)")
        print("="*60)
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self.process_parse, doc): doc for doc in docs}
            for future in as_completed(futures):
                doc = futures[future]
                try:
                    stats = future.result()
                    self.stats[doc["id"]] = stats
                except Exception as e:
                    print(f"  ❌ 解析异常: {doc['file_name']} - {e}")
                    doc_stats = DocStats(doc["id"], doc["file_name"])
                    doc_stats.mark_failed("parse", error=str(e))
                    self.stats[doc["id"]] = doc_stats
        
        # 第二阶段：串行 VLM
        print("\n" + "="*60)
        print("📊 阶段 2/4: 串行 VLM 增强")
        print("="*60)
        for doc_id, stats in self.stats.items():
            if stats.stages["parse"]["status"] == "success":
                doc = next(d for d in docs if d["id"] == doc_id)
                vlm_stats = self.process_vlm(doc)
                stats.stages.update(vlm_stats.stages)
        
        # 第三阶段：并行 Chunk
        print("\n" + "="*60)
        print("📊 阶段 3/4: 并行分块 (Chunk)")
        print("="*60)
        chunk_docs = [d for d in docs if self.stats.get(d["id"]) and self.stats[d["id"]].stages["parse"]["status"] == "success"]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self.process_chunk, doc): doc for doc in chunk_docs}
            for future in as_completed(futures):
                doc = futures[future]
                try:
                    chunk_stats = future.result()
                    self.stats[doc["id"]].stages.update(chunk_stats.stages)
                except Exception as e:
                    print(f"  ❌ 分块异常: {doc['file_name']} - {e}")
                    self.stats[doc["id"]].mark_failed("chunk", error=str(e))
        
        # 第四阶段：并行 Embedding
        print("\n" + "="*60)
        print("📊 阶段 4/4: 并行 Embedding")
        print("="*60)
        embedding_docs = [d for d in docs if self.stats.get(d["id"]) and self.stats[d["id"]].stages["chunk"]["status"] == "success"]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(self.process_embedding, doc): doc for doc in embedding_docs}
            for future in as_completed(futures):
                doc = futures[future]
                try:
                    embedding_stats = future.result()
                    self.stats[doc["id"]].stages.update(embedding_stats.stages)
                except Exception as e:
                    print(f"  ❌ Embedding 异常: {doc['file_name']} - {e}")
                    self.stats[doc["id"]].mark_failed("embedding", error=str(e))
        
        total_elapsed = time.time() - total_start
        
        # 输出统计
        self.print_summary(total_elapsed)
        
        # 保存统计结果到文件
        self.save_stats()
    
    def print_summary(self, total_elapsed: float):
        """打印统计摘要"""
        print(f"\n{'='*60}")
        print("📊 处理结果统计")
        print(f"{'='*60}")
        print(f"总耗时: {total_elapsed/60:.1f} 分钟")
        print(f"总文档数: {len(self.stats)}")
        
        success_count = sum(1 for s in self.stats.values() if all(
            stage["status"] == "success" for stage in s.stages.values()
        ))
        failed_count = len(self.stats) - success_count
        
        print(f"全部成功: {success_count}")
        print(f"部分失败: {failed_count}")
        
        print(f"\n{'='*60}")
        print("详细统计:")
        print(f"{'='*60}")
        print(f"{'文档':<40} {'解析':>6} {'VLM':>6} {'分块':>6} {'Embed':>6} {'总耗时':>8}")
        print("-"*80)
        
        for doc_id, stats in sorted(self.stats.items()):
            file_name = stats.file_name[:38]
            stages = stats.stages
            
            def stage_symbol(stage):
                if stage["status"] == "success":
                    return "✅"
                elif stage["status"] == "failed":
                    return "❌"
                else:
                    return "⏭️"
            
            total_time = sum(s["time"] for s in stages.values())
            
            print(f"{file_name:<40} {stage_symbol(stages['parse']):>6} {stage_symbol(stages['vlm']):>6} {stage_symbol(stages['chunk']):>6} {stage_symbol(stages['embedding']):>6} {total_time:>8.1f}s")
            
            # 打印失败原因
            for stage_name, stage in stages.items():
                if stage["status"] == "failed" and stage.get("error"):
                    print(f"  ⚠️  {stage_name}: {stage['error'][:100]}")
    
    def save_stats(self):
        """保存统计结果到文件"""
        output_dir = Path("output/batch_processing")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = output_dir / f"batch_stats_{timestamp}.json"
        
        stats_data = {
            "timestamp": timestamp,
            "total_documents": len(self.stats),
            "documents": {doc_id: stats.to_dict() for doc_id, stats in self.stats.items()},
        }
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ 统计结果已保存: {stats_file}")


def main():
    """主函数"""
    processor = BatchProcessor()
    processor.run()


if __name__ == "__main__":
    main()
