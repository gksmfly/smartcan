# app/db/models/quality.py

from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.db.session import Base


class SpcState(Base):
    """
    SPC/CUSUM 상태 히스토리.
    - sku 단위로 spc_state, CUSUM 값 등을 저장한다.
    """
    __tablename__ = "spc_states"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(32), index=True, nullable=False)

    spc_state = Column(String(32), nullable=False)    # OK / WARN / ALARM / UNKNOWN 등
    alarm_type = Column(String(32), nullable=True)    # POS_DRIFT / NEG_DRIFT / None

    mean = Column(Float, nullable=True)
    std = Column(Float, nullable=True)
    cusum_pos = Column(Float, nullable=True)
    cusum_neg = Column(Float, nullable=True)
    n_samples = Column(Integer, nullable=True)

    last_cycle_id = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Alarm(Base):
    """
    SPC 기반 품질 알람 로그.
    """
    __tablename__ = "alarms"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String(32), index=True, nullable=False)

    level = Column(String(16), nullable=False)        # WARN / ALARM
    alarm_type = Column(String(32), nullable=True)    # POS_DRIFT / NEG_DRIFT / None
    message = Column(String(255), nullable=True)

    cycle_id = Column(Integer, nullable=True)
    spc_state_id = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
