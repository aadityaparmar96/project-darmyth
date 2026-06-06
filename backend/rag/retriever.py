# =============================================================
#  Darmyth — backend/rag/retriever.py
#  Retrieves relevant context from vault for brain.py
#  Formats chunks into a clean context string
# =============================================================

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
             min_score: float = 0.35) -> str:
    """
    Find relevant notes for a query and return as context string.

    Args:
        query: user's question or message
        top_k: number of chunks to retrieve
        min_score: minimum similarity score (0-1) to include

    Returns:
        Formatted context string, or empty string if nothing relevant
    """
    store   = get_store()
    results = store.search(query, top_k=top_k)

    # Filter by minimum relevance score
    relevant = [r for r in results if r["score"] >= min_score]

    if not relevant:
        return ""

    # Format into clean context block
    lines = []
    for r in relevant:
        lines.append(f"[From: {r['source']}]\n{r['text']}")

    context = "\n\n".join(lines)
    print(f"[retriever] Found {len(relevant)} relevant chunks for: '{query[:50]}'")
    return context


def index_vault(force: bool = False) -> int:
    """Index or re-index the Obsidian vault."""
    return get_store().index_vault(force=force)


def update_file(filepath: str) -> None:
    """Update a single file in the vector store."""
    get_store().update_file(filepath)


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Darmyth retriever...\n")

    print("Indexing vault...")
    count = index_vault()
    print(f"Indexed {count} chunks\n")

    queries = [
        "What was the name of the Hegemony that Kael destroyed?",
        "What is Panama's view on the policy?",
        "What does india think of R2P?",
        "What is the weather today?",   # should return nothing relevant
    ]

    for q in queries:
        print(f"Q: {q}")
        context = retrieve(q)
        if context:
            print(f"Context found:\n{context[:200]}...")
        else:
            print("No relevant context found.")
        print()