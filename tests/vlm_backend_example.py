"""
VLM 后端使用示例
"""

from smartcard_kb.image_processor import ImageContentExtractor


def example_use_openai_backend():
    """使用 OpenAI 兼容后端（DashScope）"""
    extractor = ImageContentExtractor(
        backend_type="openai",
        api_key="sk-sp-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        base_url="https://coding-intl.dashscope.aliyuncs.com/v1",
        model="qwen-vl-max"
    )
    result = extractor.process_image("output/pictures/picture_0001.png", "请分析这张图片")
    print(result)


def example_use_local_backend():
    """使用本地后端"""
    extractor = ImageContentExtractor(
        backend_type="local",
        model_path=r"D:\softdata\workspaces\ai-models\Qwen3-VL-8B-Instruct"
    )
    result = extractor.process_image("output/pictures/picture_0001.png", "请分析这张图片")
    print(result)


if __name__ == "__main__":
    example_use_openai_backend()
    # example_use_local_backend()
