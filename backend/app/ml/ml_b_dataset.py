import pandas as pd
import numpy as np

# LSTM-B 입력 시퀀스 길이 (최근 몇 개 샘플을 한 번에 볼지)
SEQ_LEN = 20


def load_fills_for_lstmB(df: pd.DataFrame) -> pd.DataFrame:
    """DB에서 SELECT 해 온 fills DataFrame을 입력으로 받아
    LSTM-B 학습에 필요한 feature 컬럼을 추가한다.

    기대하는 컬럼:
      - ts        : timestamp
      - line_id   : 문자열 (예: 'LINE1')
      - recipe_id : 정수
      - target_ml : 실수
      - actual_ml : 실수
    """

    df = df.copy()

    # 오차(error) 컬럼
    df["error_ml"] = df["actual_ml"] - df["target_ml"]

    # 범주형을 인덱스로 인코딩 (one-hot 대신 간단 인덱스로 시작)
    df["recipe_idx"] = df["recipe_id"].astype("category").cat.codes
    df["line_idx"] = df["line_id"].astype("category").cat.codes

    return df


def make_sequences(df: pd.DataFrame, seq_len: int = SEQ_LEN):
    """LSTM-B 학습용 시퀀스 생성.

    feature: [error_ml, recipe_idx, line_idx]
    target : 다음 step의 error_ml
    """

    features = []
    targets = []

    arr_err = df["error_ml"].to_numpy()
    arr_rec = df["recipe_idx"].to_numpy()
    arr_line = df["line_idx"].to_numpy()

    for i in range(len(df) - seq_len):
        x_err = arr_err[i:i + seq_len]
        x_rec = arr_rec[i:i + seq_len]
        x_line = arr_line[i:i + seq_len]

        # (seq_len, 3) 형태
        x = np.stack([x_err, x_rec, x_line], axis=-1)
        y = arr_err[i + seq_len]

        features.append(x)
        targets.append(y)

    if not features:
        return np.empty((0, seq_len, 3)), np.empty((0,))

    X = np.stack(features)
    y = np.stack(targets)
    return X, y
