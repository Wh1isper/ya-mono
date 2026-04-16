"""Audio reading tool for models without native audio understanding support.

This tool allows processing audio when the model does not support
native audio understanding capabilities.
"""

from typing import Annotated

from pydantic import Field
from pydantic_ai import RunContext

from ya_agent_sdk.agents.audio_understanding import get_audio_description
from ya_agent_sdk.context import AgentContext
from ya_agent_sdk.toolsets.core.base import BaseTool


class ReadAudioTool(BaseTool):
    """Tool for reading and analyzing audio files.

    Use this tool when the model does not support native audio understanding
    but needs to process audio content from URLs.
    """

    name = "read_audio"
    description = "Read and analyze audio from a URL. Use when native audio understanding is unavailable."

    async def get_instruction(self, ctx: RunContext[AgentContext]) -> str | None:
        """No instruction needed for this tool."""
        return None

    def is_available(self, ctx: RunContext[AgentContext]) -> bool:
        return not ctx.deps.model_cfg.has_audio_understanding

    async def call(
        self,
        ctx: RunContext[AgentContext],
        url: Annotated[
            str,
            Field(description="The URL of the audio to read and analyze."),
        ],
    ) -> str:
        """Read and analyze audio from a URL.

        Args:
            ctx: The run context containing the agent context.
            url: The URL of the audio to analyze.

        Returns:
            A text description or transcription of the audio content.
        """
        agent_ctx = ctx.deps

        # Get model and settings from tool_config if available
        model = None
        model_settings = None
        if agent_ctx.tool_config:
            tool_config = agent_ctx.tool_config
            model = tool_config.audio_understanding_model
            model_settings = tool_config.audio_understanding_model_settings

        description, internal_usage = await get_audio_description(
            audio_url=url,
            model=model,
            model_settings=model_settings,
            model_wrapper=agent_ctx.model_wrapper,
            wrapper_metadata=agent_ctx.get_wrapper_metadata(),
        )

        # Store usage in extra_usages with tool_call_id
        if ctx.tool_call_id:
            agent_ctx.add_extra_usage(agent="audio_understanding", internal_usage=internal_usage, uuid=ctx.tool_call_id)

        return description
