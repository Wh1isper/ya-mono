"""Embedding-based semantic search strategy using FastEmbed.

Requires: pip install fastembed (or pip install ya-agent-sdk[tool-search])

Uses ONNX-based local embedding models for semantic similarity search.
No GPU required, no API keys needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import anyio

from ya_agent_sdk._logger import get_logger
from ya_agent_sdk.toolsets.tool_search.metadata import ToolMetadata

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

_DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"


class EmbeddingSearchStrategy:
    """Semantic search using FastEmbed (ONNX-based local embeddings).

    Pre-computes tool embeddings at index build time. Query embedding
    is computed on each search call (~5ms). Cosine similarity for ranking.

    All CPU-bound embedding computations are offloaded to a thread pool
    via ``anyio.to_thread.run_sync`` to avoid blocking the event loop.

    Requires the ``fastembed`` package::

        pip install fastembed

    Example::

        strategy = EmbeddingSearchStrategy()
        await strategy.build_index(tool_metadata_list)
        results = await strategy.search("get weather info", candidates)

    Args:
        model_name: FastEmbed model name. Default: BAAI/bge-small-en-v1.5
            (384 dims, ~50MB, runs on CPU).
        **model_kwargs: Additional kwargs passed to fastembed.TextEmbedding().
    """

    def __init__(self, model_name: str = _DEFAULT_MODEL, **model_kwargs: Any) -> None:
        self._model_name = model_name
        self._model_kwargs = model_kwargs
        self._model: Any = None  # Lazy init
        self._embeddings: Any = None  # NDArray[np.float32] | None, lazy numpy
        self._indexed_tools: list[ToolMetadata] = []

    def get_search_hint(self) -> str:
        """Hint for semantic search usage."""
        return (
            "Search uses semantic similarity. Describe what you need in natural language "
            '(e.g., "send a message to someone" or "convert between currencies"). '
            "Exact tool names are not required."
        )

    @staticmethod
    def _import_numpy() -> Any:
        """Import numpy, raising a clear error if not installed."""
        try:
            import numpy
        except ImportError:
            msg = (
                "numpy is required for EmbeddingSearchStrategy. "
                "Install it with: pip install numpy "
                "or: pip install ya-agent-sdk[tool-search]"
            )
            raise ImportError(msg) from None
        return numpy

    def _get_model(self) -> Any:
        """Lazily initialize the embedding model."""
        if self._model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError:
                msg = (
                    "fastembed is required for EmbeddingSearchStrategy. "
                    "Install it with: pip install fastembed "
                    "or: pip install ya-agent-sdk[tool-search]"
                )
                raise ImportError(msg) from None

            logger.debug(f"Loading FastEmbed model: {self._model_name}")
            self._model = TextEmbedding(self._model_name, **self._model_kwargs)
            logger.debug("FastEmbed model loaded")
        return self._model

    async def build_index(self, tools: list[ToolMetadata]) -> None:
        """Build embedding index from tool metadata.

        Computes embeddings for all tool searchable texts and stores them
        as a numpy array for fast cosine similarity computation.

        The CPU-bound embedding computation is offloaded to a thread pool.

        Args:
            tools: List of tool metadata to index.
        """
        if not tools:
            self._embeddings = None
            self._indexed_tools = []
            return

        np = self._import_numpy()
        model = self._get_model()
        texts = [t.searchable_text for t in tools]

        logger.debug(f"Computing embeddings for {len(texts)} tools")

        def _compute() -> Any:
            return np.array(list(model.embed(texts)), dtype=np.float32)

        self._embeddings = await anyio.to_thread.run_sync(_compute)  # type: ignore[reportAttributeAccessIssue]
        self._indexed_tools = list(tools)
        logger.debug(f"Embedding index built: shape={self._embeddings.shape}")

    async def search(
        self,
        query: str,
        candidates: list[ToolMetadata],
        max_results: int = 5,
    ) -> list[ToolMetadata]:
        """Search tools using semantic similarity.

        Computes cosine similarity between the query embedding and all
        candidate tool embeddings. Returns top-k results above a
        minimum similarity threshold.

        The CPU-bound embedding and similarity computations are offloaded
        to a thread pool.

        Args:
            query: Natural language search query.
            candidates: Tools to search through (must be a subset of indexed tools).
            max_results: Maximum results to return.

        Returns:
            List of matching tools, ranked by semantic similarity.
        """
        if not query or not candidates:
            return []

        if self._embeddings is None or not self._indexed_tools:
            logger.warning("Embedding index not built, falling back to empty results")
            return []

        np = self._import_numpy()
        model = self._get_model()

        # Build candidate identity set for filtering
        candidate_ids = {id(t) for t in candidates}
        indexed_tools = self._indexed_tools
        embeddings = self._embeddings

        def _compute_similarities() -> list[tuple[float, ToolMetadata]]:
            # Compute query embedding
            query_embedding = np.array(list(model.embed([query])), dtype=np.float32)[0]

            # Normalize for cosine similarity
            query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-10)
            index_norms = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)
            similarities = index_norms @ query_norm

            # Filter to candidates and sort by similarity
            scored: list[tuple[float, ToolMetadata]] = []
            for idx, tool in enumerate(indexed_tools):
                if id(tool) in candidate_ids:
                    scored.append((float(similarities[idx]), tool))

            scored.sort(key=lambda x: -x[0])
            return scored

        scored = await anyio.to_thread.run_sync(_compute_similarities)  # type: ignore[reportAttributeAccessIssue]

        # Return top-k with minimum similarity threshold
        min_similarity = 0.1
        results = [tool for score, tool in scored[:max_results] if score > min_similarity]

        if results:
            logger.debug(
                f"Embedding search for {query!r}: top result={results[0].name} "
                f"(sim={scored[0][0]:.3f}), {len(results)} total"
            )

        return results
