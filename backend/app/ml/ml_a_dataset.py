# app/ml/ml_a_dataset.py

import numpy as np

def build_lstm_a_dataset(cycles, window_size=5, K=1.2):
    """
    cycles → DB Cycle 리스트
    output X → (N, window, 3)
    output y → (N,)  (오차 기반 next valve_ms)
    """

    # 정렬
    cycles = sorted(cycles, key=lambda x: x.seq)

    feats = []
    labels = []

    for c in cycles:
        actual = float(c.actual_ml if c.actual_ml is not None else c.target_ml)
        valve  = float(c.valve_ms)
        target = float(c.target_ml)

        # 오차
        error = actual - target

        # next valve_ms (제어기 타깃)
        valve_next = valve - K * error
        valve_next = max(80, min(valve_next, 2000))

        feats.append([actual, valve, target])
        labels.append(valve_next)

    feats = np.array(feats, dtype=np.float32)
    labels = np.array(labels, dtype=np.float32)

    if len(feats) <= window_size:
        raise ValueError("Not enough cycle data for LSTM-A dataset")

    X, y = [], []

    for i in range(window_size, len(feats)):
        X.append(feats[i - window_size:i])
        y.append(labels[i])

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)