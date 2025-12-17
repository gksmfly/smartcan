# app/schemas/cycle.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CycleBase(BaseModel):
    seq: int = Field(..., description="캔 시퀀스 번호")
    sku: str = Field(..., description="음료 SKU ID (Recipe.sku_id)")
    target_ml: float = Field(..., description="목표 충전량(ml)")
    valve_ms: float = Field(..., description="이번 사이클 밸브 시간(ms)")


class CycleCreate(CycleBase):
    actual_ml: Optional[float] = Field(None, description="실제 충전량(ml)")
    error: Optional[float] = None
    next_valve_ms: Optional[float] = None
    spc_state: Optional[str] = None


class CycleOut(CycleBase):
    id: int
    actual_ml: Optional[float] = None
    error: Optional[float] = None
    next_valve_ms: Optional[float] = None
    spc_state: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True