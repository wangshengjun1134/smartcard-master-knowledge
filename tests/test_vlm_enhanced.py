"""Test VLM enhanced features"""

import sys
import ast
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_vlm_service_structure():
    """Test VLMService structure using AST"""
    print("Testing VLMService structure...")
    
    vlm_service_path = project_root / "src" / "smartcard_kb" / "docs_compile" / "vlm_service.py"
    with open(vlm_service_path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    # Find VLMService class
    vlm_service_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'VLMService':
            vlm_service_class = node
            break
    
    assert vlm_service_class is not None, "VLMService class not found"
    
    # Check methods
    methods = [node.name for node in vlm_service_class.body if isinstance(node, ast.FunctionDef)]
    assert 'generate_vlm_descriptions' in methods
    assert 'create_backend' in methods
    assert '_generate_vlm_description' in methods
    assert '_update_item_vlm_description' in methods
    
    print("✓ VLMService has all required methods")


def test_generate_vlm_descriptions_signature():
    """Test generate_vlm_descriptions method signature"""
    print("\nTesting generate_vlm_descriptions signature...")
    
    vlm_service_path = project_root / "src" / "smartcard_kb" / "docs_compile" / "vlm_service.py"
    with open(vlm_service_path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read())
    
    # Find the method
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'VLMService':
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == 'generate_vlm_descriptions':
                    # Check parameters
                    args = item.args
                    arg_names = [arg.arg for arg in args.args]
                    
                    assert 'document_id' in arg_names
                    assert 'output_dir' in arg_names
                    assert 'prompt' in arg_names
                    assert 'max_new_tokens' in arg_names
                    assert 'language' in arg_names
                    assert 'detail_level' in arg_names
                    
                    # Check defaults
                    defaults = args.defaults
                    assert len(defaults) >= 4  # prompt, max_new_tokens, language, detail_level
                    
                    print("✓ generate_vlm_descriptions has correct signature")
                    return
    
    raise AssertionError("generate_vlm_descriptions method not found")


def test_prompt_in_english():
    """Test that default prompts are in English"""
    print("\nTesting default prompts are in English...")
    
    vlm_service_path = project_root / "src" / "smartcard_kb" / "docs_compile" / "vlm_service.py"
    with open(vlm_service_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for English prompt
    assert 'Please describe this image in detail' in content
    assert 'Respond in English' in content
    
    print("✓ Default prompts are in English")


def test_detail_level_prompts():
    """Test that detail level prompts are in English"""
    print("\nTesting detail level prompts...")
    
    vlm_service_path = project_root / "src" / "smartcard_kb" / "docs_compile" / "vlm_service.py"
    with open(vlm_service_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for English detail prompts
    assert 'Provide concise descriptions' in content
    assert 'Provide thorough descriptions' in content
    assert 'Provide exhaustive, highly detailed descriptions' in content
    
    print("✓ Detail level prompts are in English")


def test_language_instructions():
    """Test that language instructions are in English"""
    print("\nTesting language instructions...")
    
    vlm_service_path = project_root / "src" / "smartcard_kb" / "docs_compile" / "vlm_service.py"
    with open(vlm_service_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for English language instructions
    assert 'Always respond in English' in content
    assert 'Always respond in Chinese (中文)' in content
    assert 'Always respond in Japanese (日本語)' in content
    
    print("✓ Language instructions are properly defined")


def test_api_vlm_request():
    """Test API VLMRequest model"""
    print("\nTesting API VLMRequest model...")
    
    api_path = project_root / "src" / "smartcard_kb" / "apis" / "docs_processing.py"
    with open(api_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for English prompt in VLMRequest
    assert 'prompt: str = "Please describe this image in detail' in content
    assert 'language: str = "en"' in content
    assert 'detail_level: str = "detailed"' in content
    
    print("✓ API VLMRequest has correct parameters with English prompts")


def test_backend_comments_in_english():
    """Test that backend comments are in English"""
    print("\nTesting backend comments...")
    
    # Check vlm_base.py
    vlm_base_path = project_root / "src" / "smartcard_kb" / "llms" / "vlm_base.py"
    with open(vlm_base_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert 'VLM Backend Abstract Base Class' in content
    assert 'Call VLM to generate response' in content
    
    # Check vlm_openai.py
    vlm_openai_path = project_root / "src" / "smartcard_kb" / "llms" / "vlm_openai.py"
    with open(vlm_openai_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert 'OpenAI Compatible API Backend' in content
    assert 'Call OpenAI compatible API to generate response' in content
    
    # Check vlm_local.py
    vlm_local_path = project_root / "src" / "smartcard_kb" / "llms" / "vlm_local.py"
    with open(vlm_local_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    assert 'Local Qwen3-VL Model Backend' in content
    assert 'Call local VLM to generate response' in content
    
    print("✓ All backend comments are in English")


if __name__ == "__main__":
    print("="*60)
    print("VLM Enhanced Features Test Suite")
    print("="*60)
    
    test_vlm_service_structure()
    test_generate_vlm_descriptions_signature()
    test_prompt_in_english()
    test_detail_level_prompts()
    test_language_instructions()
    test_api_vlm_request()
    test_backend_comments_in_english()
    
    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60)
