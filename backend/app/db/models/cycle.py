# app/db/models/cycle.py

from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.db.session import Base


class Cycle(Base):
    """
    한 번의 충전 사이클 로그.
    - seq: 라인 내에서의 캔 시퀀스 번호
    - sku: Recipe.sku_id (음료 SKU)
    """
    __tablename__ = "cycles"

    id = Column(Integer, primary_key=True, index=True)
    seq = Column(Integer, index=True, nullable=False)
    sku = Column(String(32), index=True, nullable=False)

    target_ml = Column(Float, nullable=False)
    actual_ml = Column(Float, nullable=True)
    valve_ms = Column(Float, nullable=False)

    error = Column(Float, nullable=True)
    next_valve_ms = Column(Float, nullable=True)

    spc_state = Column(String(32), nullable=True)  # OK / WARN / ALARM 등

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )