# app/schemas/recipe.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class RecipeBase(BaseModel):
    sku_id: str = Field(..., example="COKE_355")
    name: str = Field(..., example="코카콜라 355ml")
    target_amount: float = Field(..., example=355.0)
    base_valve_ms: float = Field(..., example=1200.0)
    description: Optional[str] = Field(None, example="기본 콜라 캔 레시피")
    is_active: bool = True


class RecipeCreate(RecipeBase):
    pass


class RecipeUpdate(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    base_valve_ms: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RecipeOut(RecipeBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True