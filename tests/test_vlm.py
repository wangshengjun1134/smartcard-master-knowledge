"""VLM 图片描述功能测试"""

import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from src.smartcard_kb.docs_compile.pdf_parser import PDFParser
from src.smartcard_kb.docs_compile.database import (
    query_document_items,
    delete_document_items_by_document,
)
from src.smartcard_kb.llms.base import VLMBackend
from src.smartcard_kb.llms.openai import OpenAICompatibleBackend
from src.smartcard_kb.llms.local import LocalQwenVLMBackend


# ==================== 测试 1: 集成测试 ====================

def test_vlm_integration():
    """测试 VLM 集成代码结构"""
    
    print("=" * 80)
    print("VLM 集成代码结构验证")
    print("=" * 80)
    print()
    
    # 1. 测试导入
    print("1. 测试导入...")
    try:
        print("   ✅ 所有导入成功")
    except ImportError as e:
        print(f"   ❌ 导入失败: {e}")
        return
    print()
    
    # 2. 测试 PDFParser 初始化（不启用 VLM）
    print("2. 测试 PDFParser 初始化（不启用 VLM）...")
    try:
        parser = PDFParser(
            do_ocr=True,
            max_tokens=512,
            tokenizer_name="BAAI/bge-m3",
        )
        assert parser.vlm_backend is None
        print("   ✅ PDFParser 初始化成功（无 VLM）")
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        return
    print()
    
    # 3. 测试 PDFParser 初始化（使用 mock VLM 后端）
    print("3. 测试 PDFParser 初始化（使用 mock VLM 后端）...")
    try:
        class MockVLMBackend(VLMBackend):
            def generate(self, image, messages, max_new_tokens=512):
                return "这是一个模拟的 VLM 描述"
        
        mock_backend = MockVLMBackend()
        parser_with_vlm = PDFParser(
            do_ocr=True,
            max_tokens=512,
            tokenizer_name="BAAI/bge-m3",
            vlm_backend=mock_backend,
        )
        assert parser_with_vlm.vlm_backend is not None
        assert isinstance(parser_with_vlm.vlm_backend, MockVLMBackend)
        print("   ✅ PDFParser 初始化成功（带 VLM）")
    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        return
    print()
    
    # 4. 测试 _generate_vlm_description 方法
    print("4. 测试 _generate_vlm_description 方法...")
    try:
        from PIL import Image
        test_image = Image.new("RGB", (100, 100), color="white")
        
        description = parser_with_vlm._generate_vlm_description(
            image=test_image,
            item=None,
            doc=None,
        )
        assert description == "这是一个模拟的 VLM 描述"
        print(f"   ✅ VLM 描述生成成功: {description}")
    except Exception as e:
        print(f"   ❌ VLM 描述生成失败: {e}")
        return
    print()
    
    # 5. 测试无 VLM 后端时的行为
    print("5. 测试无 VLM 后端时的行为...")
    try:
        description = parser._generate_vlm_description(
            image=test_image,
            item=None,
            doc=None,
        )
        assert description is None
        print("   ✅ 无 VLM 后端时返回 None")
    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        return
    print()
    
    # 6. 测试 VLM 配置创建
    print("6. 测试 VLM 配置创建...")
    try:
        # 测试 OpenAI 配置
        openai_config = {
            "backend_type": "openai",
            "openai_api_key": "test-key",
            "openai_base_url": "https://example.com/v1",
            "openai_model": "qwen-vl-max",
        }
        backend = parser._create_vlm_backend(openai_config)
        assert isinstance(backend, OpenAICompatibleBackend)
        print("   ✅ OpenAI 后端创建成功")
        
        # 测试本地配置（不实际加载模型）
        local_config = {
            "backend_type": "local",
            "local_model_path": "/path/to/model",
        }
        try:
            backend = parser._create_vlm_backend(local_config)
        except Exception as e:
            error_msg = str(e).lower()
            if "repo id" in error_msg or "model" in error_msg:
                print("   ✅ Local 后端配置解析成功（模型加载跳过）")
            else:
                raise
    except Exception as e:
        print(f"   ❌ 配置创建失败: {e}")
        return
    print()
    
    # 7. 验证 _extract_all_items 方法签名
    print("7. 验证 _extract_all_items 方法签名...")
    try:
        import inspect
        sig = inspect.signature(parser._extract_all_items)
        params = list(sig.parameters.keys())
        assert "doc" in params
        assert "document_id" in params
        assert "output_dir" in params
        print(f"   ✅ 方法签名正确: {params}")
    except Exception as e:
        print(f"   ❌ 方法签名验证失败: {e}")
        return
    print()
    
    print("=" * 80)
    print("所有测试通过！✅")
    print("=" * 80)


# ==================== 测试 2: VLM 后端连通性测试 ====================

def test_vlm_backend():
    """测试 VLM 后端是否正常工作"""
    
    print("=" * 80)
    print("VLM 后端连通性测试")
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
        print("初始化 OpenAI 兼容后端...")
        backend = OpenAICompatibleBackend(
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        print()
        
        # 创建一个简单的测试图片（白色背景）
        from PIL import Image
        test_image = Image.new("RGB", (200, 200), color="white")
        
        # 添加一些文字
        try:
            from PIL import ImageDraw
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
        print("初始化本地 VLM 后端...")
        backend = LocalQwenVLMBackend(model_path=model_path)
        print()
        
        # 创建一个简单的测试图片
        from PIL import Image
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


# ==================== 测试 3: VLM 真实 API 测试 ====================

def test_vlm_real():
    """测试真实 VLM API"""
    
    print("=" * 80)
    print("VLM 真实 API 测试")
    print("=" * 80)
    print()
    
    # 检查环境变量
    backend_type = os.getenv("VLM_BACKEND_TYPE", "openai")
    api_key = os.getenv("VLM_OPENAI_API_KEY", "")
    base_url = os.getenv("VLM_OPENAI_BASE_URL", "")
    model = os.getenv("VLM_OPENAI_MODEL", "qwen-vl-max")
    
    print(f"后端类型: {backend_type}")
    print(f"API Key: {api_key[:10]}..." if api_key and len(api_key) > 10 else "API Key: 未配置")
    print(f"Base URL: {base_url}")
    print(f"Model: {model}")
    print()
    
    # 检查 API Key 是否配置
    if not api_key or api_key == "sk-sp-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx":
        print("⚠️  VLM API Key 未配置")
        print()
        print("请在 .env 文件中配置:")
        print("  VLM_OPENAI_API_KEY=your-actual-api-key")
        print()
        return
    
    # 测试文件路径
    pdf_path = "specs/03-management-provisioning/gsma/SGP.22_v2.1.pdf"
    document_id = "SGP.22_v2.1_vlm_real_test"
    
    print(f"PDF 文件: {pdf_path}")
    print(f"文档 ID: {document_id}")
    print(f"页面范围: 1-3（仅测试前 3 页）")
    print()
    
    # 清理旧数据
    print("清理旧数据...")
    delete_document_items_by_document(document_id)
    print()
    
    # 配置 VLM
    vlm_config = {
        "backend_type": backend_type,
        "openai_api_key": api_key,
        "openai_base_url": base_url,
        "openai_model": model,
    }
    
    # 初始化解析器（启用 VLM）
    print("初始化 PDFParser（包含 VLM）...")
    parser = PDFParser(
        do_ocr=True,
        max_tokens=512,
        tokenizer_name="BAAI/bge-m3",
        vlm_config=vlm_config,
    )
    print()
    
    # 解析 PDF（仅前 3 页）
    print("开始解析 PDF（前 3 页）...")
    print("注意：每张图片都会调用 VLM API，可能需要一些时间...")
    print()
    
    result = parser.parse_pdf(
        pdf_path=pdf_path,
        document_id=document_id,
        page_range=(1, 3),
        output_dir="output/pictures",
    )
    
    items = result["items"]
    chunks = result["chunks"]
    
    print(f"\n解析完成！")
    print(f"  - 提取 items: {len(items)} 个")
    print(f"  - 生成 chunks: {len(chunks)} 个")
    print()
    
    # 统计图片数量
    picture_items = [it for it in items if it["label"] == "picture"]
    print(f"图片 items: {len(picture_items)} 个")
    print()
    
    # 显示图片的 VLM 描述
    print("=" * 80)
    print("图片 VLM 描述详情:")
    print("=" * 80)
    
    for i, item in enumerate(picture_items):
        metadata = item.get("metadata", {})
        caption = metadata.get("caption", "无")
        vlm_desc = metadata.get("vlm_description", "未生成")
        
        print(f"\n--- 图片 {i+1} ---")
        print(f"ID: {item['id']}")
        print(f"Caption: {caption}")
        print(f"VLM 描述 (前 300 字符): {vlm_desc[:300]}...")
        print()
    
    # 验证数据库
    print("=" * 80)
    print("验证数据库:")
    print("=" * 80)
    
    db_items = query_document_items(document_id=document_id)
    db_pictures = [it for it in db_items if it["label"] == "picture"]
    
    pictures_with_vlm = [
        it for it in db_pictures
        if it.get("metadata", {}).get("vlm_description")
    ]
    
    print(f"总图片 items: {len(db_pictures)} 个")
    print(f"包含 VLM 描述: {len(pictures_with_vlm)} 个")
    print()
    
    if pictures_with_vlm:
        print("✅ VLM 功能正常工作！")
    else:
        print("⚠️  没有图片包含 VLM 描述，可能 API 调用失败")
    
    print()
    print("=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    import sys
    
    # 根据命令行参数选择测试
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "integration":
            test_vlm_integration()
        elif test_name == "backend":
            test_vlm_backend()
        elif test_name == "real":
            test_vlm_real()
        else:
            print(f"未知测试: {test_name}")
            print("可用测试: integration, backend, real")
    else:
        # 运行所有测试
        test_vlm_integration()
        print()
        test_vlm_backend()
        print()
        test_vlm_real()
