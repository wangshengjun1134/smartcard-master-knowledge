"""测试 VLM 图片描述功能"""

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


def test_vlm_description():
    """测试 VLM 图片描述功能"""
    
    # 测试文件路径
    pdf_path = "specs/03-management-provisioning/gsma/SGP.22_v2.1.pdf"
    document_id = "SGP.22_v2.1_vlm_test"
    
    print("=" * 80)
    print("VLM 图片描述功能测试")
    print("=" * 80)
    print(f"PDF 文件: {pdf_path}")
    print(f"文档 ID: {document_id}")
    print(f"页面范围: 1-5")
    print()
    
    # 清理旧数据
    print("清理旧数据...")
    delete_document_items_by_document(document_id)
    print()
    
    # 配置 VLM（使用 API 方式）
    vlm_config = {
        "backend_type": os.getenv("VLM_BACKEND_TYPE", "openai"),
        "openai_api_key": os.getenv("VLM_API_KEY", ""),
        "openai_base_url": os.getenv("VLM_API_BASE_URL", ""),
        "openai_model": os.getenv("VLM_MODEL", "qwen-vl-max"),
    }
    
    print(f"VLM 配置:")
    print(f"  - 后端类型: {vlm_config['backend_type']}")
    print(f"  - 模型: {vlm_config.get('openai_model', 'N/A')}")
    print()
    
    # 初始化解析器（启用 VLM）
    print("初始化 PDFParser（包含 VLM）...")
    parser = PDFParser(
        do_ocr=True,
        max_tokens=512,
        tokenizer_name="BAAI/bge-m3",
        vlm_config=vlm_config,
    )
    print()
    
    # 解析 PDF（仅前 5 页）
    print("开始解析 PDF（前 5 页）...")
    result = parser.parse_pdf(
        pdf_path=pdf_path,
        document_id=document_id,
        page_range=(1, 5),
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
    
    print("=" * 80)
    print("测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_vlm_description()
