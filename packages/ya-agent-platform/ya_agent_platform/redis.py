from __future__ import annotations

from redis.asyncio import Redis


def create_redis_client(redis_url: str, *, health_check_interval: int = 30) -> Redis:
    return Redis.from_url(redis_url, health_check_interval=health_check_interval)
