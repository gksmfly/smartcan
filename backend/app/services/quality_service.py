# app/services/quality_service.py

from typing import Dict, Any, List, Optional
import json
import paho.mqtt.publish as mqtt_publish

from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from app.core.config import settings
from app.db.models.cycle import Cycle
from app.db.models.quality import SpcState, Alarm
from app.ml import lstm_b


MQTT_ALARM_TOPIC = "line1/event/alarm"


def get_recent_errors_for_sku(db: Session, sku: str, limit: int = 100) -> List[float]:
    stmt = (
        select(Cycle.error)
        .where(Cycle.sku == sku, Cycle.error.is_not(None))
        .order_by(desc(Cycle.id))
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return list(reversed(rows))


def publish_spc_alarm_mqtt(
    sku: str,
    level: str,
    alarm_type: Optional[str],
    cycle_id: Optional[int],
) -> None:
    payload = {"sku": sku, "level": level, "alarm_type": alarm_type, "cycle_id": cycle_id}
    try:
        mqtt_publish.single(
            MQTT_ALARM_TOPIC,
            json.dumps(payload, ensure_ascii=False),
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
        )
        print(f"[SPC] MQTT alarm publish -> {MQTT_ALARM_TOPIC}: {payload}")
    except Exception as e:
        print(f"[SPC] MQTT alarm publish failed: {e!r}")


def compute_spc_for_sku(db: Session, sku: str) -> Dict[str, Any]:
    """
    ✅ 중복 방지 버전

    - 같은 last_cycle_id에 대해 여러 번 호출되어도
      SpcState/Alarm을 "새로 insert"하지 않고 "갱신"한다.
    - Alarm은 "새로 생성되는 경우에만" MQTT publish 한다.
    """
    errors = get_recent_errors_for_sku(db, sku=sku, limit=100)
    info = lstm_b.get_spc_state_from_errors(errors)

    # 가장 최근 Cycle 찾기
    last_cycle_stmt = (
        select(Cycle)
        .where(Cycle.sku == sku)
        .order_by(desc(Cycle.id))
        .limit(1)
    )
    last_cycle = db.scalars(last_cycle_stmt).first()

    # 사이클이 아예 없으면 계산 결과만 리턴(쓰기 없음)
    if not last_cycle:
        return info

    last_cycle_id = last_cycle.id

    # 1) cycles.spc_state 업데이트 (같은 사이클이면 값만 덮어씀)
    last_cycle.spc_state = info.get("spc_state")
    db.add(last_cycle)

    # 2) SpcState UPSERT: (sku, last_cycle_id) 기준으로 1개만 유지
    spc_state_stmt = (
        select(SpcState)
        .where(SpcState.sku == sku, SpcState.last_cycle_id == last_cycle_id)
        .order_by(desc(SpcState.id))
        .limit(1)
    )
    spc_state_row = db.scalars(spc_state_stmt).first()

    if spc_state_row:
        # 기존 row 갱신
        spc_state_row.spc_state = info.get("spc_state")
        spc_state_row.alarm_type = info.get("alarm_type")
        spc_state_row.mean = info.get("mean")
        spc_state_row.std = info.get("std")
        spc_state_row.cusum_pos = info.get("cusum_pos")
        spc_state_row.cusum_neg = info.get("cusum_neg")
        spc_state_row.n_samples = info.get("n_samples")
        db.add(spc_state_row)
    else:
        # 새 row 생성(새 사이클에 대해서만 1번)
        spc_state_row = SpcState(
            sku=sku,
            spc_state=info.get("spc_state"),
            alarm_type=info.get("alarm_type"),
            mean=info.get("mean"),
            std=info.get("std"),
            cusum_pos=info.get("cusum_pos"),
            cusum_neg=info.get("cusum_neg"),
            n_samples=info.get("n_samples"),
            last_cycle_id=last_cycle_id,
        )
        db.add(spc_state_row)
        db.flush()  # id 확보

    # 3) Alarm UPSERT + MQTT (새 알람일 때만 publish)
    created_new_alarm = False
    if info.get("spc_state") in ("WARN", "ALARM"):
        level = info.get("spc_state")
        alarm_type = info.get("alarm_type")

        alarm_stmt = (
            select(Alarm)
            .where(
                Alarm.sku == sku,
                Alarm.level == level,
                Alarm.alarm_type == alarm_type,
                Alarm.cycle_id == last_cycle_id,
            )
            .order_by(desc(Alarm.id))
            .limit(1)
        )
        alarm_row = db.scalars(alarm_stmt).first()

        if alarm_row:
            # 기존 알람이면 spc_state_id만 최신으로 연결(중복 insert 금지)
            alarm_row.spc_state_id = spc_state_row.id
            alarm_row.message = f"SPC {level} ({alarm_type}) for SKU {sku}"
            db.add(alarm_row)
        else:
            alarm_row = Alarm(
                sku=sku,
                level=level,
                alarm_type=alarm_type,
                message=f"SPC {level} ({alarm_type}) for SKU {sku}",
                cycle_id=last_cycle_id,
                spc_state_id=spc_state_row.id,
            )
            db.add(alarm_row)
            created_new_alarm = True

    db.commit()

    # commit 성공 후, 새 알람일 때만 publish
    if created_new_alarm:
        publish_spc_alarm_mqtt(
            sku=sku,
            level=info.get("spc_state"),
            alarm_type=info.get("alarm_type"),
            cycle_id=last_cycle_id,
        )

    return info


def list_spc_states(db: Session, sku: str, limit: int = 50) -> List[SpcState]:
    stmt = (
        select(SpcState)
        .where(SpcState.sku == sku)
        .order_by(desc(SpcState.id))
        .limit(limit)
    )
    return db.scalars(stmt).all()


def list_alarms(db: Session, sku: Optional[str] = None, limit: int = 50) -> List[Alarm]:
    stmt = select(Alarm)
    if sku:
        stmt = stmt.where(Alarm.sku == sku)
    stmt = stmt.order_by(desc(Alarm.id)).limit(limit)
    return db.scalars(stmt).all()


def get_alarm_by_id(db: Session, alarm_id: int) -> Optional[Alarm]:
    stmt = select(Alarm).where(Alarm.id == alarm_id).limit(1)
    return db.scalars(stmt).first()


def read_current_spc_state(db: Session, sku: str) -> dict:
    # (읽기 전용) 최신 spc_states 1건만 반환
    stmt = (
        select(SpcState)
        .where(SpcState.sku == sku)
        .order_by(desc(SpcState.id))
        .limit(1)
    )
    row = db.scalars(stmt).first()

    if not row:
        return dict(
            spc_state="UNKNOWN",
            alarm_type=None,
            mean=None,
            std=None,
            cusum_pos=0.0,
            cusum_neg=0.0,
            n_samples=0,
        )

    return dict(
        spc_state=row.spc_state,
        alarm_type=row.alarm_type,
        mean=row.mean,
        std=row.std,
        cusum_pos=row.cusum_pos,
        cusum_neg=row.cusum_neg,
        n_samples=row.n_samples,
    )
