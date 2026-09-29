"""测试 VLM 图片描述功能（简化版）"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()


def test_vlm_backend():
    """测试 VLM 后端是否正常工作"""
    
    print("=" * 80)
    print("VLM 后端测试")
    print("=" * 80)
    print()
    
    # 配置 VLM
    backend_type = os.getenv("VLM_BACKEND_TYPE", "openai")
    print(f"后端类型: {backend_type}")
    
    if backend_type == "openai":
        api_key = os.getenv("VLM_OPENAI_API_KEY", "")
        base_url = os.getenv("VLM_OPENAI_BASE_URL", "")
        model = os.getenv("VLM_OPENAI_MODEL", "qwen-vl-max")
        
        print(f"API Key: {api_key[:10]}..." if api_key else "API Key: 未配置")
        print(f"Base URL: {base_url}")
        print(f"Model: {model}")
        print()
        
        if not api_key or api_key == "sk-sp-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx":
            print("⚠️  VLM API Key 未配置，跳过 API 测试")
            print("请在 .env 文件中配置正确的 VLM_OPENAI_API_KEY")
            return
        
        # 测试 API 后端
        from src.smartcard_kb.llms.openai import OpenAICompatibleBackend
        from PIL import Image
        import io
        
        print("初始化 OpenAI 兼容后端...")
        backend = OpenAICompatibleBackend(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        print()
        
        # 创建一个简单的测试图片（白色背景）
        test_image = Image.new("RGB", (200, 200), color="white")
        
        # 添加一些文字
        try:
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(test_image)
            draw.text((50, 80), "Hello VLM", fill="black")
        except Exception:
            pass
        
        print("发送测试请求...")
        messages = [
            {
                "role": "system",
                "content": "你是一个图像识别助手。",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": test_image},
                    {"type": "text", "text": "请描述这张图片的内容。"},
                ],
            },
        ]
        
        try:
            response = backend.generate(
                image=test_image,
                messages=messages,
                max_new_tokens=256,
            )
            print(f"✅ VLM 响应: {response}")
        except Exception as e:
            print(f"❌ VLM 请求失败: {e}")
            
    elif backend_type == "local":
        model_path = os.getenv("VLM_LOCAL_MODEL_PATH", "")
        print(f"模型路径: {model_path}")
        print()
        
        if not model_path or not Path(model_path).exists():
            print("⚠️  本地模型路径不存在，跳过本地测试")
            print(f"路径: {model_path}")
            return
        
        # 测试本地后端
        from src.smartcard_kb.llms.local import LocalQwenVLMBackend
        from PIL import Image
        
        print("初始化本地 VLM 后端...")
        backend = LocalQwenVLMBackend(model_path=model_path)
        print()
        
        # 创建一个简单的测试图片
        test_image = Image.new("RGB", (200, 200), color="white")
        
        print("发送测试请求...")
        messages = [
            {
                "role": "system",
                "content": "你是一个图像识别助手。",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": test_image},
                    {"type": "text", "text": "请描述这张图片的内容。"},
                ],
            },
        ]
        
        try:
            response = backend.generate(
                image=test_image,
                messages=messages,
                max_new_tokens=256,
            )
            print(f"✅ VLM 响应: {response}")
        except Exception as e:
            print(f"❌ VLM 请求失败: {e}")
    
    print()
    print("=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_vlm_backend()
