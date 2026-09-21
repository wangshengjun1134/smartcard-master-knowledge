"""
图片内容提取模块 - 结合 OCR 空间坐标与 VLM 的多模态理解
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
from PIL import Image

from .llms import LocalQwenVLMBackend, OpenAICompatibleBackend, VLMBackend

class ImageContentExtractor:
    """
    结合 OCR 空间坐标与 VLM 的图片内容提取器
    
    使用示例：
        # 使用本地模型
        extractor = ImageContentExtractor(backend_type="local", model_path="/path/to/model")
        
        # 使用 DashScope API
        extractor = ImageContentExtractor(
            backend_type="openai",
            api_key="your-key",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-vl-max"
        )
    """

    def __init__(
        self,
        backend_type: str = "openai",
        *,
        model_path: str = r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct",
        device: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "qwen-vl-max",
        timeout: int = 120,
    ):
        """
        初始化提取器
        :param backend_type: 后端类型 ("local" 或 "openai")
        :param model_path: 本地模型路径（仅 local 后端）
        :param device: 运行设备（仅 local 后端）
        :param api_key: API Key（仅 openai 后端）
        :param base_url: API 基础 URL（仅 openai 后端）
        :param model: 模型名称（仅 openai 后端）
        :param timeout: 请求超时时间（仅 openai 后端）
        """
        # 初始化 OCR 引擎
        try:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr_engine = RapidOCR()
            print("OCR 引擎 (RapidOCR) 加载成功")
        except ImportError:
            raise ImportError("未找到 rapidocr_onnxruntime，请 pip install rapidocr-onnxruntime")

        # 初始化 VLM 后端
        if backend_type == "local":
            self.backend = LocalQwenVLMBackend(model_path=model_path, device=device)
        elif backend_type == "openai":
            if not api_key or not base_url:
                raise ValueError("使用 openai 后端需要提供 api_key 和 base_url")
            self.backend = OpenAICompatibleBackend(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
        else:
            raise ValueError(f"不支持的后端类型: {backend_type}，支持 'local' 或 'openai'")

        print(f"ImageContentExtractor 初始化完成，后端: {backend_type}")

    def _extract_ocr_with_bbox(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        执行 OCR 并提取带坐标和置信度的文字列表
        :param image: PIL Image 对象
        :return: [{"text": "...", "bbox": [x1, y1, x2, y2], "confidence": 0.xx}, ...]
        """
        # 转换回 numpy array 供 rapidocr 使用
        img_array = np.array(image)
        result, _ = self.ocr_engine(img_array)
        
        if result is None:
            return []

        ocr_items = []
        # RapidOCR (onnxruntime) 返回格式：[[[box], text, confidence], ...]
        # box 格式：[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        for item in result:
            box = item[0]
            text = item[1]
            confidence = item[2]
            
            # 将四点坐标转换为 [min_x, min_y, max_x, max_y]
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
            
            ocr_items.append({
                "text": text.strip(),
                "bbox": bbox,
                "confidence": round(float(confidence), 4)
            })
        return ocr_items

    def process_image(
        self,
        image_path: str,
        prompt: str,
        caption: str = "",
        max_new_tokens: int = 512
    ) -> str:
        """处理图片并返回 VLM 结果"""
        if not Path(image_path).exists():
            raise FileNotFoundError(f"图片文件不存在：{image_path}")

        image = Image.open(image_path).convert("RGB")

        # 提取 OCR 空间数据
        print("正在提取 OCR 空间数据...")
        ocr_items = self._extract_ocr_with_bbox(image)
        ocr_json_str = json.dumps(ocr_items, ensure_ascii=False, indent=2)

        # 构建消息
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

        # 调用 VLM 后端
        print("正在调用 VLM 进行深度理解...")
        return self.backend.generate(image, messages, max_new_tokens)


if __name__ == "__main__":
    extractor = ImageContentExtractor(
        backend_type="openai",
        api_key="sk-sp-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        base_url="https://coding-intl.dashscope.aliyuncs.com/v1",
        model="qwen-vl-max"
    )
    # result = extractor.process_image("test.jpg", "请分析这张流程图")
    # print(result)
