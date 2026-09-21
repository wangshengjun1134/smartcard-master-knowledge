"""
简化测试：验证 OCR + VLM 流程
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import numpy as np
from pathlib import Path
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

print("="*60)
print("OCR + VLM 简化测试")
print("="*60)

# 图片路径
IMAGE_PATH = "output/pdf_page_32/page_32_img_1.png"
VLM_MODEL_PATH = r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct"

if not Path(IMAGE_PATH).exists():
    print(f"图片不存在：{IMAGE_PATH}")
    sys.exit(1)

# 步骤 1: OCR
print(f"\n[1/3] 执行 OCR: {IMAGE_PATH}")
img = np.array(Image.open(IMAGE_PATH).convert('RGB'))
ocr = RapidOCR()
result, _ = ocr(img)

if result:
    print(f"  ✅ OCR 识别到 {len(result)} 条结果")
    ocr_items = []
    for item in result:
        box = item[0]
        text = item[1]
        confidence = item[2]
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
        ocr_items.append({
            "text": text.strip(),
            "bbox": bbox,
            "confidence": float(confidence)
        })
    
    # 保存 OCR 结果
    ocr_file = Path("output/pdf_page_32/ocr_results.json")
    with open(ocr_file, "w", encoding="utf-8") as f:
        json.dump(ocr_items, f, ensure_ascii=False, indent=2)
    print(f"  📄 OCR 结果已保存到：{ocr_file}")
else:
    print("  ❌ OCR 无结果")
    sys.exit(1)

# 步骤 2: 加载 VLM
print(f"\n[2/3] 加载 VLM 模型：{VLM_MODEL_PATH}")
try:
    import torch
    from transformers import Qwen3VLForConditionalGeneration, AutoProcessor
    
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        VLM_MODEL_PATH,
        dtype="auto",
        device_map="auto"
    )
    processor = AutoProcessor.from_pretrained(VLM_MODEL_PATH)
    print("  ✅ VLM 加载成功")
except Exception as e:
    print(f"  ❌ VLM 加载失败：{e}")
    sys.exit(1)

# 步骤 3: VLM 推理
print("\n[3/3] 执行 VLM 推理...")

CAPTION = "GSMA SGP.01 规范中的 eUICC 流程图"
PROMPT = """请根据图片内容和 OCR 文字，描述这个流程图的步骤和关系。"""

system_prompt = """你是一个专业的文档视觉理解助手。请以原始图片的视觉信息为主要依据，OCR 结果仅作为辅助信息。"""

ocr_json_str = json.dumps(ocr_items, ensure_ascii=False, indent=2)

user_content = f"""### 图片标题
{CAPTION}

### 图片中的文字及其空间坐标 (JSON)
```json
{ocr_json_str}
```

### 你的任务
{PROMPT}
"""

messages = [
    {"role": "system", "content": system_prompt},
    {
        "role": "user",
        "content": [
            {"type": "image", "image": IMAGE_PATH},
            {"type": "text", "text": user_content},
        ],
    }
]

print("  正在调用 VLM...")
inputs = processor.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt"
).to(model.device)

with torch.no_grad():
    generated_ids = model.generate(**inputs, max_new_tokens=512)

generated_ids_trimmed = [
    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
]

output_text = processor.batch_decode(
    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
)

print("\n" + "="*60)
print("VLM 输出结果:")
print("="*60)
print(output_text[0])
print("="*60)

# 保存结果
result_file = Path("output/pdf_page_32/vlm_result.txt")
with open(result_file, "w", encoding="utf-8") as f:
    f.write(output_text[0])
print(f"\n📄 结果已保存到：{result_file}")
print("\n✅ 测试完成！")
