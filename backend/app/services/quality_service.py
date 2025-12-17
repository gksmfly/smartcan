# app/services/quality_service.py

from typing import Dict, Any, List, Optional

import json

from sqlalchemy.orm import Session
from sqlalchemy import select, desc

import paho.mqtt.publish as mqtt_publish

from app.core.config import settings
from app.db.models.cycle import Cycle
from app.db.models.quality import SpcState, Alarm
from app.ml import lstm_b


MQTT_ALARM_TOPIC = "line1/event/alarm"


def get_recent_errors_for_sku(db: Session, sku: str, limit: int = 100) -> List[float]:
    """
    특정 SKU에 대해 최근 error 시계열을 가져온다.
    최신 사이클부터 limit개를 읽어서, 오래된 순으로 리턴.
    """
    stmt = (
        select(Cycle.error)
        .where(Cycle.sku == sku, Cycle.error.is_not(None))
        .order_by(desc(Cycle.id))
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    # DB에서는 id DESC 로 가져왔으므로, 시간 순으로 쓰려면 역순 정렬
    errors: List[float] = list(reversed(rows))
    return errors


def publish_spc_alarm_mqtt(
    sku: str,
    level: str,
    alarm_type: Optional[str],
    cycle_id: Optional[int],
) -> None:
    """
    SPC 알람을 MQTT로 publish (옵션 기능).
    """
    payload = {
        "sku": sku,
        "level": level,
        "alarm_type": alarm_type,
        "cycle_id": cycle_id,
    }
    try:
        mqtt_publish.single(
            MQTT_ALARM_TOPIC,
            json.dumps(payload, ensure_ascii=False),
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
        )
        print(f"[SPC] MQTT alarm publish -> {MQTT_ALARM_TOPIC}: {payload}")
    except Exception as e:
        # 알람 publish 실패해도 서비스 전체가 죽지 않게 그냥 로그만 찍고 무시
        print(f"[SPC] MQTT alarm publish failed: {e!r}")


def compute_spc_for_sku(db: Session, sku: str) -> Dict[str, Any]:
    """
    1) 최근 error 시계열을 가져와서
    2) LSTM-B + CUSUM 모듈로 SPC 상태를 계산하고
    3) 결과를 cycles.spc_state, spc_states, alarms 테이블에 반영한다.
    """
    errors = get_recent_errors_for_sku(db, sku=sku, limit=100)
    info = lstm_b.get_spc_state_from_errors(errors)

    # 1) 가장 최근 Cycle의 spc_state 업데이트
    last_cycle_stmt = (
        select(Cycle)
        .where(Cycle.sku == sku)
        .order_by(desc(Cycle.id))
        .limit(1)
    )
    last_cycle = db.scalars(last_cycle_stmt).first()

    if last_cycle:
        last_cycle.spc_state = info.get("spc_state")
        db.add(last_cycle)

    # 2) SpcState 레코드 저장
    spc_state_row = SpcState(
        sku=sku,
        spc_state=info.get("spc_state"),
        alarm_type=info.get("alarm_type"),
        mean=info.get("mean"),
        std=info.get("std"),
        cusum_pos=info.get("cusum_pos"),
        cusum_neg=info.get("cusum_neg"),
        n_samples=info.get("n_samples"),
        last_cycle_id=last_cycle.id if last_cycle else None,
    )
    db.add(spc_state_row)
    db.flush()  # spc_state_row.id 확보

    # 3) 알람이 필요한 경우 alarms 테이블에 기록 + MQTT publish
    if info.get("spc_state") in ("WARN", "ALARM"):
        alarm_row = Alarm(
            sku=sku,
            level=info.get("spc_state"),
            alarm_type=info.get("alarm_type"),
            message=f"SPC {info.get('spc_state')} ({info.get('alarm_type')}) for SKU {sku}",
            cycle_id=last_cycle.id if last_cycle else None,
            spc_state_id=spc_state_row.id,
        )
        db.add(alarm_row)

        publish_spc_alarm_mqtt(
            sku=sku,
            level=info.get("spc_state"),
            alarm_type=info.get("alarm_type"),
            cycle_id=last_cycle.id if last_cycle else None,
        )

    db.commit()

    return info

def list_spc_states(db: Session, sku: str, limit: int = 50) -> List[SpcState]:
    """
    특정 SKU에 대한 최근 SPC 상태 기록 조회.
    """
    stmt = (
        select(SpcState)
        .where(SpcState.sku == sku)
        .order_by(desc(SpcState.id))
        .limit(limit)
    )
    return db.scalars(stmt).all()


def list_alarms(db: Session, sku: Optional[str] = None, limit: int = 50) -> List[Alarm]:
    """
    최근 알람 리스트 조회.
    sku 가 주어지면 해당 SKU만, 없으면 전체 알람 중 최근 것.
    """
    stmt = select(Alarm)
    if sku:
        stmt = stmt.where(Alarm.sku == sku)
    stmt = stmt.order_by(desc(Alarm.id)).limit(limit)
    return db.scalars(stmt).all()


def get_alarm_by_id(db: Session, alarm_id: int) -> Optional[Alarm]:
    """
    알람 단건 조회.
    """
    stmt = select(Alarm).where(Alarm.id == alarm_id).limit(1)
    return db.scalars(stmt).first()