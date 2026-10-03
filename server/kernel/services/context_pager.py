"""
context_pager.py — Virtual Memory Context Paging Engine
========================================================

OS-inspired context paging system for AgentOS.

Implements Algorithm VM-Paging from the AgentOS design specification:

  * Page-Out (Swap-Out): When total stored messages |M| exceed the
    active RAM window W, overflow pages are embedded via a dense vector
    mapping Φ: String → ℝᵈ and persisted in a local ChromaDB swap
    partition so they are never lost.

  * Page-In (Swap-In / Page Fault Handler): When a new user query q
    arrives, the pager performs a vector similarity search over the
    swap partition and retrieves the top-K historical pages whose
    cosine
    similarity Sim(q, pᵢ) ≥ τ, injecting them into the active
    context window as supplementary system memory.

  Similarity metric (cosine):
      Sim(q, pᵢ) = (v_q · v_pᵢ) / (‖v_q‖ · ‖v_pᵢ‖)

Architecture
------------
  MongoDB (persistent store)
      ↓  get_context fetches M = <m₁ … mₙ>
  ContextPager.page_out_messages()
      ↓  indexes P_overflow into ChromaDB swap partition
  ChromaDB (swap partition on disk)
      ↓  vector similarity search on query embedding Φ(q)
  ContextPager.page_in_relevant_context()
      ↓  returns top-K paged-in snippets to context.py
  LLM Context Window (composed and returned to task_runner)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions
from logger import logger

# Constants — tuneable hyperparameters from the algorithm specification

# W: Active RAM window size (messages kept in the live context prompt).
# Messages beyond this threshold are swapped out.
ACTIVE_RAM_WINDOW: int = 2

# τ (tau): Cosine similarity threshold for page-in acceptance.
# A swapped page is only injected back if its similarity to the current
# query meets or exceeds this value.
PAGE_IN_SIMILARITY_THRESHOLD: float = 0.55

# K: Maximum number of swapped pages to inject per query turn.
MAX_PAGE_IN_RESULTS: int = 3

# ChromaDB collection name — acts as the named swap partition.
_COLLECTION_NAME = "agentos_context_swap"

# Persistent storage path: server/kernel/data/swap_space/
_SWAP_SPACE_DIR = Path(__file__).parent.parent / "data" / "swap_space"


# Redis telemetry helpers
def _emit_page_event(event: str, task_id: str, req_id: str = "", **data: Any) -> None:
    """
    Publish a context paging lifecycle event to the Redis kernel_events
    channel so the Next.js activity panel can display PAGE_OUT / PAGE_IN
    operations in real time.

    Errors are swallowed to ensure the pager never crashes the kernel loop.
    """
    try:
        from Redis.redis_connection import publish
        from repository.task_repo import DB_add_task_event
        import asyncio

        payload = {"event": event, "req_id": req_id, "task_id": task_id, **data}

        async def persist_and_publish() -> None:
            await publish("kernel_events", payload)
            await DB_add_task_event(task_id, payload)

        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(persist_and_publish())
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("context_pager: redis emit failed (%s): %s", event, exc)


# ContextPager — singleton paging engine
class ContextPager:
    """
    Virtual Memory Context Paging Engine.

    Manages a persistent ChromaDB collection as a swap partition.
    Each record in the collection represents one swapped-out conversation
    page identified by a composite page_key:

        page_key = f"{task_id}_msg_{message_index}"

    The embedding function defaults to ChromaDB's built-in
    DefaultEmbeddingFunction (all-MiniLM-L6-v2 via ONNX) so there are
    no additional API keys required — all embedding computation is local.

    Usage
    -----
    This class should be accessed through the module-level singleton
    ``context_pager`` defined at the bottom of this file.

        from services.context_pager import context_pager

        context_pager.page_out_messages(task_id, overflow_messages)
        hits = context_pager.page_in_relevant_context(task_id, query)
    """

    def __init__(self) -> None:
        _SWAP_SPACE_DIR.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(_SWAP_SPACE_DIR))

        # Use the local ONNX-backed default embedder — no API key required.
        self._embed_fn = embedding_functions.DefaultEmbeddingFunction()

        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=self._embed_fn,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            "ContextPager: swap partition initialised at %s (collection=%s, items=%d)",
            _SWAP_SPACE_DIR,
            _COLLECTION_NAME,
            self._collection.count(),
        )

    # ------------------------------------------------------------------
    # Phase 1 — Page-Out (Swap-Out)
    # ------------------------------------------------------------------

    def page_out_messages(
        self,
        task_id: str,
        overflow_messages: list[dict],
        base_index: int = 0,
        req_id: str = "",
    ) -> int:
        """
        Embed and persist overflow messages into the swap partition.

        Implements Phase 1 of Algorithm VM-Paging:

            for each mᵢ in P_overflow:
                page_key ← CONCATENATE(T_id, "_msg_", i)
                if NOT EXISTS_IN_VECTOR_STORE(page_key):
                    vᵢ ← Φ(mᵢ.content)
                    VECTOR_STORE_INSERT(page_key, vᵢ, mᵢ.content, metadata)
                    EMIT_REDIS_EVENT("context.PAGE_OUT", …)

        Parameters
        ----------
        task_id:
            Unique task identifier used as the namespace key.
        overflow_messages:
            Ordered list of message dicts from MongoDB (role, content, …)
            that exceed the active RAM window and must be swapped out.
        base_index:
            The absolute message index of overflow_messages[0] within the
            full conversation history (used to construct stable page_keys).

        Returns
        -------
        int
            Number of newly-indexed pages (skips already-indexed pages).
        """
        if not overflow_messages:
            return 0

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for offset, msg in enumerate(overflow_messages):
            absolute_index = base_index + offset
            page_key = f"{task_id}_msg_{absolute_index}"

            # Check for existing pages to avoid duplicate embeddings.
            existing = self._collection.get(ids=[page_key])
            if existing and existing.get("ids"):
                continue

            content = msg.get("content", "").strip()
            if not content:
                continue

            role = msg.get("role", "unknown")
            timestamp = msg.get("timestamp", "")

            ids.append(page_key)
            documents.append(content)
            metadatas.append(
                {
                    "task_id": task_id,
                    "role": role,
                    "timestamp": str(timestamp),
                    "message_index": absolute_index,
                    "page_key": page_key,
                }
            )

        if not ids:
            return 0

        # Batch upsert — ChromaDB computes embeddings via the ONNX engine.
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        count = len(ids)
        logger.info(
            "ContextPager PAGE_OUT | req=%s | task=%s | pages=%d | indices=%d-%d | swap_total=%d",
            req_id or "-",
            task_id,
            count,
            base_index,
            base_index + len(overflow_messages) - 1,
            self._collection.count(),
        )

        # Emit Redis event for the live activity panel.
        _emit_page_event(
            "context.PAGE_OUT",
            task_id=task_id,
            req_id=req_id,
            paged_count=count,
            total_in_swap=self._collection.count(),
        )

        return count

    # ------------------------------------------------------------------
    # Phase 2 — Page-In (Swap-In / Page Fault Handler)
    # ------------------------------------------------------------------

    def page_in_relevant_context(
        self,
        task_id: str,
        query: str,
        top_k: int = MAX_PAGE_IN_RESULTS,
        threshold: float = PAGE_IN_SIMILARITY_THRESHOLD,
        req_id: str = "",
    ) -> list[dict]:
        """
        Perform a vector similarity search over the swap partition and
        return relevant historical pages for injection into the context window.

        Implements Phase 2 of Algorithm VM-Paging:

            v_q ← Φ(q)
            Candidates ← VECTOR_STORE_SEARCH(filter={task_id}, v_q, top_k=K)
            for each pᵢ in Candidates:
                similarity ← (v_q · v_pᵢ) / (‖v_q‖ · ‖v_pᵢ‖)
                if similarity ≥ τ:
                    P_in ← P_in ∪ { pᵢ }
                    EMIT_REDIS_EVENT("context.PAGE_IN", …)

        Parameters
        ----------
        task_id:
            Namespace filter — only pages belonging to this task are searched.
        query:
            The current user prompt used as the similarity search key.
        top_k:
            Maximum candidates to retrieve from ChromaDB before threshold
            filtering.
        threshold:
            Minimum cosine similarity τ required for a page to be paged in.

        Returns
        -------
        list[dict]
            Ordered list of accepted page dicts:
            {text, role, timestamp, message_index, similarity}
        """
        query = query.strip()
        if not query:
            return []

        # Guard: if no pages exist for this task yet, skip the search.
        try:
            total_items = self._collection.count()
        except Exception:  # pylint: disable=broad-except
            return []

        if total_items == 0:
            return []

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(top_k, total_items),
                where={"task_id": task_id},
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("ContextPager PAGE_IN search error: %s", exc)
            return []

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        accepted: list[dict] = []

        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB with cosine space returns distances in [0, 2] where
            # 0 = identical vectors. Convert to similarity ∈ [0, 1]:
            #     similarity = 1 - (distance / 2)
            similarity = 1.0 - (dist / 2.0)

            if similarity < threshold:
                continue

            page = {
                "text": doc,
                "role": meta.get("role", "unknown"),
                "timestamp": meta.get("timestamp", ""),
                "message_index": meta.get("message_index", -1),
                "similarity": round(similarity, 4),
            }
            accepted.append(page)

            logger.debug(
                "ContextPager PAGE_IN accepted: task=%s index=%s sim=%.4f",
                task_id,
                meta.get("message_index"),
                similarity,
            )

        if accepted:
            logger.info(
                "ContextPager PAGE_IN | req=%s | task=%s | pages=%d | top_similarity=%.4f | tau=%.2f",
                req_id or "-",
                task_id,
                len(accepted),
                accepted[0]["similarity"],
                threshold,
            )
            _emit_page_event(
                "context.PAGE_IN",
                task_id=task_id,
                req_id=req_id,
                pages_injected=len(accepted),
                top_similarity=accepted[0]["similarity"],
            )

        return accepted

    # ------------------------------------------------------------------
    # Phase 3 helper — Format paged-in block for LLM context injection
    # ------------------------------------------------------------------

    @staticmethod
    def format_page_in_block(pages: list[dict]) -> str:
        """
        Serialise accepted page-in results into a system-level context
        injection block for prepending to the active LLM context window.

        The block uses a clear visual delimiter so the LLM can distinguish
        between actively cached context and virtually-recalled memory.

        Parameters
        ----------
        pages:
            Accepted page-in results from page_in_relevant_context().

        Returns
        -------
        str
            Formatted system message content string.
        """
        if not pages:
            return ""

        lines = [
            "======================================================================",
            "   VIRTUAL MEMORY SWAP PAGE-IN  (Historical Context Recall)          ",
            "   The following messages were paged out of the active context        ",
            "   window and retrieved via vector similarity search.                 ",
            "======================================================================",
            "",
        ]

        for i, page in enumerate(pages, start=1):
            role_label = "User" if page["role"] == "human" else "Assistant"
            lines.append(
                f"[Paged-In Memory #{i} | {role_label} "
                f"| MsgIdx={page['message_index']} "
                f"| Sim={page['similarity']:.4f}]"
            )
            lines.append(page["text"])
            lines.append("")

        lines.append(
            "==================== End of Paged-In Memory ========================="
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def get_swap_stats(self, task_id: str | None = None) -> dict:
        """
        Return diagnostic statistics about the swap partition.

        Parameters
        ----------
        task_id:
            If given, count only pages belonging to this task.
            If None, count all pages across all tasks.
        """
        total = self._collection.count()
        if task_id:
            results = self._collection.get(where={"task_id": task_id})
            task_count = len(results.get("ids", []))
            return {
                "total_swap_pages": total,
                "task_swap_pages": task_count,
                "task_id": task_id,
                "swap_path": str(_SWAP_SPACE_DIR),
            }
        return {
            "total_swap_pages": total,
            "swap_path": str(_SWAP_SPACE_DIR),
        }


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------

context_pager = ContextPager()
