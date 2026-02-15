"""Local FAISS vector search over policy corpus.

Provides offline policy retrieval without requiring the Nehanda RAG API.
Uses sentence-transformers for embeddings and FAISS for similarity search.
"""

import json
import os
import logging
from typing import List, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)

# Default embedding dimension (all-MiniLM-L6-v2)
_EMBEDDING_DIM = 384

# Cached model reference
_model = None


def nehanda_query(query: str, top_k: int = 5, corpus_dir: str = "") -> str:
    """Search local policy corpus using vector similarity.

    Args:
        query: Search query text.
        top_k: Number of top results to return.
        corpus_dir: Directory containing .txt policy documents.

    Returns:
        JSON string ``{results: [{text, source, score}], query, count}``
        or ``"Error: <description>"`` on failure.
    """
    if not query or not query.strip():
        return "Error: Empty query"

    if not corpus_dir:
        return "Error: No corpus directory configured"

    if not os.path.isdir(corpus_dir):
        return f"Error: Corpus directory not found — {corpus_dir}"

    # Load and chunk documents
    chunks = _load_corpus(corpus_dir)
    if not chunks:
        return "Error: No documents found in corpus directory"

    try:
        # Build index
        index, chunk_list = _build_index(chunks)

        # Query
        query_embedding = _get_embeddings([query])
        distances, indices = index.search(query_embedding, min(top_k, len(chunk_list)))

        # Format results
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < 0 or idx >= len(chunk_list):
                continue
            chunk = chunk_list[idx]
            score = float(1.0 / (1.0 + dist))  # Convert L2 distance to similarity
            results.append({
                "text": chunk["text"],
                "source": chunk["source"],
                "score": round(score, 4),
            })

        # Sort by score descending
        results.sort(key=lambda r: r["score"], reverse=True)

        return json.dumps({
            "results": results,
            "query": query,
            "count": len(results),
        })

    except Exception as e:
        return f"Error: {type(e).__name__} — {e}"


def _load_corpus(corpus_dir: str) -> List[Dict[str, Any]]:
    """Load all .txt files from corpus directory and chunk them."""
    all_chunks = []
    for filename in sorted(os.listdir(corpus_dir)):
        if not filename.endswith(".txt"):
            continue
        filepath = os.path.join(corpus_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            chunks = _chunk_text(text, filename)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Failed to read {filename}: {e}")
    return all_chunks


def _chunk_text(text: str, source: str) -> List[Dict[str, Any]]:
    """Split text into chunks by paragraph boundaries.

    Args:
        text: Full document text.
        source: Source filename for metadata.

    Returns:
        List of chunk dicts with text, source, position.
    """
    paragraphs = text.split("\n\n")
    chunks = []
    position = 0
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        chunks.append({
            "text": para,
            "source": source,
            "position": position,
        })
        position += 1
    return chunks


def _build_index(chunks: List[Dict[str, Any]]):
    """Build a FAISS index from document chunks.

    Returns:
        (faiss.IndexFlatL2, chunk_list)
    """
    try:
        import faiss
    except ImportError:
        # Fallback to numpy-based brute force
        return _NumpyIndex(chunks), chunks

    texts = [c["text"] for c in chunks]
    embeddings = _get_embeddings(texts)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    return index, chunks


def _get_embeddings(texts: List[str]) -> np.ndarray:
    """Get embeddings for a list of texts using sentence-transformers.

    This function is the mock boundary for testing.
    """
    global _model
    try:
        from sentence_transformers import SentenceTransformer
        if _model is None:
            _model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = _model.encode(texts, convert_to_numpy=True)
        return embeddings.astype(np.float32)
    except ImportError:
        # Fallback: hash-based deterministic pseudo-embeddings
        logger.warning("sentence-transformers not installed, using hash-based embeddings")
        return _hash_embeddings(texts)


def _hash_embeddings(texts: List[str]) -> np.ndarray:
    """Generate deterministic pseudo-embeddings from text hashes.

    Not useful for real semantic search but allows the pipeline to function
    without sentence-transformers installed.
    """
    embeddings = np.zeros((len(texts), _EMBEDDING_DIM), dtype=np.float32)
    for i, text in enumerate(texts):
        # Use hash to seed random for deterministic output
        seed = hash(text) % (2**31)
        rng = np.random.RandomState(seed)
        embeddings[i] = rng.randn(_EMBEDDING_DIM).astype(np.float32)
        # Normalize
        norm = np.linalg.norm(embeddings[i])
        if norm > 0:
            embeddings[i] /= norm
    return embeddings


class _NumpyIndex:
    """Fallback brute-force index when FAISS is not available."""

    def __init__(self, chunks: List[Dict[str, Any]]):
        texts = [c["text"] for c in chunks]
        self.embeddings = _get_embeddings(texts)
        self.chunks = chunks

    def search(self, query_embedding: np.ndarray, k: int):
        """Brute-force L2 search."""
        # Compute L2 distances
        diffs = self.embeddings - query_embedding
        distances = np.sum(diffs ** 2, axis=1)

        # Get top-k indices
        k = min(k, len(distances))
        top_indices = np.argsort(distances)[:k]
        top_distances = distances[top_indices]

        return top_distances.reshape(1, -1), top_indices.reshape(1, -1)
