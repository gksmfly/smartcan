# app/ml/generate_initial_cycles.py

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.cycle import Cycle
import random

def generate_initial_cycles(
    sku="CIDER_500",
    target=355.0,
    max_ml=500.0,
    base_ms=1000,
    K=1.2,
    noise=0.05,
    count=30
):
    """
    LSTM-A 학습을 위한 초기 cycle 데이터 자동 생성 (v2)
    - 완전히 선형 모델 기반
    - random noise 포함으로 학습 다양성 증가
    - 과충전 → 정상 수렴 패턴 생성
    """

    print("=== Generating initial cycles for LSTM-A training ===")
    db: Session = SessionLocal()

    # 기존 CIDER 데이터 삭제
    db.query(Cycle).filter(Cycle.sku == sku).delete()
    db.commit()

    seq = 1
    valve_ms = base_ms  # 첫 cycle은 1000ms (과충전 상태)

    for i in range(count):
        ratio = valve_ms / base_ms
        actual = max_ml * max(min(ratio, 1.0), 0.0)

        # 실제 기기 편차 흉내
        actual *= (1.0 + random.uniform(-noise, noise))

        # 오차
        error = actual - target

        # 오차 기반 next valve_ms
        next_valve = valve_ms - K * error
        next_valve = max(80, min(next_valve, 2000))

        # DB insert
        cycle = Cycle(
            seq=seq,
            sku=sku,
            target_ml=target,
            actual_ml=actual,
            valve_ms=valve_ms,
            next_valve_ms=next_valve,
            error=error,
            spc_state="SIM_INIT_V2",
        )
        db.add(cycle)
        db.commit()

        print(
            f"Cycle {seq:02d}: valve={valve_ms:.1f}, "
            f"actual={actual:.1f}, err={error:.1f}, next={next_valve:.1f}"
        )

        seq += 1
        valve_ms = next_valve

    db.close()
    print("=== Initial cycle generation complete ===")