# app/ws/bus.py

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from app.ws.manager import ws_manager


class WsEventBus:
    """MQTT(별도 스레드) → FastAPI(WebSocket)로 이벤트를 안전하게 전달하는 버스.

    - MQTT 콜백은 다른 스레드에서 실행되므로, asyncio loop에 직접 await 하면 충돌 가능.
    - emit()은 call_soon_threadsafe로 Queue에 넣고,
    - run()은 FastAPI 이벤트루프에서 Queue를 소비하면서 브로드캐스트.
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def emit(self, event: Dict[str, Any]) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, event)

    async def run(self) -> None:
        while True:
            event = await self._queue.get()
            await ws_manager.broadcast_json(event)


ws_bus = WsEventBus()
