# app/api/v1/quality.py

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.quality import SpcCurrentState, SpcStateOut
from app.services import quality_service

router = APIRouter(prefix="/quality", tags=["quality"])


@router.get("/spc_state", response_model=SpcCurrentState)
def get_spc_state(
    sku: str,
    db: Session = Depends(get_db),
):
    """
    특정 SKU의 현재 SPC/CUSUM 상태 조회.

    - 마지막 fill_result까지 반영된 상태로
    - compute_spc_for_sku를 한 번 더 호출해서 최신 상태를 계산한다.
    """
    info = quality_service.compute_spc_for_sku(db, sku=sku)
    # info(dict) 안에 spc_state, alarm_type, mean, std, cusum_pos, cusum_neg, n_samples 포함
    return SpcCurrentState(**info)


@router.get("/spc_states", response_model=List[SpcStateOut])
def get_spc_states(
    sku: str,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    특정 SKU의 SPC 상태 히스토리 조회 (/quality/spc_states).
    """
    rows = quality_service.list_spc_states(db, sku=sku, limit=limit)
    return rows
