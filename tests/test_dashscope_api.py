"""测试 DashScope API 连通性"""

from openai import OpenAI

# 测试多个 URL
urls_to_test = [
    "https://coding.dashscope.aliyuncs.com/v1",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "https://coding-intl.dashscope.aliyuncs.com/v1",
]

api_key = "sk-sp-f96cee541da34d40b685a41c4755f219"
model = "qwen3.7-plus"

print(f"API Key: {api_key[:15]}...")
print(f"Model: {model}")
print()

for url in urls_to_test:
    print(f"{'='*60}")
    print(f"测试 URL: {url}")
    print(f"{'='*60}")
    
    client = OpenAI(api_key=api_key, base_url=url, timeout=30)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "你好"}],
            max_tokens=20
        )
        print(f"✅ 成功! 回复: {response.choices[0].message.content}")
        break
    except Exception as e:
        print(f"❌ 失败: {str(e)[:100]}")
    print()
