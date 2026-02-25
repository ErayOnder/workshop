"""
In-memory SSE pub/sub bus keyed by session_id.

Background tasks call publish(); SSE endpoint handlers subscribe/unsubscribe.
All operations happen in the same event loop so plain asyncio.Queue works fine.
"""
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# session_id -> list of per-connection queues
_listeners: dict[str, list[asyncio.Queue]] = {}


def subscribe(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _listeners.setdefault(session_id, []).append(q)
    return q


def unsubscribe(session_id: str, q: asyncio.Queue) -> None:
    subs = _listeners.get(session_id, [])
    try:
        subs.remove(q)
    except ValueError:
        pass
    if not subs:
        _listeners.pop(session_id, None)


async def publish(session_id: str, event: str, data: dict[str, Any]) -> None:
    for q in list(_listeners.get(session_id, [])):
        await q.put({"event": event, "data": data})
