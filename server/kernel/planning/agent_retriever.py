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
_EXCLUDED_FROM_RETRIEVAL = {"agent_creator"}
_collection = None


def _sync_index(collection) -> None:
    descriptions = get_agent_descriptions()
    # Agent Creator is dispatched by Prompt_type after an empty plan; it must
    # not compete with task specialists in semantic capability retrieval.
    ids = [name for name in descriptions if name not in _EXCLUDED_FROM_RETRIEVAL]
    documents = [f"Agent: {name}\nCapabilities:\n{descriptions[name]}" for name in ids]
    metadatas = [
        {
            "agent_name": name,
            "description_hash": hashlib.sha256(descriptions[name].encode()).hexdigest(),
        }
        for name in ids
    ]
    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    for excluded_name in _EXCLUDED_FROM_RETRIEVAL:
        collection.delete(ids=[excluded_name])
    if ids:
        logger.info("Planner capability index ready | agents=%d | path=%s", len(ids), _INDEX_PATH)
    retrieve_agent_candidates.cache_clear()


def refresh_agent_index() -> None:
    """Refresh the ChromaDB vector index with all registered agents and clear candidate cache."""
    collection = _get_collection()
    _sync_index(collection)


def _refresh_index() -> None:
    if _collection is not None:
        _sync_index(_collection)


def register_agent_in_vector_db(agent_name: str, description: str) -> None:
    """Explicitly register or update a single agent in ChromaDB vector DB."""
    if agent_name in _EXCLUDED_FROM_RETRIEVAL:
        return
    collection = _get_collection()
    doc = f"Agent: {agent_name}\nCapabilities:\n{description.strip()}"
    meta = {
        "agent_name": agent_name,
        "description_hash": hashlib.sha256(description.encode()).hexdigest(),
    }
    collection.upsert(ids=[agent_name], documents=[doc], metadatas=[meta])
    retrieve_agent_candidates.cache_clear()
    logger.info("Agent '%s' successfully registered in ChromaDB vector DB", agent_name)


def remove_agent_from_vector_db(agent_name: str) -> None:
    """Remove an agent from the ChromaDB vector DB (e.g. on registration rollback)."""
    try:
        collection = _get_collection()
        collection.delete(ids=[agent_name])
        retrieve_agent_candidates.cache_clear()
        logger.info("Agent '%s' removed from ChromaDB vector DB", agent_name)
    except Exception as exc:
        logger.warning("Could not remove agent '%s' from ChromaDB: %s", agent_name, exc)


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
        n_results=min(_TOP_K + len(_EXCLUDED_FROM_RETRIEVAL), total),
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
        if metadata.get("agent_name") not in _EXCLUDED_FROM_RETRIEVAL
    )[:_TOP_K]
    logger.info(
        "Planner candidates retrieved | task_chars=%d | candidates=%s",
        len(task),
        [f"{item['name']}:{item['similarity']}" for item in candidates],
    )
    return candidates
