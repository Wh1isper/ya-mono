"""Configuration management using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class AgentSettings(BaseSettings):
    """Configuration for agents with environment variable support.

    All settings can be overridden via environment variables with the prefix YA_AGENT_.
    For example, to set working_dir, use YA_AGENT_WORKING_DIR=/path/to/dir.
    """

    model_config = SettingsConfigDict(
        env_prefix="YA_AGENT_",
        env_file=(_PACKAGE_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    image_understanding_model: str | None = None
    """Model to use for image understanding when native vision is unavailable."""

    image_understanding_model_settings: str | None = None
    """Model settings preset name for image understanding (e.g. 'anthropic_off'). Resolved via resolve_model_settings."""

    video_understanding_model: str | None = None
    """Model to use for video understanding when native capability is unavailable."""

    video_understanding_model_settings: str | None = None
    """Model settings preset name for video understanding (e.g. 'anthropic_off'). Resolved via resolve_model_settings."""

    audio_understanding_model: str | None = None
    """Model to use for audio understanding when native capability is unavailable."""

    audio_understanding_model_settings: str | None = None
    """Model settings preset name for audio understanding (e.g. 'gemini_thinking_level_low'). Resolved via resolve_model_settings."""

    compact_model: str | None = None
    """Model to use for compact when native capability is unavailable."""
