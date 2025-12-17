# app/api/v1/control.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.services import cycles_service, recipes_service
from app.ml.lstm_a import get_lstm_a_model
from app.services.r2r import compute_next_valve_time
from app.mqtt.client import mqtt_client
from app.schemas.cycle import CycleCreate

router = APIRouter(prefix="/control", tags=["control"])

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

    recent = cycles_service.get_recent_cycles_for_sku(db, req.sku_id, 50)

    lstm = get_lstm_a_model()
    predicted = lstm.predict_next(recipe, recent)

    valve_ms = predicted

    last_seq = cycles_service.get_last_seq_for_sku(db, req.sku_id) + 1

    cycles_service.create_cycle(
        db,
        CycleCreate(
            seq=last_seq,
            sku=req.sku_id,
            target_ml=recipe.target_amount,
            valve_ms=valve_ms,
            actual_ml=None
        )
    )

    payload = {
        "sku": req.sku_id,
        "seq": last_seq,
        "target_ml": recipe.target_amount,
        "valve_ms": valve_ms,
        "mode": req.mode,
    }

    mqtt_client.publish_fill_command(payload)

    return FillResponse(
        sku_id=req.sku_id,
        cycle_no=last_seq,
        target_amount=recipe.target_amount,
        predicted_next_amount=predicted,
        valve_ms=valve_ms,
    )