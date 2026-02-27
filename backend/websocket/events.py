"""
WebSocket event helpers and utilities.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from core.logging import get_logger

logger = get_logger(__name__)

# Retry configuration for transient WS failures
_WS_MAX_RETRIES = 2
_WS_RETRY_BACKOFF_BASE = 0.1  # seconds


async def send_ws_event(
    websocket: WebSocket,
    event_type: str,
    data: Dict[str, Any] = None,
    run_id: str = None,
    session_id: str = None
) -> bool:
    """Send a WebSocket event with retry on transient failure.

    Retries up to ``_WS_MAX_RETRIES`` times with exponential back-off
    for transient errors (e.g. brief network hiccups).  Permanent
    disconnects are detected via ``WebSocketState`` and bail immediately.

    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Check connection state before sending
    try:
        if websocket.client_state != WebSocketState.CONNECTED:
            return False
    except Exception:
        pass

    message = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "data": data or {}
    }

    if run_id:
        message["run_id"] = run_id
    if session_id:
        message["session_id"] = session_id

    last_error = None
    for attempt in range(_WS_MAX_RETRIES + 1):
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            last_error = e
            # If socket is no longer connected, don't retry
            try:
                if websocket.client_state != WebSocketState.CONNECTED:
                    break
            except Exception:
                break
            if attempt < _WS_MAX_RETRIES:
                await asyncio.sleep(_WS_RETRY_BACKOFF_BASE * (2 ** attempt))

    logger.warning("ws_send_failed event=%s retries=%d error=%s",
                    event_type, _WS_MAX_RETRIES, last_error)
    return False
