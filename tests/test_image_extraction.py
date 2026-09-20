"""测试图片内容提取模块 (OCR + VLM)"""

import pytest
from pathlib import Path
from smartcard_kb.image_processor import ImageContentExtractor


def test_image_extraction_with_ocr_and_vlm():
    """测试使用 OCR 空间坐标结合 VLM 提取图片内容"""
    
    # ================= 配置区 =================
    # 本地模型路径
    VLM_MODEL_PATH = r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct"
    
    # 本地图片路径 (请替换为实际存在的 .jpg 或 .png 文件)
    IMAGE_PATH = r"替换为你的本地图片路径.jpg"
    
    # 提示词
    PROMPT = "请根据图片内容和提供的文字坐标，分析这张图片中的业务流程。"
    
    # 图片描述 (可选)
    CAPTION = "一张关于用户申请流程的示意图。"
    # ==========================================

    if not Path(VLM_MODEL_PATH).exists():
        pytest.skip(f"本地模型路径不存在: {VLM_MODEL_PATH}")
        
    if not Path(IMAGE_PATH).exists():
        pytest.skip(f"测试图片路径不存在: {IMAGE_PATH}。请在代码中修改 IMAGE_PATH 变量。")

    print(f"\n[1/3] 初始化提取器 (模型: {VLM_MODEL_PATH})...")
    extractor = ImageContentExtractor(vlm_model_path=VLM_MODEL_PATH)
    
    print(f"[2/3] 开始处理图片: {IMAGE_PATH}")
    try:
        result = extractor.process_image(
            image_path=IMAGE_PATH,
            prompt=PROMPT,
            caption=CAPTION,
            max_new_tokens=512
        )
        
        print("[3/3] 推理完成！")
        print("\n" + "="*50)
        print("🤖 VLM 最终输出:")
        print("="*50)
        print(result)
        print("="*50)
        
        assert result is not None
        assert len(result) > 0
        
    except Exception as e:
        pytest.fail(f"推理过程中发生错误: {str(e)}")


if __name__ == "__main__":
    test_image_extraction_with_ocr_and_vlm()
