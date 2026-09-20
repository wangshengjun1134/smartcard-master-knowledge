"""测试 Qwen3-VL-8B-Instruct 本地模型推理"""

import pytest
from pathlib import Path
import torch
from transformers import Qwen3VLForConditionalGeneration, AutoProcessor


def test_qwen3_vl_local_inference():
    """使用本地 Qwen3-VL 模型进行图文推理测试"""
    
    # ================= 配置区 =================
    # 本地模型路径
    MODEL_PATH = r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct"
    
    # 本地图片路径 (请替换为实际存在的 .jpg 或 .png 文件)
    IMAGE_PATH = r"D:\softdata\workspaces\buff\smartcard-master-knowledge\tests\流程图.png"
    
    # 提示词
    PROMPT = "请详细描述这张图片中的内容。"
    
    # 最大生成 token 数
    MAX_NEW_TOKENS = 256
    # ==========================================

    if not Path(MODEL_PATH).exists():
        pytest.skip(f"本地模型路径不存在: {MODEL_PATH}")
        
    if not Path(IMAGE_PATH).exists():
        pytest.skip(f"测试图片路径不存在: {IMAGE_PATH}。请在代码中修改 IMAGE_PATH 变量。")

    print(f"\n[1/4] 加载模型: {MODEL_PATH}")
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        MODEL_PATH, 
        dtype="auto", 
        device_map="auto"
    )
    
    print("[2/4] 加载处理器...")
    processor = AutoProcessor.from_pretrained(MODEL_PATH)
    
    print("[3/4] 构建输入数据...")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": IMAGE_PATH},
                {"type": "text", "text": PROMPT},
            ],
        }
    ]
    
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt"
    )
    inputs = inputs.to(model.device)
    
    print("[4/4] 开始推理生成...")
    with torch.no_grad():
        generated_ids = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)
        
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    
    print("\n" + "="*50)
    print("🤖 模型推理结果:")
    print("="*50)
    print(output_text[0])
    print("="*50)


if __name__ == "__main__":
    test_qwen3_vl_local_inference()
