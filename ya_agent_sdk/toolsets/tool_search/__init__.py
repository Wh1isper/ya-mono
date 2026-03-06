"""Tool search toolset for dynamic tool loading.

Provides ToolSearchToolSet, a wrapper over multiple AbstractToolsets that
enables dynamic tool discovery via a model-callable ``tool_search`` tool.

Toolsets with ``id`` are treated as namespaces (atomic loading);
toolsets without ``id`` provide loose tools (individual loading).
State is stored in AgentContext for automatic session restore.

Usage::

    from ya_agent_sdk.toolsets.tool_search import ToolSearchToolSet

    search_toolset = ToolSearchToolSet(
        toolsets=[arxiv_toolset, github_toolset, misc_toolset],
        namespace_descriptions={"arxiv": "Search academic papers"},
    )
"""

from ya_agent_sdk.toolsets.tool_search.metadata import ToolMetadata, extract_metadata_from_schema
from ya_agent_sdk.toolsets.tool_search.strategies import SearchStrategy
from ya_agent_sdk.toolsets.tool_search.strategies.keyword import KeywordSearchStrategy
from ya_agent_sdk.toolsets.tool_search.toolset import ToolSearchToolSet

__all__ = [
    "KeywordSearchStrategy",
    "SearchStrategy",
    "ToolMetadata",
    "ToolSearchToolSet",
    "extract_metadata_from_schema",
]


# EmbeddingSearchStrategy is available via __getattr__ below (requires fastembed).
# Not in __all__ because it is an optional dependency.


def __getattr__(name: str):
    """Lazy import for optional EmbeddingSearchStrategy."""
    if name == "EmbeddingSearchStrategy":
        from ya_agent_sdk.toolsets.tool_search.strategies.embedding import EmbeddingSearchStrategy

        return EmbeddingSearchStrategy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
