"""本地重排模型后端（基于 BGE-Reranker）"""

import os
from typing import List, Tuple

from smartcard_kb.logger import logger

from .reranker_base import RerankerBackend


class LocalRerankerBackend(RerankerBackend):
    """本地重排模型后端"""

    def __init__(self, model_path: str = "D:/softdata/workspaces/ai-models/bge-reranker-v2-m3"):
        """
        初始化本地重排模型后端

        :param model_path: 模型路径或 HuggingFace 模型 ID
        """
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            import torch
        except ImportError:
            raise ImportError(
                "使用本地重排模型需要安装 transformers 和 torch: "
                "pip install transformers torch"
            )

        self.torch = torch
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        logger.info(f"加载重排模型: {model_path}, 设备: {self.device}")

        # 检查模型文件是否完整（防止 Git LFS 指针文件）
        tokenizer_json = os.path.join(model_path, "tokenizer.json")
        sp_model = os.path.join(model_path, "sentencepiece.bpe.model")

        for f in [tokenizer_json, sp_model]:
            if os.path.exists(f):
                # 使用二进制模式读取，避免编码错误
                with open(f, 'rb') as fp:
                    content = fp.read(100)
                    if b'git-lfs' in content:
                        raise FileNotFoundError(
                            f"模型文件 {os.path.basename(f)} 是 Git LFS 指针文件，未下载实际内容。\n"
                            f"请手动下载该文件并替换，或运行:\n"
                            f"  cd {model_path}\n"
                            f"  git lfs pull\n"
                            f"或从 HuggingFace 手动下载: https://huggingface.co/BAAI/bge-reranker-v2-m3"
                        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, local_files_only=True, trust_remote_code=True
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_path, local_files_only=True
        )
        self.model.to(self.device)
        self.model.eval()

        self.model_path = model_path
        logger.info(f"本地重排模型加载完成: {model_path}")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10,
    ) -> List[Tuple[int, float]]:
        """
        对文档列表进行重排
        
        :param query: 查询文本
        :param documents: 文档列表
        :param top_k: 返回前 K 个结果
        :return: 排序后的 (原始索引, 分数) 列表
        """
        if not documents:
            return []

        # 构建查询-文档对
        pairs = [[query, doc] for doc in documents]

        #  tokenize
        inputs = self.tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self.device)

        # 推理
        with self.torch.no_grad():
            outputs = self.model(**inputs)
            scores = outputs.logits.squeeze(-1).cpu().numpy()

        # 转换为 float 列表
        scores = scores.tolist()

        # 按分数降序排序
        scored_docs = list(enumerate(scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # 返回前 top_k 个
        return [(idx, float(score)) for idx, score in scored_docs[:top_k]]
