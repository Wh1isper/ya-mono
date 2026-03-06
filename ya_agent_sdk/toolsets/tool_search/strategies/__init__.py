"""Search strategies for tool discovery.

Provides pluggable search algorithms for ToolSearchToolSet:
- KeywordSearchStrategy: Zero-dependency regex/keyword matching (default)
- EmbeddingSearchStrategy: Semantic search via FastEmbed (optional)
"""

from __future__ import annotations

from typing import Protocol

from ya_agent_sdk.toolsets.tool_search.metadata import ToolMetadata


class SearchStrategy(Protocol):
    """Protocol for pluggable tool search strategies.

    Implementations must provide a `search` method that takes a query string
    and a list of candidate ToolMetadata, returning ranked results.

    Optionally implement `build_index` for strategies that need pre-computation
    (e.g., embedding vectors).
    """

    def build_index(self, tools: list[ToolMetadata]) -> None:
        """Build or rebuild the search index from tool metadata.

        Called when the tool registry changes. Strategies that need
        pre-computation (e.g., embeddings) should implement this.

        Strategies that don't need pre-computation can implement this as ``pass``.
        """
        ...

    def search(
        self,
        query: str,
        candidates: list[ToolMetadata],
        max_results: int = 5,
    ) -> list[ToolMetadata]:
        """Search candidate tools and return ranked results.

        Args:
            query: The search query (natural language or regex pattern).
            candidates: The pool of tools to search through.
            max_results: Maximum number of results to return.

        Returns:
            List of matching ToolMetadata, ranked by relevance.
        """
        ...


__all__ = [
    "SearchStrategy",
]
