# app/main.py

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import Base, engine
from app.db import models  # noqa: F401

from app.api.v1 import recipes as recipes_router
from app.api.v1 import cycles as cycles_router
from app.api.v1 import control as control_router
from app.api.v1 import quality as quality_router
from app.api.v1 import alarms as alarms_router

from app.api import ws as ws_router
from app.api import admin_page as admin_page_router

from app.mqtt.client import mqtt_client
from app.ml.lstm_a import get_lstm_a_model
from app.ml.lstm_b import load_lstm_b_model
from app.ws.bus import ws_bus


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME)

    # SQLite/PG 등 DB 테이블 생성
    Base.metadata.create_all(bind=engine)

    origins = [
        origin.strip()
        for origin in settings.BACKEND_CORS_ORIGINS.split(",")
        if origin.strip()
    ]
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # REST API
    app.include_router(recipes_router.router, prefix="/api/v1")
    app.include_router(cycles_router.router, prefix="/api/v1")
    app.include_router(control_router.router, prefix="/api/v1")
    app.include_router(quality_router.router, prefix="/api/v1")
    app.include_router(alarms_router.router, prefix="/api/v1")

    # Option C: WebSocket + 관리자 최소 페이지
    app.include_router(ws_router.router)
    app.include_router(admin_page_router.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.on_event("startup")
    async def on_startup():
        # WS EventBus는 FastAPI 이벤트 루프에 묶어둠
        ws_bus.set_loop(asyncio.get_running_loop())
        asyncio.create_task(ws_bus.run())

        # MQTT 클라이언트 시작 (별도 스레드)
        mqtt_client.start()

        # ML 모델/컨트롤러 초기화
        get_lstm_a_model()
        model_path = Path(__file__).resolve().parent / "ml" / "lstm_b.pt"
        load_lstm_b_model(str(model_path))

    return app


app = create_app()
