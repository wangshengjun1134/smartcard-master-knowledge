"""测试检索接口"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_search():
    """测试检索接口"""
    print("=" * 60)
    print("测试检索接口")
    print("=" * 60)
    
    # 测试 1: 混合检索 + 重排
    print("\n[测试 1] 混合检索 + 重排")
    response = requests.post(
        f"{BASE_URL}/api/search",
        json={
            "query": "eUICC architecture",
            "search_type": "hybrid",
            "top_k": 5,
            "rerank_top_k": 3,
            "threshold": 0.1,
            "enable_rerank": True,
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"  查询: {result['query']}")
        print(f"  结果数: {result['total']}")
        print(f"  是否重排: {result['reranked']}")
        for i, r in enumerate(result['results'][:3], 1):
            print(f"\n  结果 {i}:")
            print(f"    Score: {r['score']:.4f}")
            print(f"    Chunk: {r['chunk_index']}")
            print(f"    Pages: {r['page_nos']}")
            print(f"    Text: {r['text'][:100]}...")
    else:
        print(f"  错误: {response.status_code}")
        print(f"  {response.text}")
    
    # 测试 2: 纯向量检索
    print("\n[测试 2] 纯向量检索")
    response = requests.post(
        f"{BASE_URL}/api/search",
        json={
            "query": "eSIM profile installation",
            "search_type": "vector",
            "top_k": 3,
            "threshold": 0.3,
            "enable_rerank": False,
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"  查询: {result['query']}")
        print(f"  结果数: {result['total']}")
        for i, r in enumerate(result['results'][:2], 1):
            print(f"\n  结果 {i}:")
            print(f"    Score: {r['score']:.4f}")
            print(f"    Text: {r['text'][:80]}...")
    else:
        print(f"  错误: {response.status_code}")
        print(f"  {response.text}")
    
    # 测试 3: 纯关键词检索
    print("\n[测试 3] 纯关键词检索")
    response = requests.post(
        f"{BASE_URL}/api/search",
        json={
            "query": "Security Domain SD",
            "search_type": "keyword",
            "top_k": 3,
            "threshold": 0.1,
            "enable_rerank": False,
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"  查询: {result['query']}")
        print(f"  结果数: {result['total']}")
    else:
        print(f"  错误: {response.status_code}")
        print(f"  {response.text}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_search()
