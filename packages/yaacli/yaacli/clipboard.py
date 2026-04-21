"""System clipboard helpers for YAACLI TUI paste handling."""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import sys
from dataclasses import dataclass

from ya_agent_sdk.utils import detect_image_media_type

_SUPPORTED_MEDIA_TYPES: tuple[str, ...] = (
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
)


@dataclass(frozen=True)
class ClipboardImage:
    """Image content read from the system clipboard."""

    data: bytes
    media_type: str


@dataclass(frozen=True)
class ClipboardImageReadResult:
    """Clipboard image read outcome."""

    image: ClipboardImage | None
    error: str | None = None


async def _run_command(args: list[str], timeout_seconds: float = 2.0) -> tuple[int, bytes, bytes]:
    """Run a subprocess and capture stdout/stderr."""
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except TimeoutError:
        process.kill()
        stdout, stderr = await process.communicate()
        return 124, stdout, b"clipboard command timed out"

    returncode = process.returncode if process.returncode is not None else 1
    return returncode, stdout, stderr


async def _read_macos_clipboard_image() -> ClipboardImageReadResult:
    if shutil.which("pngpaste") is None:
        return ClipboardImageReadResult(
            image=None,
            error="Clipboard image paste requires pngpaste on macOS.",
        )

    returncode, stdout, _stderr = await _run_command(["pngpaste", "-"])
    if returncode != 0 or not stdout:
        return ClipboardImageReadResult(image=None)

    media_type = detect_image_media_type(stdout) or "image/png"
    return ClipboardImageReadResult(image=ClipboardImage(data=stdout, media_type=media_type))


async def _read_wayland_clipboard_image() -> ClipboardImageReadResult:
    if shutil.which("wl-paste") is None:
        return ClipboardImageReadResult(
            image=None,
            error="Clipboard image paste requires wl-paste on Wayland.",
        )

    returncode, stdout, _stderr = await _run_command(["wl-paste", "--list-types"])
    if returncode != 0:
        return ClipboardImageReadResult(image=None)

    available_types = {line.strip() for line in stdout.decode("utf-8", errors="ignore").splitlines() if line.strip()}
    for media_type in _SUPPORTED_MEDIA_TYPES:
        if media_type not in available_types:
            continue
        read_returncode, image_bytes, _read_stderr = await _run_command([
            "wl-paste",
            "--no-newline",
            "--type",
            media_type,
        ])
        if read_returncode == 0 and image_bytes:
            detected_type = detect_image_media_type(image_bytes) or media_type
            return ClipboardImageReadResult(image=ClipboardImage(data=image_bytes, media_type=detected_type))

    return ClipboardImageReadResult(image=None)


async def _read_x11_clipboard_image() -> ClipboardImageReadResult:
    if shutil.which("xclip") is None:
        return ClipboardImageReadResult(
            image=None,
            error="Clipboard image paste requires xclip on X11.",
        )

    returncode, stdout, _stderr = await _run_command(["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"])
    if returncode != 0:
        return ClipboardImageReadResult(image=None)

    available_types = {line.strip() for line in stdout.decode("utf-8", errors="ignore").splitlines() if line.strip()}
    for media_type in _SUPPORTED_MEDIA_TYPES:
        if media_type not in available_types:
            continue
        read_returncode, image_bytes, _read_stderr = await _run_command([
            "xclip",
            "-selection",
            "clipboard",
            "-t",
            media_type,
            "-o",
        ])
        if read_returncode == 0 and image_bytes:
            detected_type = detect_image_media_type(image_bytes) or media_type
            return ClipboardImageReadResult(image=ClipboardImage(data=image_bytes, media_type=detected_type))

    return ClipboardImageReadResult(image=None)


async def _read_windows_clipboard_image() -> ClipboardImageReadResult:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell is None:
        return ClipboardImageReadResult(
            image=None,
            error="Clipboard image paste requires PowerShell on Windows.",
        )

    command = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "Add-Type -AssemblyName System.Drawing; "
        "if (-not [System.Windows.Forms.Clipboard]::ContainsImage()) { exit 0 }; "
        "$image = [System.Windows.Forms.Clipboard]::GetImage(); "
        "$stream = New-Object System.IO.MemoryStream; "
        "$image.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png); "
        "[Convert]::ToBase64String($stream.ToArray())"
    )
    returncode, stdout, _stderr = await _run_command([powershell, "-NoProfile", "-Command", command])
    if returncode != 0:
        return ClipboardImageReadResult(image=None)

    payload = stdout.decode("utf-8", errors="ignore").strip()
    if not payload:
        return ClipboardImageReadResult(image=None)

    image_bytes = base64.b64decode(payload)
    media_type = detect_image_media_type(image_bytes) or "image/png"
    return ClipboardImageReadResult(image=ClipboardImage(data=image_bytes, media_type=media_type))


async def read_clipboard_image() -> ClipboardImageReadResult:
    """Read an image from the system clipboard when available."""
    if sys.platform == "darwin":
        return await _read_macos_clipboard_image()

    if sys.platform.startswith("win"):
        return await _read_windows_clipboard_image()

    if sys.platform.startswith("linux"):
        errors: list[str] = []
        if os.environ.get("WAYLAND_DISPLAY"):
            result = await _read_wayland_clipboard_image()
            if result.image is not None:
                return result
            if result.error:
                errors.append(result.error)
        if os.environ.get("DISPLAY"):
            result = await _read_x11_clipboard_image()
            if result.image is not None:
                return result
            if result.error:
                errors.append(result.error)
        if errors:
            return ClipboardImageReadResult(image=None, error=" ".join(dict.fromkeys(errors)))
        return ClipboardImageReadResult(
            image=None,
            error="Clipboard image paste requires wl-paste on Wayland or xclip on X11.",
        )

    return ClipboardImageReadResult(
        image=None,
        error=f"Clipboard image paste is not supported on platform: {sys.platform}.",
    )
