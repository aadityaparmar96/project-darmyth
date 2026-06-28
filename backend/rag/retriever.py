# =============================================================
#  Darmyth — backend/rag/retriever.py
#  Retrieves relevant context from vault for brain.py
#  Formats chunks into a clean context string
# =============================================================

# =============================================================
#  Darmyth — backend/rag/retriever.py
#  Retrieves relevant context from vault for brain.py
#  Includes keyword boost for chapter/file specific queries
# =============================================================

# =============================================================
#  Darmyth — backend/rag/retriever.py
#  Retrieves relevant context from vault for brain.py
#  Includes keyword boost for chapter/file specific queries
# =============================================================

# =============================================================
#  Darmyth — backend/rag/retriever.py
#  Retrieves relevant context from vault for brain.py
#  Chapter queries use direct filename filter, not semantic search
# =============================================================

import re
import yaml
from pathlib import Path
from backend.rag.store import VectorStore

# ── Load settings ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
YAML_PATH = BASE_DIR / "config" / "settings.yaml"

with open(YAML_PATH, "r") as f:
    SETTINGS = yaml.safe_load(f)

TOP_K = SETTINGS["memory"]["top_k_chunks"]

# ── Singleton store ───────────────────────────────────────────
_store = None

def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store


# ── Retriever ─────────────────────────────────────────────────
def retrieve(query: str,
             top_k: int = TOP_K,
             min_score: float = 0.40) -> str:
    """
    Find relevant notes for a query and return as context string.
    Chapter queries bypass semantic search and use direct filename filter.
    """
    store = get_store()

    # ── Chapter keyword — direct filename filter ──────────────
    chapter_match = re.search(r'chapter\s+(\d+)', query, re.IGNORECASE)
    if chapter_match:
        chapter_num = chapter_match.group(1)
        results = store.search_by_source(f"Chapter {chapter_num}", top_k=top_k)
        if results:
            print(f"[retriever] Chapter {chapter_num} direct match — {len(results)} chunks")
        else:
            # Fallback to semantic if no direct match
            print(f"[retriever] No direct match for Chapter {chapter_num}, falling back to semantic")
            candidates = store.search(query, top_k=top_k * 2)
            results    = [r for r in candidates if r["score"] >= min_score][:top_k]
    else:
        # Normal semantic search
        candidates = store.search(query, top_k=top_k * 3)
        results    = [r for r in candidates if r["score"] >= min_score][:top_k]

    if not results:
        return ""

    lines = []
    for r in results:
        lines.append(f"[From: {r['source']}]\n{r['text']}")

    context = "\n\n".join(lines)
    print(f"[retriever] Found {len(results)} chunks for: '{query[:50]}'")
    return context


def index_vault(force: bool = False) -> int:
    return get_store().index_vault(force=force)


def update_file(filepath: str) -> None:
    get_store().update_file(filepath)


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Darmyth retriever...\n")

    count = index_vault()
    print(f"Indexed {count} chunks\n")

    queries = [
        "What is Aaditya working on?",
        "What happens in Chapter 14?",
        "What does India think of R2P?",
        "What is the weather today?",
    ]

    for q in queries:
        print(f"Q: {q}")
        context = retrieve(q)
        if context:
            print(f"Context:\n{context[:200]}...")
        else:
            print("No relevant context found.")
        print()