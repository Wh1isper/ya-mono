import httpx
from pydantic_ai.models import (
    get_user_agent,
)
from pydantic_ai.retries import AsyncTenacityTransport, RetryConfig
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential


def create_async_http_client(
    *,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 900,
    connect: int = 5,
    read: int = 300,
) -> httpx.AsyncClient:
    """Create a new httpx.AsyncClient with optional extra headers.

    Each call creates a new client instance. The caller is responsible for
    the client's lifecycle (closing it when done). For gateway providers,
    the client lives for the agent's lifetime and is cleaned up on process exit.

    Args:
        extra_headers: Additional headers to include in all requests.
            Useful for sticky routing via x-session-id header.
        timeout: Total timeout in seconds.
        connect: Connection timeout in seconds.
        read: Read timeout in seconds.

    Returns:
        A new httpx.AsyncClient instance.
    """
    headers = {"User-Agent": get_user_agent()}
    if extra_headers:
        headers.update(extra_headers)

    return httpx.AsyncClient(
        transport=AsyncTenacityTransport(
            config=RetryConfig(
                retry=retry_if_exception_type((
                    httpx.HTTPError,
                    httpx.StreamError,
                )),
                wait=wait_exponential(multiplier=1, max=10),
                stop=stop_after_attempt(10),
                reraise=True,
            )
        ),
        timeout=httpx.Timeout(timeout=timeout, connect=connect, read=read),
        headers=headers,
    )
