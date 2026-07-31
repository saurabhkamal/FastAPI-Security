import time
from typing import Any

_TTL_SECONDS = 300
_cache: dict[tuple[str, str, str], tuple[float, Any]] = {}


def get_cached_response(scope: str, idempotency_key: str | None, identity: str) -> Any | None:
    """Returns a previously stored result for this (scope, key, identity) if still fresh."""
    if not idempotency_key:
        return None

    key = (scope, idempotency_key, identity)
    entry = _cache.get(key)
    if entry is None:
        return None

    expires_at, result = entry
    if time.time() > expires_at:
        del _cache[key]
        return None

    return result


def store_response(scope: str, idempotency_key: str | None, identity: str, result: Any) -> None:
    if not idempotency_key:
        return
    _cache[(scope, idempotency_key, identity)] = (time.time() + _TTL_SECONDS, result)


def reset_idempotency_cache() -> None:
    _cache.clear()
