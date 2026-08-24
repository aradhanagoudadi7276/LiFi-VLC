import asyncio
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    """Manages concurrent WebSocket connections to broadcast real-time telemetry."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, data: dict):
        if not self.active_connections:
            return
            
        # Create a snapshot copy of connections to avoid modification errors during broadcast
        targets = list(self.active_connections)
        
        # Async broadcast to all connected web clients
        tasks = [self._safe_send(ws, data) for ws in targets]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_send(self, websocket: WebSocket, data: dict):
        try:
            await websocket.send_json(data)
        except Exception:
            # Client disconnected unexpectedly or connection broken
            self.disconnect(websocket)


# Global singleton instance
ws_manager = WebSocketManager()
