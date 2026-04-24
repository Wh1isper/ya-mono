"""Filters for message history processing.

This module provides history processors for pydantic-ai agents.
"""

from ya_agent_sdk.filters._builders import (
    KEEP_COMPACT,
    KEEP_HANDOFF,
    KEEP_TAG_KEY,
    build_context_restored_part,
    build_original_request_parts,
    build_steering_parts,
    has_keep_tag,
)
from ya_agent_sdk.filters.auto_load_files import process_auto_load_files
from ya_agent_sdk.filters.background_shell import inject_background_results
from ya_agent_sdk.filters.cold_start import cold_start_trim
from ya_agent_sdk.filters.environment_instructions import create_environment_instructions_filter
from ya_agent_sdk.filters.handoff import process_handoff_message
from ya_agent_sdk.filters.image import drop_extra_images, drop_extra_videos, drop_gif_images, split_large_images
from ya_agent_sdk.filters.media_upload import create_media_upload_filter
from ya_agent_sdk.filters.reasoning_normalize import normalize_reasoning_for_model
from ya_agent_sdk.filters.system_prompt import create_system_prompt_filter
from ya_agent_sdk.filters.tool_args import fix_truncated_tool_args

__all__ = [
    "KEEP_COMPACT",
    "KEEP_HANDOFF",
    "KEEP_TAG_KEY",
    "build_context_restored_part",
    "build_original_request_parts",
    "build_steering_parts",
    "cold_start_trim",
    "create_environment_instructions_filter",
    "create_media_upload_filter",
    "create_system_prompt_filter",
    "drop_extra_images",
    "drop_extra_videos",
    "drop_gif_images",
    "fix_truncated_tool_args",
    "has_keep_tag",
    "inject_background_results",
    "normalize_reasoning_for_model",
    "process_auto_load_files",
    "process_handoff_message",
    "split_large_images",
]
