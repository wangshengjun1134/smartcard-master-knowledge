"""本地重排模型后端（基于 BGE-Reranker）"""

from typing import List, Tuple

from .reranker_base import RerankerBackend


class LocalRerankerBackend(RerankerBackend):
    """本地重排模型后端"""

    def __init__(self, model_path: str = "BAAI/bge-reranker-v2-m3"):
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
        
        print(f"加载重排模型: {model_path}, 设备: {self.device}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, local_files_only=True
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_path, local_files_only=True
        )
        self.model.to(self.device)
        self.model.eval()
        
        self.model_path = model_path
        print(f"本地重排模型加载完成: {model_path}")

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
        with torch.no_grad():
            outputs = self.model(**inputs)
            scores = outputs.logits.squeeze(-1).cpu().numpy()

        # 转换为 float 列表
        scores = scores.tolist()

        # 按分数降序排序
        scored_docs = list(enumerate(scores))
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        # 返回前 top_k 个
        return [(idx, float(score)) for idx, score in scored_docs[:top_k]]
