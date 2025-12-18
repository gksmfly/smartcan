# app/db/models/recipe.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func
from app.db.session import Base


class Recipe(Base):
    """
    한 SKU(음료 종류)에 대한 레시피.
    """
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)

    sku_id = Column(String(32), unique=True, index=True, nullable=False)
    name = Column(String(64), nullable=False)

    target_amount = Column(Float, nullable=False)      # 목표 충전량(ml)
    base_valve_ms = Column(Float, nullable=False)      # 기본 밸브 시간(ms)

    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="1")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )