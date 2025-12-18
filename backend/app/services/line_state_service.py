# app/services/line_state_service.py
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

def set_current_sku(db: Session, sku: str, line_id: str = "line1") -> None:
    db.execute(text("""
        INSERT INTO line_state(line_id, current_sku)
        VALUES (:line_id, :sku)
        ON CONFLICT (line_id)
        DO UPDATE SET current_sku = EXCLUDED.current_sku, updated_at = now()
    """), {"line_id": line_id, "sku": sku})
    db.commit()

def get_current_sku(db: Session, line_id: str = "line1") -> Optional[str]:
    row = db.execute(
        text("SELECT current_sku FROM line_state WHERE line_id = :line_id"),
        {"line_id": line_id},
    ).scalar_one_or_none()
    return row
