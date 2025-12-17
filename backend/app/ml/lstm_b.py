# app/ml/lstm_b.py

from __future__ import annotations

from typing import Dict, Any, Sequence, Optional

import numpy as np

from .ml_b_model import LSTMB
from .ml_b_spc import compute_spc_cusum


# 글로벌 LSTM-B 모델 핸들 (옵션, 없으면 CUSUM-only 모드)
LSTM_B_MODEL: Optional[LSTMB] = None


def load_lstm_b_model(model_path: str) -> None:
    """주어진 경로에서 학습된 LSTM-B 모델을 로드해
    전역 LSTM_B_MODEL 변수에 올린다.

    model_path 가 비어 있거나 파일이 존재하지 않으면
    아무 것도 하지 않고 CUSUM-only 모드로 동작한다.
    """
    import os

    global LSTM_B_MODEL

    if not model_path:
        return

    if not os.path.exists(model_path):
        # 학습된 모델이 아직 없는 경우에는 그냥 None 유지
        return

    # torch는 여기서만 지연 임포트해서, 서버 기동 시 한 번만 불러오도록 한다.
    import torch

    model = LSTMB()
    state = torch.load(model_path, map_location="cpu")

    # state_dict 만 저장된 경우와, {'state_dict': ...} 형태 둘 다 대응
    if isinstance(state, dict) and "state_dict" in state:
        state = state["state_dict"]

    model.load_state_dict(state)
    model.eval()

    LSTM_B_MODEL = model
    print(f"[LSTM-B] 모델 로드 완료: {model_path}")


def get_spc_state_from_errors(errors: Sequence[float]) -> Dict[str, Any]:
    """최근 error 시계열을 받아 SPC/CUSUM 상태를 계산한다.

    현재 구현은 error 전체를 표준화한 뒤 CUSUM 통계를 계산하고,
    결과를 기반으로 OK / WARN / ALARM 상태를 판정한다.
    (LSTM-B는 현재 학습/분석용으로만 사용하고, 실시간 SPC 입력은 error 기반)
    """
    # numpy array 로 변환
    errors_arr = np.asarray(list(errors), dtype=float)

    # 샘플이 전혀 없는 경우: UNKNOWN
    if errors_arr.size == 0:
        info = {
            "spc_state": "UNKNOWN",
            "alarm_type": None,
            "mean": None,
            "std": None,
            "cusum_pos": 0.0,
            "cusum_neg": 0.0,
            "n_samples": 0,
        }
        return info

    # CUSUM 기반 SPC 계산 (OK / WARN / ALARM)
    info = compute_spc_cusum(errors_arr)
    info["n_samples"] = int(errors_arr.size)

    return info
