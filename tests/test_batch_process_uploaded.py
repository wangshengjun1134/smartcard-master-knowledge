"""
测试批量处理uploaded状态的文档
- 查询数据库中uploaded状态的doc_info记录
- 复用现有解析逻辑（Parse → VLM → Chunk → Embedding）
- 并发度为5
- 统计结果
- 支持长时间运行（数小时）不中断
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from dataclasses import dataclass, field

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.smartcard_kb.docs_compile.database import (
    get_connection, 
    query_document_info,
    insert_document_items,
    update_document_info,
    query_document_items,
    query_chunks,
    get_document_stats,
)
from src.smartcard_kb.docs_compile.pdf_parser import PDFParser
from src.smartcard_kb.docs_compile.vlm_service import VLMService
from src.smartcard_kb.docs_compile.chunker import Chunker
from src.smartcard_kb.docs_compile.embedding_service import EmbeddingService
from src.smartcard_kb.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            f'output/batch_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class DocProcessStats:
    """文档处理统计"""
    document_id: str
    file_name: str
    stages: Dict[str, Any] = field(default_factory=dict)
    total_time: float = 0.0
    error: str = None
    
    def __post_init__(self):
        self.stages = {
            "parse": {"status": "pending", "time": 0, "items": 0, "error": None},
            "vlm": {"status": "pending", "time": 0, "pictures": 0, "error": None},
            "chunk": {"status": "pending", "time": 0, "chunks": 0, "error": None},
            "embedding": {"status": "pending", "time": 0, "error": None},
        }
    
    def to_dict(self):
        return {
            "document_id": self.document_id,
            "file_name": self.file_name,
            "stages": self.stages,
            "total_time": self.total_time,
            "error": self.error,
        }


class BatchProcessTester:
    """批量处理测试器"""
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.stats: List[DocProcessStats] = []
        self.start_time = None
        
        # 初始化解析器
        self.parser = PDFParser(do_ocr=True)
        
        # 初始化VLM后端（延迟初始化，在process_vlm中创建）
        self.vlm_backend = None
        
        # 初始化分块器
        self.chunker = Chunker()
        
        # Embedding后端（延迟初始化）
        self.embedding_backend = None
    
    def get_uploaded_documents(self, limit: int = None) -> List[Dict[str, Any]]:
        """查询uploaded状态的文档"""
        logger.info(f"查询uploaded状态的文档 (limit={limit})...")
        
        docs = query_document_info(processing_status='uploaded')
        
        if limit:
            docs = docs[:limit]
        
        logger.info(f"找到 {len(docs)} 个uploaded状态的文档")
        return docs
    
    def process_parse(self, doc: Dict[str, Any], stats: DocProcessStats) -> bool:
        """执行解析阶段"""
        stage = stats.stages["parse"]
        stage["status"] = "running"
        stage_start = time.time()
        
        try:
            logger.info(f"[{doc['file_name']}] 开始解析...")
            
            # 更新状态为parsing
            update_document_info({
                "id": doc['id'],
                "processing_status": "parsing",
            })
            
            # 执行解析
            result = self.parser.parse_pdf(
                pdf_path=doc['file_path'],
                document_id=doc['id'],
                output_dir="output/pictures"
            )
            
            # 获取解析结果统计
            items = result.get('items', [])
            item_count = len(items)
            
            # 统计各类型数量
            text_count = sum(1 for item in items if item.get('label') == 'text')
            title_count = sum(1 for item in items if item.get('label') == 'section_header')
            table_count = sum(1 for item in items if item.get('label') == 'table')
            picture_count = sum(1 for item in items if item.get('label') == 'picture')
            formula_count = sum(1 for item in items if item.get('label') == 'formula')
            
            # 更新状态为parsed
            update_document_info({
                "id": doc['id'],
                "processing_status": "parsed",
                "item_count": item_count,
                "text_count": text_count,
                "title_count": title_count,
                "table_count": table_count,
                "picture_count": picture_count,
                "formula_count": formula_count,
            })
            
            stage["status"] = "completed"
            stage["time"] = round(time.time() - stage_start, 2)
            stage["items"] = item_count
            
            logger.info(
                f"[{doc['file_name']}] 解析完成: {item_count} items "
                f"(text={text_count}, title={title_count}, table={table_count}, "
                f"picture={picture_count}, formula={formula_count}), "
                f"耗时 {stage['time']}s"
            )
            
            return True
            
        except Exception as e:
            stage["status"] = "failed"
            stage["error"] = str(e)
            stage["time"] = round(time.time() - stage_start, 2)
            
            # 更新数据库状态
            try:
                update_document_info({
                    "id": doc['id'],
                    "processing_status": "parse_failed",
                    "processing_error": str(e),
                })
            except:
                pass
            
            logger.error(f"[{doc['file_name']}] 解析失败: {e}", exc_info=True)
            return False
    
    def process_vlm(self, doc: Dict[str, Any], stats: DocProcessStats) -> bool:
        """执行VLM阶段"""
        stage = stats.stages["vlm"]
        stage["status"] = "running"
        stage_start = time.time()
        
        try:
            logger.info(f"[{doc['file_name']}] 开始VLM处理...")
            
            # 更新状态
            update_document_info({
                "id": doc['id'],
                "processing_status": "vlm_processing",
            })
            
            # 查询图片items
            pictures = query_document_items(
                document_id=doc['id'],
                label='picture',
                is_rag_enabled=True
            )
            
            picture_count = len(pictures)
            
            if picture_count > 0:
                # 创建VLM后端和服务
                resolved_api_key = settings.vlm_openai_api_key
                resolved_base_url = settings.vlm_openai_base_url
                resolved_model = settings.vlm_openai_model
                
                if not resolved_api_key:
                    raise ValueError("VLM API Key 未配置")
                
                backend = VLMService.create_backend(
                    backend_type="openai",
                    api_key=resolved_api_key,
                    base_url=resolved_base_url,
                    model=resolved_model,
                )
                vlm_service = VLMService(vlm_backend=backend)
                
                # 生成VLM描述
                vlm_results = vlm_service.generate_vlm_descriptions(
                    document_id=doc['id'],
                    output_dir="output/pictures",
                )
                
                logger.info(f"[{doc['file_name']}] VLM处理完成: {picture_count} 张图片")
            else:
                logger.info(f"[{doc['file_name']}] 没有需要处理的图片")
            
            # 更新状态
            update_document_info({
                "id": doc['id'],
                "processing_status": "vlm_completed",
            })
            
            stage["status"] = "completed"
            stage["time"] = round(time.time() - stage_start, 2)
            stage["pictures"] = picture_count
            
            logger.info(f"[{doc['file_name']}] VLM完成, 耗时 {stage['time']}s")
            
            return True
            
        except Exception as e:
            stage["status"] = "failed"
            stage["error"] = str(e)
            stage["time"] = round(time.time() - stage_start, 2)
            
            try:
                update_document_info({
                    "id": doc['id'],
                    "processing_status": "vlm_failed",
                    "processing_error": str(e),
                })
            except:
                pass
            
            logger.error(f"[{doc['file_name']}] VLM失败: {e}", exc_info=True)
            return False
    
    def process_chunk(self, doc: Dict[str, Any], stats: DocProcessStats) -> bool:
        """执行分块阶段"""
        stage = stats.stages["chunk"]
        stage["status"] = "running"
        stage_start = time.time()
        
        try:
            logger.info(f"[{doc['file_name']}] 开始分块...")
            
            # 更新状态
            update_document_info({
                "id": doc['id'],
                "processing_status": "chunking",
            })
            
            # 调用分块器（内部会查询items）
            result = self.chunker.generate_chunks(
                pdf_path=doc['file_path'],
                document_id=doc['id'],
            )
            
            chunks = result.get('chunks', [])
            chunk_count = len(chunks)
            
            logger.info(f"[{doc['file_name']}] 分块完成: {chunk_count} chunks")
            
            # 更新状态
            update_document_info({
                "id": doc['id'],
                "processing_status": "chunked",
            })
            
            stage["status"] = "completed"
            stage["time"] = round(time.time() - stage_start, 2)
            stage["chunks"] = chunk_count
            
            logger.info(f"[{doc['file_name']}] 分块完成, 耗时 {stage['time']}s")
            
            return True
            
        except Exception as e:
            stage["status"] = "failed"
            stage["error"] = str(e)
            stage["time"] = round(time.time() - stage_start, 2)
            
            try:
                update_document_info({
                    "id": doc['id'],
                    "processing_status": "chunk_failed",
                    "processing_error": str(e),
                })
            except:
                pass
            
            logger.error(f"[{doc['file_name']}] 分块失败: {e}", exc_info=True)
            return False
    
    def process_embedding(self, doc: Dict[str, Any], stats: DocProcessStats) -> bool:
        """执行Embedding阶段"""
        stage = stats.stages["embedding"]
        stage["status"] = "running"
        stage_start = time.time()
        
        try:
            logger.info(f"[{doc['file_name']}] 开始生成Embedding...")
            
            # 更新状态
            update_document_info({
                "id": doc['id'],
                "processing_status": "embedding",
            })
            
            # 查询chunks
            chunks = query_chunks(
                document_id=doc['id'],
                is_rag_enabled=True
            )
            
            if chunks:
                # 创建Embedding后端和服务
                # 使用本地embedding模型
                embedding_backend = EmbeddingService.create_backend(
                    backend_type="local",
                    model_name="BAAI/bge-m3",
                )
                embedding_service = EmbeddingService(embedding_backend=embedding_backend)
                
                # 生成embeddings
                embedding_service.generate_embeddings(
                    document_id=doc['id'],
                )
                
                logger.info(f"[{doc['file_name']}] Embedding生成完成: {len(chunks)} chunks")
            else:
                logger.warning(f"[{doc['file_name']}] 没有需要生成embedding的chunks")
            
            # 更新状态
            update_document_info({
                "id": doc['id'],
                "processing_status": "embedded",
            })
            
            stage["status"] = "completed"
            stage["time"] = round(time.time() - stage_start, 2)
            
            logger.info(f"[{doc['file_name']}] Embedding完成, 耗时 {stage['time']}s")
            
            return True
            
        except Exception as e:
            stage["status"] = "failed"
            stage["error"] = str(e)
            stage["time"] = round(time.time() - stage_start, 2)
            
            try:
                update_document_info({
                    "id": doc['id'],
                    "processing_status": "embedding_failed",
                    "processing_error": str(e),
                })
            except:
                pass
            
            logger.error(f"[{doc['file_name']}] Embedding失败: {e}", exc_info=True)
            return False
    
    def process_document(self, doc: Dict[str, Any]) -> DocProcessStats:
        """处理单个文档（完整流程）"""
        stats = DocProcessStats(
            document_id=doc['id'],
            file_name=doc['file_name']
        )
        
        doc_start = time.time()
        
        logger.info(f"{'='*80}")
        logger.info(f"开始处理文档: {doc['file_name']} (ID: {doc['id']})")
        logger.info(f"{'='*80}")
        
        # 阶段1: Parse
        if not self.process_parse(doc, stats):
            stats.error = "Parse failed"
            stats.total_time = time.time() - doc_start
            return stats
        
        # 阶段2: VLM
        if not self.process_vlm(doc, stats):
            stats.error = "VLM failed"
            stats.total_time = time.time() - doc_start
            return stats
        
        # 阶段3: Chunk
        if not self.process_chunk(doc, stats):
            stats.error = "Chunk failed"
            stats.total_time = time.time() - doc_start
            return stats
        
        # 阶段4: Embedding
        if not self.process_embedding(doc, stats):
            stats.error = "Embedding failed"
            stats.total_time = time.time() - doc_start
            return stats
        
        stats.total_time = time.time() - doc_start
        
        logger.info(f"{'='*80}")
        logger.info(f"文档处理完成: {doc['file_name']}, 总耗时: {stats.total_time:.2f}s")
        logger.info(f"{'='*80}")
        
        return stats
    
    def run(self, limit: int = None):
        """运行批量处理测试"""
        self.start_time = time.time()
        
        logger.info(f"{'#'*80}")
        logger.info(f"批量处理测试开始")
        logger.info(f"并发度: {self.max_workers}")
        logger.info(f"{'#'*80}")
        
        # 查询文档
        docs = self.get_uploaded_documents(limit=limit)
        
        if not docs:
            logger.info("没有需要处理的文档")
            return
        
        logger.info(f"总共需要处理 {len(docs)} 个文档")
        
        # 并发处理
        with ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="doc_processor") as executor:
            futures = {
                executor.submit(self.process_document, doc): doc 
                for doc in docs
            }
            
            for future in as_completed(futures):
                doc = futures[future]
                try:
                    stats = future.result()
                    self.stats.append(stats)
                except Exception as e:
                    logger.error(f"文档处理异常 {doc['file_name']}: {e}", exc_info=True)
                    self.stats.append(DocProcessStats(
                        document_id=doc['id'],
                        file_name=doc['file_name'],
                        error=str(e)
                    ))
        
        # 输出统计结果
        self.print_summary()
    
    def print_summary(self):
        """打印统计摘要"""
        total_time = time.time() - self.start_time
        
        logger.info(f"\n{'#'*80}")
        logger.info(f"批量处理完成 - 统计摘要")
        logger.info(f"{'#'*80}")
        logger.info(f"总耗时: {total_time:.2f}s ({total_time/60:.2f}分钟)")
        logger.info(f"处理文档数: {len(self.stats)}")
        
        # 统计各阶段成功/失败
        stage_names = ["parse", "vlm", "chunk", "embedding"]
        for stage_name in stage_names:
            completed = sum(1 for s in self.stats if s.stages[stage_name]["status"] == "completed")
            failed = sum(1 for s in self.stats if s.stages[stage_name]["status"] == "failed")
            pending = sum(1 for s in self.stats if s.stages[stage_name]["status"] == "pending")
            
            avg_time = 0
            times = [s.stages[stage_name]["time"] for s in self.stats if s.stages[stage_name]["time"] > 0]
            if times:
                avg_time = sum(times) / len(times)
            
            logger.info(f"\n{stage_name.upper()}:")
            logger.info(f"  成功: {completed}, 失败: {failed}, 未执行: {pending}")
            logger.info(f"  平均耗时: {avg_time:.2f}s")
        
        # 成功/失败文档统计
        success_docs = [s for s in self.stats if not s.error]
        failed_docs = [s for s in self.stats if s.error]
        
        logger.info(f"\n成功文档: {len(success_docs)}")
        logger.info(f"失败文档: {len(failed_docs)}")
        
        if failed_docs:
            logger.info(f"\n失败文档列表:")
            for s in failed_docs:
                logger.info(f"  - {s.file_name}: {s.error}")
        
        # 保存详细统计到文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stats_file = f"output/batch_test_stats_{timestamp}.json"
        os.makedirs("output", exist_ok=True)
        
        stats_data = {
            "summary": {
                "total_time": total_time,
                "total_docs": len(self.stats),
                "success_docs": len(success_docs),
                "failed_docs": len(failed_docs),
            },
            "documents": [s.to_dict() for s in self.stats]
        }
        
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n详细统计已保存到: {stats_file}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量处理uploaded状态的文档')
    parser.add_argument('--limit', type=int, default=None, help='限制处理的文档数量')
    parser.add_argument('--workers', type=int, default=5, help='并发worker数量')
    
    args = parser.parse_args()
    
    # 创建测试器并运行
    tester = BatchProcessTester(max_workers=args.workers)
    tester.run(limit=args.limit)


if __name__ == "__main__":
    main()
