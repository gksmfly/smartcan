# app/db/models/r2r_state.py

from sqlalchemy import Column, Integer, Float, DateTime, func, String
from app.db.session import Base


class R2RState(Base):
    """
    R2R 보정 히스토리 (제어 로그)
    """
    __tablename__ = "r2r_states"

    id = Column(Integer, primary_key=True, index=True)
    seq = Column(Integer, index=True, nullable=False)
    sku = Column(String(32), index=True, nullable=False)

    prev_valve_ms = Column(Float, nullable=False)
    error = Column(Float, nullable=False)
    K = Column(Float, nullable=False)
    next_valve_ms = Column(Float, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )