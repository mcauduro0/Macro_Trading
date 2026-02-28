"""WebSocket API endpoints with ConnectionManager.

Provides real-time WebSocket channels for:
- /ws/signals   -- Live trading signal updates
- /ws/portfolio -- Portfolio position and P&L updates
- /ws/alerts    -- System alerts and notifications

Usage from other modules:
    from src.api.routes.websocket_api import manager
    await manager.broadcast("alerts", {"type": "risk_breach", "message": "VaR limit exceeded"})
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


# ---------------------------------------------------------------------------
# ConnectionManager -- tracks active WebSocket connections per channel
# ---------------------------------------------------------------------------
class ConnectionManager:
    """Manages WebSocket connections grouped by named channels.

    Attributes:
        active: Dict mapping channel names to sets of connected WebSocket instances.
    """

    def __init__(self) -> None:
        self.active: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """Accept a WebSocket connection and add it to the specified channel.

        Args:
            websocket: The WebSocket connection to accept.
            channel: Channel name to register the connection under.
        """
        await websocket.accept()
        if channel not in self.active:
            self.active[channel] = set()
        self.active[channel].add(websocket)
        logger.info(
            "websocket_connected channel=%s total=%d",
            channel,
            len(self.active[channel]),
        )

    def disconnect(self, websocket: WebSocket, channel: str) -> None:
        """Remove a WebSocket connection from a channel.

        Args:
            websocket: The WebSocket connection to remove.
            channel: Channel name to remove the connection from.
        """
        if channel in self.active:
            self.active[channel].discard(websocket)
            logger.info(
                "websocket_disconnected channel=%s remaining=%d",
                channel,
                len(self.active[channel]),
            )

    async def broadcast(self, channel: str, message: dict[str, Any]) -> None:
        """Send a JSON message to all connected clients on a channel.

        Disconnected clients are automatically cleaned up.

        Args:
            channel: Channel name to broadcast to.
            message: Dict payload to send as JSON.
        """
        if channel not in self.active:
            return

        disconnected: list[WebSocket] = []
        payload = json.dumps(message)

        for websocket in self.active[channel]:
            try:
                await websocket.send_text(payload)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected clients
        for ws in disconnected:
            self.active[channel].discard(ws)
            logger.debug("websocket_cleaned_stale channel=%s", channel)

    @property
    def channel_counts(self) -> dict[str, int]:
        """Return the number of active connections per channel."""
        return {ch: len(conns) for ch, conns in self.active.items()}


# Module-level singleton
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# WebSocket endpoints
# ---------------------------------------------------------------------------
@router.websocket("/ws/signals")
async def signals_websocket(websocket: WebSocket):
    """WebSocket endpoint for live trading signal updates.

    Clients receive real-time signal broadcasts from the signal aggregation
    pipeline. Sends keepalive pings and accepts incoming messages.
    """
    await manager.connect(websocket, "signals")
    try:
        while True:
            # Receive messages (keepalive / subscription control)
            data = await websocket.receive_text()
            logger.debug("ws_signals_received data=%s", data[:100] if data else "")
    except WebSocketDisconnect:
        manager.disconnect(websocket, "signals")


@router.websocket("/ws/portfolio")
async def portfolio_websocket(websocket: WebSocket):
    """WebSocket endpoint for portfolio position and P&L updates.

    Clients receive real-time portfolio state changes including position
    updates, equity changes, and risk metric deltas.
    """
    await manager.connect(websocket, "portfolio")
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("ws_portfolio_received data=%s", data[:100] if data else "")
    except WebSocketDisconnect:
        manager.disconnect(websocket, "portfolio")


@router.websocket("/ws/alerts")
async def alerts_websocket(websocket: WebSocket):
    """WebSocket endpoint for system alerts and notifications.

    Clients receive risk breach alerts, strategy status changes,
    data pipeline failures, and other operational notifications.
    """
    await manager.connect(websocket, "alerts")
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("ws_alerts_received data=%s", data[:100] if data else "")
    except WebSocketDisconnect:
        manager.disconnect(websocket, "alerts")
