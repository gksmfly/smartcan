# app/schemas/quality.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SpcCurrentState(BaseModel):
    """
    /quality/spc_state 응답용 현재 SPC 상태.
    """
    spc_state: str = Field(..., description="현재 SPC 상태 (OK / WARN / ALARM / UNKNOWN 등)")
    alarm_type: Optional[str] = Field(None, description="알람 종류 (POS_DRIFT / NEG_DRIFT / None)")
    mean: Optional[float] = Field(None, description="오차 평균")
    std: Optional[float] = Field(None, description="오차 표준편차")
    cusum_pos: float = Field(..., description="양의 방향 CUSUM 값")
    cusum_neg: float = Field(..., description="음의 방향 CUSUM 값")
    n_samples: int = Field(..., description="SPC 계산에 사용된 샘플 개수")


class SpcStateOut(BaseModel):
    """
    spc_states 테이블 1건을 나타내는 스키마.
    """
    id: int
    sku: str
    spc_state: str
    alarm_type: Optional[str] = None
    mean: Optional[float] = None
    std: Optional[float] = None
    cusum_pos: Optional[float] = None
    cusum_neg: Optional[float] = None
    n_samples: Optional[int] = None
    last_cycle_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
        orm_mode = True


class AlarmOut(BaseModel):
    """
    alarms 테이블 1건을 나타내는 스키마.
    """
    id: int
    sku: str
    level: str
    alarm_type: Optional[str] = None
    message: Optional[str] = None
    cycle_id: Optional[int] = None
    spc_state_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
        orm_mode = True
