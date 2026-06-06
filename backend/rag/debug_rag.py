from backend.rag.store import VectorStore

s = VectorStore()

# Test direct source search
print("Testing search_by_source for 'Chapter 14':")
results = s.search_by_source("Chapter 14", top_k=5)
print(f"Results: {len(results)}")
for r in results:
    print(f"  Source: {r['source']}")
    print(f"  Text: {r['text'][:100]}")
    print()

# Also check what sources exist in DB with "14"
print("\nAll chunks with '14' in source:")
all_results = s._collection.get(include=["metadatas"])
sources_with_14 = set(m["source"] for m in all_results["metadatas"] if "14" in m["source"])
print(sources_with_14)