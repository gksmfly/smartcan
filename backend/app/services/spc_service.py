# app/services/spc_service.py

from datetime import datetime
from sqlalchemy.orm import Session
from app.db.models import SpcState
from app.services.cycles_service import get_recent_cycles_for_sku

def recompute_spc_state(db: Session, sku: str):
    recent = get_recent_cycles_for_sku(db, sku=sku, limit=30)
    if not recent:
        return

    errors = [c.error for c in recent if c.error is not None]
    mean = sum(errors) / len(errors)
    std = (sum((e - mean) ** 2 for e in errors) / len(errors)) ** 0.5

    state = "ALARM" if abs(errors[-1]) > 5 else "NORMAL"

    spc = db.query(SpcState).filter_by(sku=sku).first()
    if not spc:
        spc = SpcState(sku=sku)
        db.add(spc)

    spc.spc_state = state
    spc.mean = mean
    spc.std = std
    spc.n_samples = len(errors)
    spc.updated_at = datetime.utcnow()