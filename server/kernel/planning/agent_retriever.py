"""Semantic retrieval of relevant agents for the planner."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from Agents.agent_registry import get_agent_descriptions
from logger import logger

_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "planning_agent_index"
_COLLECTION_NAME = "agent_capabilities"
_TOP_K = 5
_collection = None


def _refresh_index() -> None:
    if _collection is None:
        return
    descriptions = get_agent_descriptions()
    ids = list(descriptions)
    documents = [f"Agent: {name}\nCapabilities:\n{descriptions[name]}" for name in ids]
    metadatas = [
        {
            "agent_name": name,
            "description_hash": hashlib.sha256(descriptions[name].encode()).hexdigest(),
        }
        for name in ids
    ]
    if ids:
        _collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("Planner capability index ready | agents=%d | path=%s", len(ids), _INDEX_PATH)


def _get_collection():
    global _collection
    if _collection is None:
        _INDEX_PATH.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(_INDEX_PATH))
        _collection = client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=embedding_functions.DefaultEmbeddingFunction(),
            metadata={"hnsw:space": "cosine"},
        )
        _refresh_index()
    return _collection


@lru_cache(maxsize=128)
def retrieve_agent_candidates(task: str) -> tuple[dict, ...]:
    """Return the most semantically relevant agent candidates for a task."""
    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return ()

    results = collection.query(
        query_texts=[task],
        n_results=min(_TOP_K, total),
        include=["documents", "metadatas", "distances"],
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    candidates = tuple(
        {
            "name": metadata["agent_name"],
            "description": document,
            # Chroma cosine distance is d = 1 - cosine_similarity.
            "similarity": round(1 - distance, 4),
        }
        for document, metadata, distance in zip(documents, metadatas, distances)
    )
    logger.info(
        "Planner candidates retrieved | task_chars=%d | candidates=%s",
        len(task),
        [f"{item['name']}:{item['similarity']}" for item in candidates],
    )
    return candidates
