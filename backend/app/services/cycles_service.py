# app/services/cycles_service.py

from typing import List, Optional, Dict, Any
from app.services import quality_service

from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.db.models.cycle import Cycle
from app.schemas.cycle import CycleCreate

from app.services import line_state_service

def create_cycle(db: Session, data: CycleCreate) -> Cycle:
    cycle = Cycle(
        seq=data.seq,
        sku=data.sku,
        target_ml=data.target_ml,
        actual_ml=data.actual_ml,
        valve_ms=data.valve_ms,
        error=data.error,
        next_valve_ms=data.next_valve_ms,
        spc_state=data.spc_state,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def list_cycles(
    db: Session,
    sku: Optional[str] = None,
    limit: int = 50,
) -> List[Cycle]:
    stmt = select(Cycle).order_by(desc(Cycle.created_at)).limit(limit)
    if sku:
        stmt = stmt.where(Cycle.sku == sku)
    stmt = stmt.order_by(desc(Cycle.id)).limit(limit)    
    return list(db.scalars(stmt))
def _fallback_target_ml(db: Session, sku: str) -> float:
    # 1) 같은 sku의 마지막 cycle target_ml 재사용 (없으면 0.0)
    stmt = (
        select(Cycle.target_ml)
        .where(Cycle.sku == sku, Cycle.target_ml.is_not(None))
        .order_by(desc(Cycle.id))
        .limit(1)
    )
    last = db.execute(stmt).scalar_one_or_none()
    return float(last) if last is not None else 0.0

def get_cycle_by_id(db: Session, cycle_id: int) -> Optional[Cycle]:
    return db.get(Cycle, cycle_id)


def get_recent_cycles_for_sku(
    db: Session,
    sku: str,
    limit: int = 50,
) -> List[Cycle]:
    stmt = (
        select(Cycle)
        .where(Cycle.sku == sku)
        .order_by(desc(Cycle.created_at))
        .limit(limit)
    )
    rows = list(db.scalars(stmt))
    rows.reverse()
    return rows


def get_last_seq_for_sku(db: Session, sku: str) -> int:
    stmt = (
        select(Cycle.seq)
        .where(Cycle.sku == sku)
        .order_by(desc(Cycle.seq))
        .limit(1)
    )
    last = db.execute(stmt).scalar_one_or_none()
    return last or 0


# MQTT 이벤트용 헬퍼들

def _find_cycle_by_seq_and_sku(
    db: Session,
    seq: int,
    sku: str,
) -> Optional[Cycle]:
    stmt = (
        select(Cycle)
        .where(Cycle.seq == seq, Cycle.sku == sku)
        .limit(1)
    )
    return db.scalars(stmt).first()


def log_can_in_event(db: Session, payload: Dict[str, Any]) -> Cycle:
    """
    MQTT: line1/event/can_in
    payload 예:
    {"seq":12,"sku":"COKE_355"}
    또는 {"seq":12,"sku":"COKE_355","target_ml":355.0}
    """
    seq = payload.get("seq") or payload.get("can_seq") or payload.get("cycle_no")
    sku = payload.get("sku") or payload.get("sku_id")

    if seq is None or sku is None:
        raise ValueError(f"invalid can_in payload: {payload}")

    seq = int(seq)
    sku = str(sku)

    # target_ml 은 없어도 됨(태깅은 보통 sku/seq만 옴)
    raw_target = payload.get("target_ml") or payload.get("target_amount")
    try:
        target_ml = float(raw_target) if raw_target is not None else 0.0
    except Exception:
        target_ml = 0.0

    if target_ml <= 0:
        target_ml = _fallback_target_ml(db, sku)

    valve_ms = payload.get("valve_ms") or payload.get("valve_time")
    try:
        valve_ms = float(valve_ms) if valve_ms is not None else 0.0
    except Exception:
        valve_ms = 0.0

    existing = _find_cycle_by_seq_and_sku(db, seq=seq, sku=sku)
    if existing:
        existing.target_ml = target_ml
        existing.valve_ms = valve_ms
        db.add(existing)
        db.commit()
        db.refresh(existing)
        # current_sku 갱신(시그니처 차이 방어)
        try:
            line_state_service.set_current_sku(db, line_id="line1", sku=sku)
        except TypeError:
            line_state_service.set_current_sku(db, sku=sku)
        return existing

    cycle = Cycle(
        seq=seq,
        sku=sku,
        target_ml=target_ml,
        actual_ml=None,
        valve_ms=valve_ms,
        error=None,
        next_valve_ms=None,
        spc_state=None,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    try:
        line_state_service.set_current_sku(db, line_id="line1", sku=sku)
    except TypeError:
        line_state_service.set_current_sku(db, sku=sku)

    return cycle


def log_fill_result_event(db: Session, payload: Dict[str, Any]) -> Cycle:
    """
    MQTT: line1/event/fill_result
    payload 예:
    {
      "seq": 12,
      "sku": "COKE_355",
      "actual_ml": 352.1,
      "target_ml": 355.0,
      "valve_ms": 1234.0,
      "status": "OK"
    }
    """
    seq = payload.get("seq") or payload.get("can_seq")
    sku = payload.get("sku") or payload.get("sku_id")
    actual_ml = payload.get("actual_ml") or payload.get("measured_value")
    target_ml = payload.get("target_ml") or payload.get("target_amount")
    valve_ms = payload.get("valve_ms")

    if seq is None or sku is None or actual_ml is None or valve_ms is None:
        raise ValueError(f"invalid fill_result payload: {payload}")

    cycle = _find_cycle_by_seq_and_sku(db, seq=seq, sku=sku)
    if not cycle:
        cycle = Cycle(
            seq=seq,
            sku=sku,
            target_ml=target_ml or actual_ml,
            actual_ml=actual_ml,
            valve_ms=valve_ms,
            error=None,
            next_valve_ms=None,
            spc_state=None,
        )
    else:
        cycle.actual_ml = actual_ml
        cycle.valve_ms = valve_ms
        if target_ml is not None:
            cycle.target_ml = target_ml

    if cycle.actual_ml is not None and cycle.target_ml is not None:
        cycle.error = cycle.actual_ml - cycle.target_ml

    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    
    line_state_service.set_current_sku(db, sku=cycle.sku)

    
    return cycle
