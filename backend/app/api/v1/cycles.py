# app/api/v1/cycles.py

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cycle import CycleCreate, CycleOut
from app.services import cycles_service

router = APIRouter(prefix="/cycles", tags=["cycles"])


@router.post("/", response_model=CycleOut)
def create_cycle_endpoint(
    data: CycleCreate,
    db: Session = Depends(get_db),
):
    return cycles_service.create_cycle(db, data)


@router.get("/", response_model=List[CycleOut])
def list_cycles_endpoint(
    sku: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    return cycles_service.list_cycles(db, sku=sku, limit=limit)


@router.get("/{cycle_id}", response_model=CycleOut)
def get_cycle_endpoint(
    cycle_id: int,
    db: Session = Depends(get_db),
):
    cycle = cycles_service.get_cycle_by_id(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Cycle not found")
    return cycle