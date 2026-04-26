from __future__ import annotations

import inspect
import logging
import sys
from types import FrameType
from urllib.parse import urlsplit, urlunsplit

from loguru import logger

_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
_INTERCEPTED_LOGGER_NAMES = (
    "alembic",
    "asyncio",
    "fastapi",
    "uvicorn",
    "uvicorn.error",
)
_QUIET_LOGGER_LEVELS = {
    "sqlalchemy": logging.WARNING,
    "sqlalchemy.engine": logging.WARNING,
    "sqlalchemy.pool": logging.WARNING,
    "uvicorn.access": logging.WARNING,
}


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = inspect.currentframe()
        depth = 2
        while isinstance(frame, FrameType):
            module_name = frame.f_globals.get("__name__", "")
            if module_name == __name__ or module_name.startswith("logging"):
                frame = frame.f_back
                depth += 1
                continue
            break

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_claw_logging(log_level: str | None) -> None:
    normalized_level = _normalize_log_level(log_level)
    logger.remove()
    logger.add(
        sys.stderr,
        level=normalized_level,
        format=_LOG_FORMAT,
        colorize=sys.stderr.isatty(),
        backtrace=False,
        diagnose=False,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    logging.root.setLevel(_stdlib_log_level(normalized_level))
    for logger_name in _INTERCEPTED_LOGGER_NAMES:
        stdlib_logger = logging.getLogger(logger_name)
        stdlib_logger.handlers.clear()
        stdlib_logger.propagate = True
        stdlib_logger.setLevel(0)
    for logger_name, level in _QUIET_LOGGER_LEVELS.items():
        stdlib_logger = logging.getLogger(logger_name)
        stdlib_logger.handlers.clear()
        stdlib_logger.propagate = True
        stdlib_logger.setLevel(level)


def redact_url(raw_url: str) -> str:
    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return "<redacted-url>"
    if "@" not in parts.netloc:
        return raw_url
    _, _, host_part = parts.netloc.rpartition("@")
    return urlunsplit((parts.scheme, f"***:***@{host_part}", parts.path, parts.query, parts.fragment))


def _normalize_log_level(log_level: str | None) -> str:
    normalized = (log_level or "INFO").strip().upper() or "INFO"
    try:
        logger.level(normalized)
    except ValueError:
        return "INFO"
    return normalized


def _stdlib_log_level(log_level: str) -> int:
    level = logging.getLevelName(log_level)
    return level if isinstance(level, int) else logging.INFO
