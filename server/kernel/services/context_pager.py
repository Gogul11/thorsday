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
import os
import hashlib
import threading
from collections import OrderedDict
from time import perf_counter
import asyncio

import chromadb
from chromadb.utils import embedding_functions
from logger import logger

# Constants — tuneable hyperparameters from the algorithm specification

# W: Active RAM window size (messages kept in the live context prompt).
# Messages beyond this threshold are swapped out.
ACTIVE_RAM_WINDOW: int = 20

# τ (tau): Cosine similarity threshold for page-in acceptance.
# A swapped page is only injected back if its similarity to the current
# query meets or exceeds this value.
PAGE_IN_SIMILARITY_THRESHOLD: float = 0.4

# K: Maximum number of swapped pages to inject per query turn.
MAX_PAGE_IN_RESULTS: int = 3

# Chroma accepts batches, but keeping a bounded batch avoids oversized writes
# when a long conversation is first paged out.
PAGE_OUT_BATCH_SIZE: int = 64

# Bound the process-local vector cache so long-running AgentOS processes do not
# grow memory without limit. The cache is keyed by exact message content.
EMBEDDING_CACHE_MAX_ITEMS: int = 4096

# ChromaDB collection name — acts as the named swap partition.
_COLLECTION_NAME = "agentos_context_swap"

# Persistent storage path: server/kernel/data/swap_space/
_DEFAULT_SWAP_SPACE_DIR = Path(__file__).parent.parent / "data" / "swap_space"
# Evaluation runs can point the pager at an isolated Chroma directory. This
# prevents smoke tests and benchmark runs from polluting the production swap
# partition.
_SWAP_SPACE_DIR = Path(os.getenv("AOS_CONTEXT_SWAP_DIR", str(_DEFAULT_SWAP_SPACE_DIR)))


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

        # Append-only conversations normally overflow at the end. Remembering
        # the highest indexed page per task lets repeated context loads avoid
        # rescanning and re-embedding the complete overflow prefix. The
        # watermark is rebuilt from Chroma on first use after a process restart.
        self._page_out_watermarks: dict[str, int] = {}
        self._last_page_out_metrics: dict[str, Any] = {}
        self._embedding_cache: OrderedDict[str, list[float]] = OrderedDict()
        self._embedding_cache_lock = threading.Lock()

        # Background page-out state. The queue is created lazily on the active
        # asyncio event loop because ContextPager is instantiated at import
        # time, before the kernel loop necessarily exists.
        self._page_out_queue: asyncio.Queue[tuple[str, str]] | None = None
        self._page_out_worker_task: asyncio.Task | None = None
        self._queued_page_out_tasks: set[str] = set()

        logger.info(
            "ContextPager: swap partition initialised at %s (collection=%s, items=%d)",
            _SWAP_SPACE_DIR,
            _COLLECTION_NAME,
            self._collection.count(),
        )

    async def enqueue_page_out(self, task_id: str, req_id: str = "") -> None:
        """Schedule asynchronous indexing for a task's overflow messages.

        Scheduling is deduplicated per task. If several messages are persisted
        during one turn, the worker reads the latest overflow prefix once and
        the existing page-out watermark skips anything already indexed.
        """
        if not task_id:
            return

        if self._page_out_queue is None or self._page_out_worker_task is None:
            self._page_out_queue = asyncio.Queue()
            self._page_out_worker_task = asyncio.create_task(
                self._page_out_worker(),
                name="context-page-out-worker",
            )

        if task_id in self._queued_page_out_tasks:
            return

        self._queued_page_out_tasks.add(task_id)
        await self._page_out_queue.put((task_id, req_id))

    async def _page_out_worker(self) -> None:
        """Continuously index overflow messages outside request handling."""
        from repository.task_repo import DB_get_task_overflow_messages

        while True:
            task_id, req_id = await self._page_out_queue.get()  # type: ignore[union-attr]
            try:
                overflow = await DB_get_task_overflow_messages(
                    task_id,
                    active_window=ACTIVE_RAM_WINDOW,
                )
                if overflow:
                    await asyncio.to_thread(
                        self.page_out_messages,
                        task_id=task_id,
                        overflow_messages=overflow,
                        base_index=0,
                        req_id=req_id,
                    )
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pylint: disable=broad-except
                # The next message or request for this task will enqueue it
                # again. A failed background index must never fail the user
                # request that already completed.
                logger.exception(
                    "ContextPager background PAGE_OUT failed | task=%s: %s",
                    task_id,
                    exc,
                )
            finally:
                self._queued_page_out_tasks.discard(task_id)
                self._page_out_queue.task_done()  # type: ignore[union-attr]

    # Phase 1 — Page-Out (Swap-Out)
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

        started = perf_counter()
        candidate_indices = [
            base_index + offset for offset in range(len(overflow_messages))
        ]
        if task_id not in self._page_out_watermarks:
            # One metadata lookup restores the optimization after a restart.
            existing = self._collection.get(
                where={"task_id": task_id}, include=["metadatas"]
            )
            existing_indices = [
                int(meta["message_index"])
                for meta in (existing.get("metadatas") or [])
                if meta and "message_index" in meta
            ]
            self._page_out_watermarks[task_id] = max(existing_indices, default=-1)

        watermark = self._page_out_watermarks[task_id]
        candidate_indices = [index for index in candidate_indices if index > watermark]
        skipped_by_watermark = len(overflow_messages) - len(candidate_indices)

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for absolute_index in candidate_indices:
            msg = overflow_messages[absolute_index - base_index]
            page_key = f"{task_id}_msg_{absolute_index}"
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
            self._last_page_out_metrics = {
                "task_id": task_id,
                "indexed_count": 0,
                "skipped_existing_or_watermark": skipped_by_watermark,
                "embedding_latency_ms": 0.0,
                "embedding_cache_hit_count": 0,
                "embedding_cache_miss_count": 0,
                "embedding_cache_hit_rate": 1.0,
                "vector_store_write_latency_ms": 0.0,
                "total_latency_ms": round((perf_counter() - started) * 1000, 3),
            }
            return 0

        # Compute embeddings explicitly so embedding and Chroma write time can
        # be measured separately, and so the vectors are never recomputed by
        # Chroma during upsert.
        embeddings, embedding_latency_ms, cache_hits, cache_misses = (
            self._get_cached_embeddings(documents)
        )

        write_started = perf_counter()
        for start in range(0, len(ids), PAGE_OUT_BATCH_SIZE):
            end = start + PAGE_OUT_BATCH_SIZE
            self._collection.upsert(
                ids=ids[start:end],
                documents=documents[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
            )
        write_latency_ms = (perf_counter() - write_started) * 1000

        self._page_out_watermarks[task_id] = max(
            self._page_out_watermarks[task_id],
            max(int(meta["message_index"]) for meta in metadatas),
        )

        count = len(ids)
        total_latency_ms = (perf_counter() - started) * 1000
        self._last_page_out_metrics = {
            "task_id": task_id,
            "indexed_count": count,
            "skipped_existing_or_watermark": skipped_by_watermark,
            "embedding_latency_ms": round(embedding_latency_ms, 3),
            "embedding_cache_hit_count": cache_hits,
            "embedding_cache_miss_count": cache_misses,
            "embedding_cache_hit_rate": (
                round(cache_hits / (cache_hits + cache_misses), 4)
                if cache_hits + cache_misses
                else 1.0
            ),
            "vector_store_write_latency_ms": round(write_latency_ms, 3),
            "total_latency_ms": round(total_latency_ms, 3),
            "batch_size": PAGE_OUT_BATCH_SIZE,
        }
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
            **{
                key: value
                for key, value in self._last_page_out_metrics.items()
                if key != "task_id"
            },
        )

        return count

    def get_last_page_out_metrics(self) -> dict[str, Any]:
        """Return timing and deduplication data for the most recent page-out."""
        return dict(self._last_page_out_metrics)

    def _get_cached_embeddings(
        self, documents: list[str]
    ) -> tuple[list[list[float]], float, int, int]:
        """Return embeddings while reusing exact-content vectors.

        The cache is process-local because the configured embedding function
        is process-local. Chroma remains the durable store for page vectors;
        this cache avoids repeating model inference before those vectors are
        written for another page or task.
        """
        keys = [
            hashlib.sha256(document.encode("utf-8")).hexdigest()
            for document in documents
        ]
        result: list[list[float] | None] = [None] * len(documents)
        missing_documents: list[str] = []
        missing_positions: list[int] = []

        with self._embedding_cache_lock:
            for position, key in enumerate(keys):
                cached = self._embedding_cache.get(key)
                if cached is None:
                    missing_documents.append(documents[position])
                    missing_positions.append(position)
                else:
                    self._embedding_cache.move_to_end(key)
                    result[position] = cached

            cache_hits = len(documents) - len(missing_documents)

            embedding_started = perf_counter()
            new_embeddings = (
                self._embed_fn(missing_documents) if missing_documents else []
            )
            embedding_latency_ms = (perf_counter() - embedding_started) * 1000

            for position, key, embedding in zip(
                missing_positions,
                (keys[index] for index in missing_positions),
                new_embeddings,
            ):
                # ChromaDB 1.5 validates against native Python numbers; the
                # local ONNX embedder returns numpy.float32 values.
                vector = [float(value) for value in embedding]
                self._embedding_cache[key] = vector
                self._embedding_cache.move_to_end(key)
                result[position] = vector
                while len(self._embedding_cache) > EMBEDDING_CACHE_MAX_ITEMS:
                    self._embedding_cache.popitem(last=False)

        # Every position is filled unless the embedding function violates its
        # contract; fail loudly rather than writing malformed Chroma records.
        if any(vector is None for vector in result):
            raise RuntimeError("Embedding function returned an incomplete batch")
        return (
            [vector for vector in result if vector is not None],
            embedding_latency_ms,
            cache_hits,
            len(missing_documents),
        )

    # Phase 2 — Page-In (Swap-In / Page Fault Handler)
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
            # ChromaDB cosine distance is defined as:
            #     distance = 1 - cosine_similarity
            # Therefore the similarity is recovered directly as 1 - distance.
            similarity = 1.0 - dist

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


context_pager = ContextPager()
