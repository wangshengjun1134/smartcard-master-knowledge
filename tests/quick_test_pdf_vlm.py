"""
快速测试：从 PDF 第 32 页提取图片并调用 VLM 描述
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import fitz
from pathlib import Path
from smartcard_kb.image_processor import ImageContentExtractor

# 配置
PDF_PATH = "specs/03-management-provisioning/gsma/SGP.01-v1.12.pdf"
PAGE_NUMBER = 32
VLM_MODEL_PATH = r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct"
OUTPUT_DIR = Path("output/pdf_page_32")

print("="*60)
print("PDF 图片提取 + OCR + VLM 描述测试")
print("="*60)

# 步骤 1: 检查文件
if not Path(PDF_PATH).exists():
    print(f"PDF 文件不存在：{PDF_PATH}")
    sys.exit(1)

if not Path(VLM_MODEL_PATH).exists():
    print(f"VLM 模型路径不存在：{VLM_MODEL_PATH}")
    sys.exit(1)

# 步骤 2: 从 PDF 提取图片
print(f"\n[1/4] 从 PDF 第{PAGE_NUMBER}页提取图片...")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

doc = fitz.open(PDF_PATH)
page = doc[PAGE_NUMBER - 1]
image_info_list = page.get_images(full=True)

print(f"找到 {len(image_info_list)} 张图片")

image_paths = []
for i, img_info in enumerate(image_info_list):
    xref = img_info[0]
    try:
        base_image = doc.extract_image(xref)
        if base_image:
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            output_path = OUTPUT_DIR / f"page_{PAGE_NUMBER}_img_{i+1}.{image_ext}"
            with open(output_path, "wb") as f:
                f.write(image_bytes)
            image_paths.append(str(output_path))
            print(f"  ✅ 保存图片：{output_path}")
    except Exception as e:
        print(f"  ❌ 提取失败：{e}")

# 如果没找到图片，渲染页面为截图
if not image_paths:
    print("未找到嵌入图片，渲染页面为截图...")
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    page_image_path = OUTPUT_DIR / f"page_{PAGE_NUMBER}_full.png"
    pix.save(str(page_image_path))
    image_paths = [str(page_image_path)]
    print(f"  ✅ 保存页面截图：{page_image_path}")

doc.close()

# 步骤 3: 初始化 VLM
print(f"\n[2/4] 初始化 VLM 模型...")
try:
    extractor = ImageContentExtractor(vlm_model_path=VLM_MODEL_PATH)
    print("  ✅ VLM 加载成功")
except Exception as e:
    print(f"   VLM 加载失败：{e}")
    sys.exit(1)

# 步骤 4: 处理每张图片
CAPTION = "GSMA SGP.01 规范中的 Integrated eUICC with USB CCID 测试接口架构图"
PROMPT = """请详细描述这张架构图的内容，包括：
1. 图中包含哪些主要组件和模块？
2. 各组件之间的连接关系和数据流向是什么？
3. 标注了哪些测试接口（如 ES9+, ES10a/b/c, ES11 等）？
4. 这个架构图的整体用途是什么？

请结合图中的文字标签、箭头方向、框线颜色等进行详细分析。"""

for i, img_path in enumerate(image_paths, 1):
    print(f"\n[3/4] 处理图片 {i}/{len(image_paths)}: {img_path}")
    print("-"*60)
    
    try:
        result = extractor.process_image(
            image_path=img_path,
            prompt=PROMPT,
            caption=CAPTION,
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
