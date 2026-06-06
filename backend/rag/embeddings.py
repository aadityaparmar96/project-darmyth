# =============================================================
#  Darmyth — backend/rag/embeddings.py
#  Reads notes from Obsidian vault, chunks them, embeds them
#  Model: all-MiniLM-L6-v2 (~80MB, fast, good quality)
# =============================================================

import os
import yaml
from pathlib import Path
from sentence_transformers import SentenceTransformer

# ── Load settings ─────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parents[2]
YAML_PATH = BASE_DIR / "config" / "settings.yaml"

with open(YAML_PATH, "r") as f:
    SETTINGS = yaml.safe_load(f)

NOTES_PATH      = Path(SETTINGS["memory"]["notes_path"])
FILE_TYPES      = SETTINGS["memory"]["file_types"]
EXCLUDE_FOLDERS = SETTINGS["memory"]["exclude_folders"]

# ── Embedding model ───────────────────────────────────────────
MODEL_NAME = "all-MiniLM-L6-v2"
_model     = None

def get_model() -> SentenceTransformer:
    """Load embedding model once, reuse after."""
    global _model
    if _model is None:
        print(f"[embeddings] Loading {MODEL_NAME}...")
        _model = SentenceTransformer(MODEL_NAME)
        print("[embeddings] Model ready.")
    return _model


# ── File reading ──────────────────────────────────────────────
def read_vault(notes_path: Path = NOTES_PATH) -> list[dict]:
    """
    Walk the Obsidian vault and read all .md/.txt files.
    Returns list of {path, filename, content} dicts.
    """
    documents = []

    if not notes_path.exists():
        print(f"[embeddings] Vault not found: {notes_path}")
        return documents

    for root, dirs, files in os.walk(notes_path):
        # Skip excluded folders
        dirs[:] = [d for d in dirs if d not in EXCLUDE_FOLDERS]

        for file in files:
            if any(file.endswith(ext) for ext in FILE_TYPES):
                filepath = Path(root) / file
                try:
                    content = filepath.read_text(encoding="utf-8").strip()
                    if content:
                        documents.append({
                            "path":     str(filepath),
                            "filename": file,
                            "content":  content,
                        })
                except Exception as e:
                    print(f"[embeddings] Could not read {file}: {e}")

    print(f"[embeddings] Found {len(documents)} notes in vault.")
    return documents


# ── Chunking ──────────────────────────────────────────────────
def chunk_document(doc: dict,
                   chunk_size: int = 250,
                   overlap: int = 30) -> list[dict]:
    """
    Split a document into overlapping chunks.
    Small chunks = more precise retrieval.

    Args:
        doc: document dict with 'content', 'filename', 'path'
        chunk_size: characters per chunk
        overlap: characters of overlap between chunks

    Returns:
        List of chunk dicts with text, source, chunk_id
    """
    content  = doc["content"]
    chunks   = []
    start    = 0
    chunk_id = 0

    while start < len(content):
        end   = start + chunk_size
        chunk = content[start:end]

        # Try to break at sentence boundary
        if end < len(content):
            last_period = chunk.rfind('.')
            last_newline = chunk.rfind('\n')
            break_point = max(last_period, last_newline)
            if break_point > chunk_size // 2:
                chunk = content[start:start + break_point + 1]
                end   = start + break_point + 1

        chunks.append({
            "text":     chunk.strip(),
            "source":   doc["filename"],
            "path":     doc["path"],
            "chunk_id": f"{doc['filename']}_{chunk_id}",
        })
        chunk_id += 1
        start = end - overlap

    return [c for c in chunks if len(c["text"]) > 20]


def chunk_all(documents: list[dict]) -> list[dict]:
    """Chunk all documents."""
    all_chunks = []
    for doc in documents:
        all_chunks.extend(chunk_document(doc))
    print(f"[embeddings] Created {len(all_chunks)} chunks from {len(documents)} notes.")
    return all_chunks


# ── Embedding ─────────────────────────────────────────────────
def embed_chunks(chunks: list[dict]) -> tuple[list, list, list]:
    """
    Embed all chunks using MiniLM.

    Returns:
        (texts, embeddings, metadatas) — ready for ChromaDB
    """
    model  = get_model()
    texts  = [c["text"] for c in chunks]
    ids    = [c["chunk_id"] for c in chunks]
    metas  = [{"source": c["source"], "path": c["path"]} for c in chunks]

    print(f"[embeddings] Embedding {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
    print("[embeddings] Done.")

    return texts, embeddings.tolist(), metas, ids


# ── Single text embedding (for queries) ───────────────────────
def embed_query(text: str) -> list:
    """Embed a single query string for retrieval."""
    model = get_model()
    return model.encode(text).tolist()


# ── Quick test ────────────────────────────────────────────────
if __name__ == "__main__":
    print("Testing Darmyth embeddings...\n")

    docs   = read_vault()
    if not docs:
        print("No notes found — check your vault path in settings.yaml")
        exit(1)

    chunks = chunk_all(docs)
    print(f"\nSample chunk:\n{chunks[0]['text'][:200]}\n")

    texts, embeddings, metas, ids = embed_chunks(chunks[:3])
    print(f"\nEmbedding shape: {len(embeddings[0])} dimensions")
    print("Embeddings working correctly!")