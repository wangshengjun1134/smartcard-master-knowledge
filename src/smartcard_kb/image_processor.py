"""
图片内容提取模块 - 结合 OCR 空间坐标与 VLM 的多模态理解
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
import torch
from PIL import Image
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor


class ImageContentExtractor:
    """
    结合 OCR 空间坐标与 VLM 的图片内容提取器
    逻辑：
    1. 使用 OCR 提取文字及其边界框 (bbox)
    2. 将 OCR 结果、图片、Caption 和 Prompt 组合成结构化输入
    3. 调用 VLM 进行深度理解
    """

    def __init__(
        self,
        vlm_model_path: str = r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct",
        device: str = "cuda" if torch.cuda.is_available() else "cpu"
    ):
        """
        初始化提取器
        :param vlm_model_path: 本地 VLM 模型路径
        :param device: 运行设备
        """
        print(f"正在加载 VLM 模型: {vlm_model_path}")
        self.device = device
        
        # 加载 VLM
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            vlm_model_path,
            dtype="auto",
            device_map="auto"
        )
        self.processor = AutoProcessor.from_pretrained(vlm_model_path)
        
        # 加载 OCR 引擎 (使用 rapidocr，已随 docling 安装)
        try:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr_engine = RapidOCR()
            print("OCR 引擎 (RapidOCR) 加载成功")
        except ImportError:
            raise ImportError("未找到 rapidocr_onnxruntime，请确保已安装 docling 或单独安装 rapidocr")

    def _extract_ocr_with_bbox(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        执行 OCR 并提取带坐标和置信度的文字列表
        :param image: PIL Image 对象
        :return: [{"text": "...", "bbox": [x1, y1, x2, y2], "confidence": 0.xx}, ...]
        """
        # 转换回 numpy array 供 rapidocr 使用
        img_array = np.array(image)
        result = self.ocr_engine(img_array)
        
        if result is None or result[0] is None:
            return []

        ocr_items = []
        # RapidOCR 返回格式: (boxes, texts, scores)
        # boxes 格式: [[ [x1,y1], [x2,y2], [x3,y3], [x4,y4] ], ...]
        boxes = result[0]
        texts = result[1]
        scores = result[2]

        for box, text, score in zip(boxes, texts, scores):
            # 将四点坐标转换为 [min_x, min_y, max_x, max_y]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
            
            ocr_items.append({
                "text": text.strip(),
                "bbox": bbox,
                "confidence": round(float(score), 4)
            })
        return ocr_items

    def process_image(
        self, 
        image_path: str, 
        prompt: str, 
        caption: str = "", 
        max_new_tokens: int = 512
    ) -> str:
        """
        处理图片并返回 VLM 的识别结果
        :param image_path: 图片路径
        :param prompt: 给 VLM 的任务提示词
        :param caption: 图片的基础描述 (可选)
        :param max_new_tokens: 最大生成 token 数
        :return: VLM 生成的文本
        """
        if not Path(image_path).exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        image = Image.open(image_path).convert("RGB")
        
        # 1. 提取 OCR 空间数据
        print("正在提取 OCR 空间数据...")
        ocr_items = self._extract_ocr_with_bbox(image)
        
        # 2. 构建结构化 OCR 描述 (保留空间关系)
        ocr_json_str = json.dumps(ocr_items, ensure_ascii=False, indent=2)
        
        # 3. 构建 VLM Prompt
        system_prompt = """你是一个专业的文档视觉理解助手。

你会收到：
1. 一张原始图片
2. OCR 提取出的文字及其空间坐标
3. 图片标题（如果存在）
4. 用户要求完成的任务

请以原始图片的视觉信息为主要依据，OCR 结果仅作为辅助信息。

特别注意：
- OCR 可能存在识别错误；
- 不要盲目相信 OCR；
- 根据图片中的位置、框、箭头、连线、颜色、形状和布局理解内容；
- 对流程图、架构图等图片，要重点分析节点之间的关系和方向；
- 如果 OCR 与图片视觉信息冲突，以图片中能够确认的信息为准；
- 不要臆测图片中不存在的信息。"""
        
        user_content = f"""
### 图片标题
{caption if caption else "无"}

### 图片中的文字及其空间坐标与置信度 (JSON)
```json
{ocr_json_str}
```

### 你的任务
{prompt}
"""

        # 4. 构建消息格式
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image_path},
                    {"type": "text", "text": user_content},
                ],
            }
        ]

        # 5. 推理
        print("正在调用 VLM 进行深度理解...")
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(self.model.device)

        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=max_new_tokens)
            
        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        
        return output_text[0]


if __name__ == "__main__":
    # 测试示例
    extractor = ImageContentExtractor()
    # 注意：此处需要替换为真实的图片路径和提示词
    # result = extractor.process_image("test.jpg", "请分析这张流程图，并提取其中的判断逻辑。")
    # print(result)
    pass
