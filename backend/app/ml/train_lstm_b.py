"""
app/ml/train_lstm_b.py

DB에 쌓여 있는 cycles/recipes 데이터를 이용해
LSTM-B 모델을 학습하고 app/ml/lstm_b.pt 로 저장하는 스크립트.

사용법 (backend 폴더에서):

    $ source .venv/bin/activate
    $ python -m app.ml.train_lstm_b
"""

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import TensorDataset, DataLoader
import torch.nn as nn

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.cycle import Cycle
from app.db.models.recipe import Recipe
from app.ml.ml_b_dataset import load_fills_for_lstmB, make_sequences, SEQ_LEN
from app.ml.ml_b_model import LSTMB


MODEL_PATH = Path(__file__).with_name("lstm_b.pt")


def load_fills_df(db: Session) -> pd.DataFrame:
    """
    cycles + recipes 를 조인해서 LSTM-B 학습용 DataFrame 생성.

    컬럼:
      - ts        : timestamp
      - line_id   : 라인 ID (여기선 'LINE1' 고정)
      - recipe_id : Recipe.id
      - target_ml : Cycle.target_ml
      - actual_ml : Cycle.actual_ml
    """
    stmt = (
        select(
            Cycle.created_at.label("ts"),
            Cycle.sku.label("sku"),
            Recipe.id.label("recipe_id"),
            Cycle.target_ml.label("target_ml"),
            Cycle.actual_ml.label("actual_ml"),
        )
        .join(Recipe, Recipe.sku_id == Cycle.sku)
        .where(Cycle.actual_ml.is_not(None))
        .order_by(Cycle.created_at.asc())
    )

    rows = db.execute(stmt).all()
    if not rows:
        return pd.DataFrame()

    data = []
    for ts, sku, recipe_id, target_ml, actual_ml in rows:
        data.append(
            {
                "ts": ts,
                "line_id": "LINE1",  # 단일 라인 가정
                "recipe_id": recipe_id,
                "target_ml": float(target_ml),
                "actual_ml": float(actual_ml),
            }
        )

    return pd.DataFrame(data)


def train_lstm_b(model: LSTMB, loader: DataLoader, num_epochs: int = 20, lr: float = 1e-3):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    for epoch in range(num_epochs):
        model.train()
        epoch_loss = 0.0
        n = 0

        for x, y in loader:
            x = x.to(device)
            y = y.to(device)

            opt.zero_grad()
            y_hat = model(x)
            loss = loss_fn(y_hat, y)
            loss.backward()
            opt.step()

            batch_size = x.size(0)
            epoch_loss += loss.item() * batch_size
            n += batch_size

        print(f"[LSTM-B] epoch {epoch+1}/{num_epochs}, loss={epoch_loss / max(n, 1):.4f}")


def save_lstm_b(model: LSTMB, path: Path = MODEL_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)
    print(f"[LSTM-B] 모델 저장: {path}")


def main():
    # 1) DB에서 데이터 적재
    db: Session = SessionLocal()
    try:
        df = load_fills_df(db)
    finally:
        db.close()

    if df.empty:
        print("[LSTM-B] 학습할 데이터가 없습니다. cycles 테이블을 먼저 채워주세요.")
        return

    # 2) feature 엔지니어링 + 시퀀스 생성
    df_feat = load_fills_for_lstmB(df)
    X, y = make_sequences(df_feat, seq_len=SEQ_LEN)

    if X.shape[0] == 0:
        print("[LSTM-B] 시퀀스가 생성되지 않았습니다. 데이터 개수를 확인하세요.")
        return

    print(f"[LSTM-B] 학습용 샘플 수: {X.shape[0]}, 입력 차원: {X.shape[2]}")

    X_tensor = torch.tensor(X, dtype=torch.float32)
    y_tensor = torch.tensor(y, dtype=torch.float32)

    dataset = TensorDataset(X_tensor, y_tensor)
    loader = DataLoader(dataset, batch_size=32, shuffle=True)

    # 3) 모델 생성 및 학습
    input_dim = X.shape[2]
    model = LSTMB(input_dim=input_dim, hidden_dim=64, num_layers=2)
    train_lstm_b(model, loader, num_epochs=20, lr=1e-3)

    # 4) 모델 저장
    save_lstm_b(model, MODEL_PATH)


if __name__ == "__main__":
    main()
