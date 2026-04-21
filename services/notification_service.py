"""
In-process WebSocket fan-out for news events.
"""

from typing import List

from fastapi import WebSocket
from logger_config import logger


class NewsWebSocketManager:
    """Track browser connections and broadcast JSON payloads."""

    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info("News WebSocket client connected (%s)", len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info("News WebSocket client disconnected (%s)", len(self._connections))

    async def broadcast(self, message: dict) -> None:
        stale: List[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception as exc:
                logger.debug("WebSocket send failed: %s", exc)
                stale.append(ws)
        for ws in stale:
            self.disconnect(ws)


news_ws_manager = NewsWebSocketManager()
