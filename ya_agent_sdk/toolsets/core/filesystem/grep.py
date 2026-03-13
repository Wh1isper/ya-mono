"""Grep tool for content search."""

import json
import re
from functools import cache
from pathlib import Path
from typing import Annotated, Any, cast

from pydantic import Field
from pydantic_ai import RunContext
from y_agent_environment import FileOperator

from ya_agent_sdk._logger import get_logger
from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.toolsets.core.base import BaseTool
from ya_agent_sdk.toolsets.core.filesystem._gitignore import filter_gitignored
from ya_agent_sdk.toolsets.core.filesystem._types import GrepMatch
from ya_agent_sdk.toolsets.core.filesystem._utils import is_binary_file

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_MAX_RESULT_SIZE = 60000


@cache
def _load_instruction() -> str:
    """Load grep instruction from prompts/grep.md."""
    prompt_file = _PROMPTS_DIR / "grep.md"
    return prompt_file.read_text()


def _add_gitignore_info(results: dict[str, Any], gitignore_summary: list[str]) -> None:
    """Add gitignore exclusion info to results."""
    if gitignore_summary:
        results["<gitignore_excluded>"] = gitignore_summary
        results["<note>"] = "Some files excluded by .gitignore. Set include_ignored=true to include them."


def _truncate_results(results: dict[str, Any], gitignore_summary: list[str]) -> dict[str, Any]:
    """Truncate results by dropping context when too large."""
    logger.info("Results too long, dropping context")
    truncated: dict[str, Any] = {
        match: {
            "line_number": match_data["line_number"],
            "matching_line": match_data["matching_line"],
            "context_start_line": match_data["context_start_line"],
        }
        for match, match_data in results.items()
        if isinstance(match_data, dict) and "line_number" in match_data
    }
    truncated["<system>"] = "Results truncated. Use `view` to read specific files."
    _add_gitignore_info(truncated, gitignore_summary)
    return truncated


class GrepTool(BaseTool):
    """Tool for searching file contents using regular expressions."""

    name = "grep"
    description = "Search file contents using regex patterns. Returns matches with context lines."

    def is_available(self, ctx: RunContext[AgentContext]) -> bool:
        """Check if tool is available (requires file_operator)."""
        if ctx.deps.file_operator is None:
            logger.debug("GrepTool unavailable: file_operator is not configured")
            return False
        return True

    async def get_instruction(self, ctx: RunContext[AgentContext]) -> str | None:
        """Load instruction from prompts/grep.md."""
        return _load_instruction()

    def _search_file_for_matches(
        self,
        file_path: str,
        content: str,
        regex_pattern: re.Pattern[str],
        context_lines: int,
        max_matches_per_file: int,
    ) -> dict[str, GrepMatch]:
        """Search a single file for regex matches."""
        matches: dict[str, GrepMatch] = {}
        file_matches = 0

        lines = content.splitlines(keepends=True)

        for i, line in enumerate(lines):
            if regex_pattern.search(line):
                if max_matches_per_file > 0 and file_matches >= max_matches_per_file:
                    break

                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)

                context = "".join(lines[start:end])

                match_data = GrepMatch(
                    file_path=file_path,
                    line_number=i + 1,
                    matching_line=line.rstrip("\n"),
                    context=context,
                    context_start_line=start + 1,
                )

                matches[f"{file_path}:{i + 1}"] = match_data
                file_matches += 1

        return matches

    async def _check_file_searchable(
        self,
        file_operator: FileOperator,
        file_path: str,
        max_file_size: int,
    ) -> str | None:
        """Check if a file is searchable. Returns skip reason or None if OK."""
        if await file_operator.is_dir(file_path):
            return "directory"

        if max_file_size > 0:
            try:
                stat = await file_operator.stat(file_path)
                if stat["size"] > max_file_size:
                    return "too_large"
            except Exception:
                logger.debug(f"Failed to stat file, skipping size check: {file_path}", exc_info=True)

        try:
            if await is_binary_file(file_operator, file_path):
                return "binary"
        except Exception:
            logger.debug(f"Failed to check binary status: {file_path}", exc_info=True)

        return None

    async def _search_files(
        self,
        file_operator: FileOperator,
        files: list[str],
        compiled_pattern: re.Pattern[str],
        context_lines: int,
        max_results: int,
        max_matches_per_file: int,
        max_file_size: int = 0,
    ) -> tuple[dict[str, Any], int, list[str]]:
        """Search files and return (results, match_count, skipped_large_files)."""
        results: dict[str, Any] = {}
        total_matches_found = 0
        skipped_large_files: list[str] = []

        for file_path in files:
            skip_reason = await self._check_file_searchable(file_operator, file_path, max_file_size)
            if skip_reason == "too_large":
                skipped_large_files.append(file_path)
                continue
            if skip_reason:
                continue

            try:
                content = await file_operator.read_file(file_path)
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
                continue

            file_matches = self._search_file_for_matches(
                file_path, content, compiled_pattern, context_lines, max_matches_per_file
            )

            for match_key, match_data in file_matches.items():
                if max_results > 0 and total_matches_found >= max_results:
                    results["<system>"] = f"Hit global limit: {max_results} matches"
                    return results, total_matches_found, skipped_large_files

                results[match_key] = match_data
                total_matches_found += 1

        return results, total_matches_found, skipped_large_files

    async def call(
        self,
        ctx: RunContext[AgentContext],
        pattern: Annotated[str, Field(description="Regular expression pattern to search for")],
        include: Annotated[
            str,
            Field(description="Glob pattern to filter files (default: **/*)", default="**/*"),
        ] = "**/*",
        context_lines: Annotated[
            int,
            Field(description="Context lines before/after matches (default: 2)", default=2),
        ] = 2,
        max_results: Annotated[
            int,
            Field(description="Max total matches (default: 100, -1 for unlimited)", default=100),
        ] = 100,
        max_matches_per_file: Annotated[
            int,
            Field(description="Max matches per file (default: 20, -1 for unlimited)", default=20),
        ] = 20,
        max_files: Annotated[
            int,
            Field(description="Max files to search (default: 50, -1 for unlimited)", default=50),
        ] = 50,
        include_ignored: Annotated[
            bool,
            Field(description="Include files ignored by .gitignore (default: false)", default=False),
        ] = False,
    ) -> dict[str, Any] | str:
        """Search file contents using regular expressions."""
        file_operator = cast(FileOperator, ctx.deps.file_operator)

        try:
            compiled_pattern = re.compile(pattern, re.UNICODE)
        except re.error as e:
            return f"Error: Invalid regex pattern: {e}"

        files = await file_operator.glob(include)
        gitignore_summary: list[str] = []

        if not include_ignored:
            filter_result = await filter_gitignored(files, file_operator)
            files = filter_result.kept
            gitignore_summary = filter_result.get_ignored_summary(max_items=5)

        files_to_search = files[:max_files] if max_files > 0 else files

        max_file_size = ctx.deps.tool_config.grep_max_file_size

        results, total_matches, skipped_large_files = await self._search_files(
            file_operator,
            files_to_search,
            compiled_pattern,
            context_lines,
            max_results,
            max_matches_per_file,
            max_file_size,
        )

        logger.info(f"Total matches found: {total_matches}")
        if skipped_large_files:
            results["<skipped_large_files>"] = skipped_large_files
            results.setdefault("<note>", "")
            if results["<note>"]:
                results["<note>"] += " "
            results["<note>"] += (
                f"{len(skipped_large_files)} file(s) skipped due to size limit. "
                "Use shell `grep` command to search these files."
            )
        _add_gitignore_info(results, gitignore_summary)

        if len(json.dumps(results, default=str)) > _MAX_RESULT_SIZE:
            return _truncate_results(results, gitignore_summary)

        return results


__all__ = ["GrepTool"]
