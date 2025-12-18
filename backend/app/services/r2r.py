# app/services/r2r.py

from typing import List, Optional

from statistics import mean

from app.db.models.cycle import Cycle
from app.db.models.recipe import Recipe


def compute_next_valve_time(
    recipe: Recipe,
    recent_cycles: List[Cycle],
    predicted_next_amount: Optional[float] = None,
    k_gain: float = 0.3,
    window_size: int = 10,
) -> float:
    """
    최근 N개 오차 기반 R2R 보정:

    - last_valve_ms: 최근 사이클의 밸브 시간
                     (없으면 recipe.base_valve_ms 사용)
    - error: 최근 N개 사이클의 error 평균
             (error = actual_ml - target_ml)
             만약 error가 아직 없다면 predicted_next_amount 로부터
             error ≈ predicted_next_amount - recipe.target_amount 로 추정
    - next_valve = last_valve_ms + k_gain * mean_error
    """
    # 1. 기준 밸브 시간
    if recent_cycles:
        last_cycle = recent_cycles[-1]
        last_valve = last_cycle.valve_ms or recipe.base_valve_ms
    else:
        last_valve = recipe.base_valve_ms

    # 2. 최근 window_size개 error 평균
    errors = [
        c.error
        for c in recent_cycles[-window_size:]
        if c.error is not None
    ]

    if errors:
        mean_error = float(mean(errors))
    elif predicted_next_amount is not None:
        mean_error = float(predicted_next_amount - recipe.target_amount)
    else:
        mean_error = 0.0

    next_valve = float(last_valve + k_gain * mean_error)

    # 3. 안전 범위 클램핑
    if next_valve < 100.0:
        next_valve = 100.0
    if next_valve > 5000.0:
        next_valve = 5000.0

    return next_valve