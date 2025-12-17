# app/api/v1/alarms.py

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.quality import AlarmOut
from app.services import quality_service

router = APIRouter(prefix="/alarms", tags=["alarms"])


@router.get("/recent", response_model=List[AlarmOut])
def get_recent_alarms(
    sku: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    최근 알람 리스트 조회.

    - sku 가 주어지면 해당 SKU 알람만
    - 안 주면 전체 알람 중 최근 limit 개
    """
    rows = quality_service.list_alarms(db, sku=sku, limit=limit)
    return rows


@router.get("/{alarm_id}", response_model=AlarmOut)
def get_alarm_detail(
    alarm_id: int,
    db: Session = Depends(get_db),
):
    """
    알람 단건 상세 조회 (/alarms/{alarm_id})
    """
    alarm = quality_service.get_alarm_by_id(db, alarm_id=alarm_id)
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarm not found")
    return alarm
