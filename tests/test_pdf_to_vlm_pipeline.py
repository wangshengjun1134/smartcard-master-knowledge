"""
端到端测试：从 PDF 提取图片 → OCR → VLM 描述
测试 SGP.01-v1.12.pdf 第 32 页的架构图
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
from smartcard_kb.pdf_image_extractor import extract_and_save_images
from smartcard_kb.image_processor import ImageContentExtractor


def test_pdf_image_extraction_and_vlm_description():
    """
    完整测试流程：
    1. 从 PDF 第 32 页提取图片
    2. 使用 OCR 提取文字及坐标
    3. 调用 VLM 描述图片内容
    """
    
    # ================= 配置 =================
    PDF_PATH = "specs/03-management-provisioning/gsma/SGP.01-v1.12.pdf"
    PAGE_NUMBER = 32  # 目标页码
    VLM_MODEL_PATH = r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct"
    OUTPUT_DIR = "output/pdf_page_32"
    
    # 针对 eUICC 架构图的提示词
    CAPTION = "GSMA SGP.01 规范中的 Integrated eUICC with USB CCID 测试接口架构图"
    
    PROMPT = """请详细描述这张架构图的内容，包括：
1. 图中包含哪些主要组件和模块？
2. 各组件之间的连接关系和数据流向是什么？
3. 标注了哪些测试接口（如 ES9+, ES10a/b/c, ES11 等）？
4. 这个架构图的整体用途是什么？

请结合图中的文字标签、箭头方向、框线颜色等进行详细分析。"""
    # ==========================================

    print("="*60)
    print("📋 端到端测试：PDF 图片提取 + OCR + VLM 描述")
    print("="*60)
    
    # 检查文件是否存在
    if not Path(PDF_PATH).exists():
        print(f"❌ PDF 文件不存在: {PDF_PATH}")
        return
    
    if not Path(VLM_MODEL_PATH).exists():
        print(f"❌ VLM 模型路径不存在: {VLM_MODEL_PATH}")
        return
    
    # ========== 步骤 1: 从 PDF 提取图片 ==========
    print(f"\n[步骤 1/3] 从 PDF 第 {PAGE_NUMBER} 页提取图片...")
    print(f"PDF 路径：{PDF_PATH}")
    
    try:
        image_paths = extract_and_save_images(PDF_PATH, PAGE_NUMBER, OUTPUT_DIR)
        
        if not image_paths:
            print("⚠️  未找到任何图片，尝试截取整个页面作为图片...")
            # 备选方案：渲染页面为图片
            import fitz
            doc = fitz.open(PDF_PATH)
            page = doc[PAGE_NUMBER - 1]
            mat = fitz.Matrix(2.0, 2.0)  # 2x 缩放
            pix = page.get_pixmap(matrix=mat)
            page_image_path = Path(OUTPUT_DIR) / f"page_{PAGE_NUMBER}_full.png"
            pix.save(str(page_image_path))
            image_paths = [str(page_image_path)]
            print(f"✅ 保存页面截图：{page_image_path}")
            doc.close()
    except Exception as e:
        print(f"❌ 提取图片失败：{e}")
        return
    
    print(f"✅ 共提取 {len(image_paths)} 张图片")
    for img_path in image_paths:
        print(f"   - {img_path}")
    
    # ========== 步骤 2 & 3: OCR + VLM ==========
    print(f"\n[步骤 2/3] 初始化 VLM 模型 (OCR 会自动加载)...")
    print(f"模型路径：{VLM_MODEL_PATH}")
    
    try:
        extractor = ImageContentExtractor(vlm_model_path=VLM_MODEL_PATH)
    except Exception as e:
        print(f"❌ 加载 VLM 模型失败：{e}")
        return
    
    # 处理每张图片
    for i, img_path in enumerate(image_paths, 1):
        print(f"\n[步骤 3/{3}] 处理图片 {i}/{len(image_paths)}: {img_path}")
        print("-" * 60)
        
        try:
            result = extractor.process_image(
                image_path=img_path,
                prompt=PROMPT,
                caption=CAPTION,
                max_new_tokens=1024
            )
            
            print("\n" + "="*60)
            print(f"🤖 VLM 对图片 {i} 的描述结果:")
            print("="*60)
            print(result)
            print("="*60)
            
            # 保存结果到文件
            result_file = Path(OUTPUT_DIR) / f"vlm_result_img_{i}.txt"
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


if __name__ == "__main__":
    test_pdf_image_extraction_and_vlm_description()
