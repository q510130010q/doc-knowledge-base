import re
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions


COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Pattern to identify function/class/method names in queries.
# Use ASCII-only word chars to avoid matching CJK characters.
_FUNC_NAME_RE = re.compile(r"[A-Z][A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


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
        # 1. Vector search (semantic)
        semantic: list[dict[str, Any]] = []
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k * 2,
            )
            if results["ids"] and results["ids"][0]:
                for i in range(len(results["ids"][0])):
                    semantic.append({
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results.get("distances") else 0,
                    })
        except Exception:
            pass

        # 2. Keyword matching: boost chunks that contain function/API names from the query
        keywords = _FUNC_NAME_RE.findall(query)
        # Only keep meaningful-looking identifiers (≥4 chars, has uppercase mix)
        keywords = [kw for kw in keywords if len(kw) >= 3]

        if keywords:
            try:
                all_data = self.collection.get()
                keyword_hits: list[dict[str, Any]] = []
                seen_ids = {r["id"] for r in semantic}

                for i, doc in enumerate(all_data["documents"]):
                    for kw in keywords:
                        if kw in doc:
                            chunk_id = all_data["ids"][i]
                            # Boost distance based on how "definition-like" the chunk is.
                            # Chunks with 指令说明/指令原型/指令参数 near the function name
                            # are likely the actual definition, not just a code example.
                            raw_distance = 0.25  # default keyword hit
                            if kw in doc:
                                # Check for definition indicators within the same chunk
                                def_indicators = [
                                    "指令说明", "指令原型", "指令参数",
                                    "指令类型", "指令返回值", "相关指令",
                                ]
                                near_def = 0
                                for indicator in def_indicators:
                                    pos_indicator = doc.find(indicator)
                                    pos_kw = doc.find(kw)
                                    if pos_indicator != -1 and pos_kw != -1:
                                        # Indicator within 500 chars of keyword
                                        if abs(pos_indicator - pos_kw) < 500:
                                            near_def += 1
                                # Boost: each definition indicator reduces distance
                                if near_def >= 2:
                                    raw_distance = 0.08
                                elif near_def >= 1:
                                    raw_distance = 0.15

                            if chunk_id in seen_ids:
                                for r in semantic:
                                    if r["id"] == chunk_id:
                                        r["distance"] = min(r["distance"], raw_distance)
                                        break
                            else:
                                keyword_hits.append({
                                    "id": chunk_id,
                                    "text": doc,
                                    "metadata": all_data["metadatas"][i] if all_data["metadatas"] else {},
                                    "distance": raw_distance,
                                })
                            break  # one match per doc is enough

                # 3. Merge: keyword hits first (low distance = relevant),
                # then semantic results, deduped by id
                merged = keyword_hits[:]
                seen = {r["id"] for r in merged}
                for r in semantic:
                    if r["id"] not in seen:
                        merged.append(r)
                        seen.add(r["id"])

                # Sort by distance (lower = more relevant)
                merged.sort(key=lambda x: x["distance"])
                return merged[:top_k]

            except Exception:
                pass

        return semantic[:top_k]

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