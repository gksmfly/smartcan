# app/main.py

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

from app.mqtt.client import mqtt_client
from pathlib import Path
from app.ml.lstm_a import get_lstm_a_model
from app.ml.lstm_b import load_lstm_b_model

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
    )

    # PostgreSQL에 테이블 생성
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

    app.include_router(
        recipes_router.router,
        prefix="/api/v1",
    )
    app.include_router(
        cycles_router.router,
        prefix="/api/v1",
    )
    app.include_router(
        control_router.router,
        prefix="/api/v1",
    )
    app.include_router(
        quality_router.router,
        prefix="/api/v1",
    )
    app.include_router(
        alarms_router.router,
        prefix="/api/v1",
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.on_event("startup")
    def on_startup():
        # MQTT 클라이언트 시작
        mqtt_client.start()
        # LSTM-A 컨트롤러 싱글톤 초기화
        get_lstm_a_model()
        # LSTM-B 모델 로드 (있으면)
        model_path = Path(__file__).resolve().parent / "ml" / "lstm_b.pt"
        load_lstm_b_model(str(model_path))

    return app


app = create_app()