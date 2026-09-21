"""
测试 Docling 提取 PDF 图片功能
验证：PDF → Docling 提取图片 → 保存图片 → OCR → VLM 描述
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
from smartcard_kb.document import DoclingPDFProcessor
from smartcard_kb.image_processor import ImageContentExtractor

print("="*60)
print("Docling 提取 PDF 图片 + OCR + VLM 测试")
print("="*60)

# 配置
PDF_PATH = "specs/03-management-provisioning/gsma/SGP.01-v1.12.pdf"
PAGE_NUMBER = 32
OUTPUT_DIR = Path("output/docling_test")

# OpenAI 兼容后端配置
VLM_CONFIG = {
    "backend_type": "openai",
    "api_key": "sk-sp-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "base_url": "https://coding.dashscope.aliyuncs.com/v1",
    "model": "qwen3.7-plus"
}

if not Path(PDF_PATH).exists():
    print(f"❌ PDF 文件不存在：{PDF_PATH}")
    sys.exit(1)

# ========== 步骤 1: Docling 提取图片 ==========
print(f"\n[步骤 1/3] 使用 Docling 从 PDF 第{PAGE_NUMBER}页提取图片...")
print(f"PDF 路径：{PDF_PATH}")

try:
    processor = DoclingPDFProcessor(do_ocr=True)
    results = processor.process_pdf(
        PDF_PATH,
        page_range=(PAGE_NUMBER, PAGE_NUMBER),
        output_dir=str(OUTPUT_DIR / "pictures")
    )
    
    # 筛选出图片
    pictures = [r for r in results if r['type'] == 'picture']
    
    if not pictures:
        print("⚠️  未找到任何图片，尝试提取全部内容...")
        for r in results[:5]:
            print(f"  - 类型：{r['type']}, 页码：{r['page']}")
    else:
        print(f"✅ 共提取 {len(pictures)} 张图片:")
        for pic in pictures:
            print(f"   - {pic['text']}")
            if pic.get('caption'):
                print(f"     标题：{pic['caption']}")
            
except Exception as e:
    print(f"❌ Docling 提取失败：{e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ========== 步骤 2 & 3: 对每张图片进行 OCR + VLM ==========
print(f"\n[步骤 2/3] 初始化 VLM 后端 (OpenAI 兼容)...")
print(f"后端类型：{VLM_CONFIG['backend_type']}")
print(f"模型：{VLM_CONFIG['model']}")

try:
    extractor = ImageContentExtractor(**VLM_CONFIG)
    print("✅ VLM 加载成功")
except Exception as e:
    print(f"❌ 加载 VLM 模型失败：{e}")
    sys.exit(1)

# 处理每张图片
for i, pic in enumerate(pictures, 1):
    img_path = pic['text']
    if not img_path or not Path(img_path).exists():
        print(f"⚠️  图片不存在：{img_path}")
        continue
    
    print(f"\n[步骤 3/{3}] 处理图片 {i}/{len(pictures)}: {img_path}")
    print("-"*60)
    
    try:
        result = extractor.process_image(
            image_path=img_path,
            prompt="请详细描述这张架构图的内容，包括各个组件、连接关系和数据流向。",
            caption=pic.get('caption', 'PDF 中的架构图'),
            max_new_tokens=1024
        )
        
        print("\n" + "="*60)
        print(f"VLM 对图片 {i} 的描述结果:")
        print("="*60)
        print(result)
        print("="*60)
        
        # 保存结果
        result_file = OUTPUT_DIR / f"vlm_result_img_{i}.txt"
        with open(result_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"📄 结果已保存到：{result_file}")
        
    except Exception as e:
        print(f"❌ VLM 推理失败：{e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*60)
print("✅ 测试完成！")
print("="*60)
