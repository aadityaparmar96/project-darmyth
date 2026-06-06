# =============================================================
#  Darmyth — backend/rag/store.py
#  ChromaDB vector store — persists embeddings locally
# =============================================================

import yaml
import chromadb
from pathlib import Path
from backend.rag.embeddings import (
    read_vault, chunk_all, embed_chunks, embed_query
)

# ── Load settings ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
YAML_PATH = BASE_DIR / "config" / "settings.yaml"

with open(YAML_PATH, "r") as f:
    SETTINGS = yaml.safe_load(f)

DB_PATH = BASE_DIR / SETTINGS["memory"]["db_path"]
TOP_K   = SETTINGS["memory"]["top_k_chunks"]


class VectorStore:
    COLLECTION_NAME = "darmyth_notes"

    def __init__(self):
        DB_PATH.mkdir(parents=True, exist_ok=True)
        self._client     = chromadb.PersistentClient(path=str(DB_PATH))
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        print(f"[store] ChromaDB ready — {self._collection.count()} chunks stored.")

    def index_vault(self, force: bool = False) -> int:
        existing = self._collection.count()
        if existing > 0 and not force:
            print(f"[store] Already indexed ({existing} chunks). Use force=True to re-index.")
            return existing

        # Clear existing
        if existing > 0:
            self._client.delete_collection(self.COLLECTION_NAME)
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )

        docs   = read_vault()
        if not docs:
            print("[store] No notes found to index.")
            return 0

        chunks = chunk_all(docs)
        texts, embeddings, metas, ids = embed_chunks(chunks)

        # Store in batches of 100
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            self._collection.add(
                documents=texts[i:i+batch_size],
                embeddings=embeddings[i:i+batch_size],
                metadatas=metas[i:i+batch_size],
                ids=ids[i:i+batch_size],
            )

        count = self._collection.count()
        print(f"[store] Indexed {count} chunks into ChromaDB.")
        return count

    def update_file(self, filepath: str) -> None:
        from pathlib import Path as P
        from backend.rag.embeddings import chunk_document, embed_chunks

        path = P(filepath)
        if not path.exists():
            return

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return

        doc    = {"path": str(path), "filename": path.name, "content": content}
        chunks = chunk_document(doc)
        if not chunks:
            return

        texts, embeddings, metas, ids = embed_chunks(chunks)

        # Delete old chunks for this file
        try:
            existing = self._collection.get(where={"source": path.name})
            if existing["ids"]:
                self._collection.delete(ids=existing["ids"])
        except Exception:
            pass

        # Add new chunks
        self._collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metas,
            ids=ids,
        )
        print(f"[store] Updated: {path.name} ({len(chunks)} chunks)")

    def search(self, query: str, top_k: int = TOP_K) -> list[dict]:
        if self._collection.count() == 0:
            return []

        query_embedding = embed_query(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"]
        )

        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            chunks.append({
                "text":   doc,
                "source": results["metadatas"][0][i]["source"],
                "score":  1 - results["distances"][0][i],
            })

        return chunks

    def count(self) -> int:
        return self._collection.count()


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Darmyth vector store...\n")

    store = VectorStore()
    store.index_vault(force=True)

    print(f"\nTotal chunks: {store.count()}\n")

    test_queries = [
        "What is Kael's home planet?", 
        "What does India think about the policy?", 
        "Where did kael destroy the gem?",
    ]

    for query in test_queries:
        print(f"Query: {query}")
        results = store.search(query, top_k=2)
        for r in results:
            print(f"  [{r['score']:.2f}] {r['source']}: {r['text'][:100]}...")
        print()