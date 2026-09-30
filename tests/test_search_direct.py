"""直接测试 SearchService"""

from smartcard_kb.docs_compile.search_service import SearchService

print("初始化 SearchService...")
try:
    service = SearchService()
    print("SearchService 初始化成功")
    
    print("\n执行检索...")
    result = service.search(
        query="eUICC architecture",
        search_type="hybrid",
        top_k=5,
        rerank_top_k=3,
        threshold=0.1,
        enable_rerank=True,
    )
    
    print(f"查询: {result['query']}")
    print(f"结果数: {result['total']}")
    print(f"是否重排: {result['reranked']}")
    
    for i, r in enumerate(result['results'][:3], 1):
        print(f"\n结果 {i}:")
        print(f"  Score: {r['score']:.4f}")
        print(f"  Chunk: {r['chunk_index']}")
        print(f"  Pages: {r['page_nos']}")
        print(f"  Text: {r['text'][:100]}...")
        
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
