# app/ws/manager.py

from __future__ import annotations

from typing import Set

from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 연결 관리 + 브로드캐스트"""

    def __init__(self) -> None:
        self._active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._active:
            self._active.remove(ws)

    async def broadcast_json(self, payload: dict) -> None:
        dead = []
        for ws in list(self._active):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()
