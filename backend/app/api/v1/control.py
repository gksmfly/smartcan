# app/api/v1/control.py

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.mqtt.client import mqtt_client
from app.schemas.cycle import CycleCreate
from app.services import cycles_service, recipes_service
from app.ml.lstm_a import compute_next_valve_time
from app.ws.bus import ws_bus

router = APIRouter(prefix="/control", tags=["control"])


# ===== 현재 RFID가 선택한 SKU 상태(앱 UI용) =====

class CurrentSku(BaseModel):
    sku_id: str | None = None


# 간단히 메모리 보관(데모용). 실제 운영이면 DB/Redis 권장
current_sku_state = CurrentSku(sku_id=None)


@router.get("/current_sku", response_model=CurrentSku)
def get_current_sku():
    return current_sku_state


@router.post("/current_sku", response_model=CurrentSku)
def set_current_sku(req: CurrentSku):
    current_sku_state.sku_id = req.sku_id
    return current_sku_state


# ===== 충전 요청(앱/시뮬레이터) =====

class FillRequest(BaseModel):
    sku_id: str
    mode: str = "NORMAL"


class FillResponse(BaseModel):
    sku_id: str
    cycle_no: int
    target_amount: float
    predicted_next_amount: float
    valve_ms: float
    status: str = "REQUESTED"


@router.post("/fill", response_model=FillResponse)
def request_fill(req: FillRequest, db: Session = Depends(get_db)):
    recipe = recipes_service.get_recipe_by_sku_id(db, req.sku_id)
    if not recipe:
        raise HTTPException(404, "Recipe not found")

    target_amount = float(recipe.target_amount)

    # 다음 시퀀스
    last_seq = cycles_service.get_last_seq_for_sku(db, req.sku_id) + 1

    # LSTM-A(+R2R)로 밸브 시간 계산
    valve_ms = float(compute_next_valve_time(db, sku_id=req.sku_id, target_amount=target_amount))

    # DB에 cycle 생성(충전 전 상태)
    cycles_service.create_cycle(
        db,
        CycleCreate(
            seq=last_seq,
            sku=req.sku_id,
            target_ml=target_amount,
            valve_ms=valve_ms,
            actual_ml=None,
            error=None,
            next_valve_ms=None,
            spc_state=None,
        ),
    )

    # UNO로 fill 명령(MQTT)
    payload = {
        "sku": req.sku_id,
        "seq": last_seq,
        "target_ml": target_amount,
        "valve_ms": valve_ms,
        "mode": req.mode,
    }
    mqtt_client.publish_fill_command(payload)

    # Option C: 관리자 WS로도 기록(요청 이벤트)
    ws_bus.emit({
        "type": "fill_requested",
        "ts": int(time.time()),
        "data": {
            "sku_id": req.sku_id,
            "seq": last_seq,
            "target_ml": target_amount,
            "valve_ms": valve_ms,
            "mode": req.mode,
        },
    })

    return FillResponse(
        sku_id=req.sku_id,
        cycle_no=last_seq,
        target_amount=target_amount,
        predicted_next_amount=target_amount,  # (데모) 목표량 기반
        valve_ms=valve_ms,
    )


# ===== 보정 버튼(end-to-end) =====

class CorrectionRequest(BaseModel):
    sku_id: str


class CorrectionResponse(BaseModel):
    sku_id: str
    status: str = "CORRECTION_APPLIED"


@router.post("/apply_correction", response_model=CorrectionResponse)
def apply_correction(req: CorrectionRequest):
    """안드로이드/관리자 UI에서 '오차 보정' 버튼 눌렀을 때.

    - 서버: 보정 명령을 MQTT(line1/cmd/corr)로 publish
    - 브리지: UNO에 'CORR\n' 전달
    - UNO: 파란 LED + 355/355 표시 + (다음 Fill을 OK로 만드는 로직은 UNO에서 correctionPending=true로 처리)
    """

    payload = {"sku": req.sku_id, "cmd": "CORR"}
    mqtt_client.publish_corr_command(payload)

    ws_bus.emit({
        "type": "corr_issued",
        "ts": int(time.time()),
        "data": {"sku_id": req.sku_id},
    })

    return CorrectionResponse(sku_id=req.sku_id)
