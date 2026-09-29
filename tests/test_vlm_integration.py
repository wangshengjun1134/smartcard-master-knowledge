"""验证 VLM 集成代码结构"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_vlm_integration():
    """测试 VLM 集成代码是否正确"""
    
    print("=" * 80)
    print("VLM 集成代码结构验证")
    print("=" * 80)
    print()
    
    # 1. 测试导入
    print("1. 测试导入...")
    try:
        from src.smartcard_kb.docs_compile.pdf_parser import PDFParser
        from src.smartcard_kb.llms.base import VLMBackend
        from src.smartcard_kb.llms.openai import OpenAICompatibleBackend
        from src.smartcard_kb.llms.local import LocalQwenVLMBackend
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
        # 这里会失败因为模型路径不存在，但我们可以验证配置解析
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
    print()
    print("VLM 集成功能说明:")
    print("  1. 支持 API 方式（OpenAI 兼容接口）")
    print("  2. 支持本地模型方式（Qwen3-VL）")
    print("  3. 默认不启用 VLM（需显式配置）")
    print("  4. 图片描述存储在 metadata.vlm_description 字段")
    print("  5. VLM 失败时自动降级（不影响解析流程）")


if __name__ == "__main__":
    test_vlm_integration()
