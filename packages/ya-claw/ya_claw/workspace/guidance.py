from __future__ import annotations

import logging
from dataclasses import dataclass
from html import escape
from pathlib import Path

from ya_claw.workspace.provider import WorkspaceBinding

logger = logging.getLogger(__name__)

WORKSPACE_GUIDANCE_FILENAME = "AGENTS.md"
WORKSPACE_GUIDANCE_TAG = "workspace-guidance"


@dataclass(slots=True)
class WorkspaceGuidance:
    host_path: Path
    virtual_path: Path
    content: str


def load_workspace_guidance(binding: WorkspaceBinding) -> WorkspaceGuidance | None:
    guidance_path = binding.host_path / WORKSPACE_GUIDANCE_FILENAME
    if not guidance_path.is_file():
        return None

    try:
        content = guidance_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "Failed to read workspace guidance file",
            extra={"path": str(guidance_path), "error": str(exc)},
        )
        return None
    except UnicodeDecodeError as exc:
        logger.warning(
            "Failed to decode workspace guidance file",
            extra={"path": str(guidance_path), "error": str(exc)},
        )
        return None

    if content.strip() == "":
        return None

    return WorkspaceGuidance(
        host_path=guidance_path,
        virtual_path=binding.virtual_path / WORKSPACE_GUIDANCE_FILENAME,
        content=content,
    )


def format_workspace_guidance(guidance: WorkspaceGuidance) -> str:
    path = escape(str(guidance.virtual_path), quote=True)
    return f'<{WORKSPACE_GUIDANCE_TAG} path="{path}">\n{guidance.content}\n</{WORKSPACE_GUIDANCE_TAG}>'
