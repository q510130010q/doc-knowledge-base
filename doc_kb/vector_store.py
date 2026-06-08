from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions


COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class VectorStore:
    def __init__(self, persist_dir: str | Path = "data/chroma"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL,
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[dict[str, Any]]) -> int:
        if not chunks:
            return 0
        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        return len(chunks)

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
            )
        except Exception:
            return []

        output: list[dict[str, Any]] = []
        if not results["ids"] or not results["ids"][0]:
            return output

        for i in range(len(results["ids"][0])):
            output.append({
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results.get("distances") else 0,
            })
        return output

    def list_sources(self) -> list[str]:
        try:
            meta = self.collection.get()["metadatas"]
        except Exception:
            return []
        if not meta:
            return []
        sources = set()
        for m in meta:
            if m and "source" in m:
                sources.add(m["source"])
        return sorted(sources)

    def count_chunks(self) -> int:
        try:
            return self.collection.count()
        except Exception:
            return 0

    def delete_source(self, source: str) -> int:
        try:
            results = self.collection.get(where={"source": source})
            ids = results["ids"]
            if ids:
                self.collection.delete(ids=ids)
            return len(ids)
        except Exception:
            return 0

    def reset(self):
        try:
            self.client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
