# app/ml/train_lstm_a.py

import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
import joblib

from app.db.session import SessionLocal
from app.services.cycles_service import get_recent_cycles_for_sku
from app.ml.ml_a_dataset import build_lstm_a_dataset
from app.ml.ml_a_model import LSTMA
from pathlib import Path


def train_lstm_a(sku="CIDER_500"):
    db = SessionLocal()

    print("[TRAIN] Loading cycles...")
    cycles = get_recent_cycles_for_sku(db, sku, limit=300)

    if len(cycles) < 15:
        raise RuntimeError(f"[TRAIN] Not enough cycles ({len(cycles)})")

    print("[TRAIN] Building dataset...")
    X, y = build_lstm_a_dataset(cycles, window_size=5, K=1.2)
    N, T, F = X.shape
    print(f"[TRAIN] Dataset X={X.shape}, y={y.shape}")

    # -------------------------
    # X scaling
    # -------------------------
    from sklearn.preprocessing import StandardScaler
    x_scaler = StandardScaler()
    X_scaled = x_scaler.fit_transform(X.reshape(N, -1)).reshape(N, T, F)

    # -------------------------
    # y scaling
    # -------------------------
    y = y.reshape(-1, 1)
    y_scaler = StandardScaler()
    y_scaled = y_scaler.fit_transform(y).reshape(-1)

    # -------------------------
    # Tensor
    # -------------------------
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32)
    y_tensor = torch.tensor(y_scaled, dtype=torch.float32)

    ds = TensorDataset(X_tensor, y_tensor)
    dl = DataLoader(ds, batch_size=8, shuffle=True)

    device = torch.device("cpu")
    model = LSTMA(input_dim=F).to(device)

    opt = torch.optim.Adam(model.parameters(), lr=1e-2)
    loss_fn = nn.MSELoss()

    print("[TRAIN] Training start...")

    for epoch in range(120):
        total = 0
        loss_total = 0
        for xb, yb in dl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()

            loss_total += loss.item() * len(xb)
            total += len(xb)

        print(f"[TRAIN] Epoch {epoch+1:03d} | loss={loss_total/total:.4f}")

    # -------------------------
    # Save model & scalers
    # -------------------------
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)

    torch.save(model.state_dict(), model_dir / f"lstm_a_{sku}.pt")
    joblib.dump(x_scaler, model_dir / f"lstm_a_{sku}_x_scaler.pkl")
    joblib.dump(y_scaler, model_dir / f"lstm_a_{sku}_y_scaler.pkl")

    print("[TRAIN] Saved model & scalers")