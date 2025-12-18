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
    특정 SKU의 현재 SPC/CUSUM 상태 조회(읽기 전용).

    - 여기서는 compute/recompute 하지 않습니다. (GET은 DB에 쓰지 않음)
    - 마지막으로 계산되어 저장된 spc_states 중 최신 1건을 반환합니다.
    """
    rows = quality_service.list_spc_states(db, sku=sku, limit=1)

    if not rows:
        return SpcCurrentState(
            spc_state="UNKNOWN",
            alarm_type=None,
            mean=None,
            std=None,
            cusum_pos=0.0,
            cusum_neg=0.0,
            n_samples=0,
        )

    latest = rows[0]
    return SpcCurrentState(
        spc_state=latest.spc_state,
        alarm_type=getattr(latest, "alarm_type", None),
        mean=getattr(latest, "mean", None),
        std=getattr(latest, "std", None),
        cusum_pos=getattr(latest, "cusum_pos", 0.0),
        cusum_neg=getattr(latest, "cusum_neg", 0.0),
        n_samples=getattr(latest, "n_samples", 0),
    )


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
