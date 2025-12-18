# app/api/ws.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.manager import ws_manager

router = APIRouter(tags=["ws"])


@router.websocket("/ws/admin")
async def ws_admin(ws: WebSocket):
    """관리자 대시보드용 WebSocket.

    서버는 이벤트를 push만 하면 되고, 클라이언트 메시지는 사용하지 않아도 된다.
    """
    await ws_manager.connect(ws)
    try:
        while True:
            # keep-alive용 수신 루프 (클라이언트에서 ping 보내도 됨)
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)
