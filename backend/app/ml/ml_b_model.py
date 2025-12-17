import torch
import torch.nn as nn


class LSTMB(nn.Module):
    """멀티 SKU/멀티 라인 품질 예측용 LSTM-B 모델."""

    def __init__(self, input_dim: int = 3, hidden_dim: int = 64, num_layers: int = 2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
        )
        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        # x: (batch, seq_len, input_dim)
        out, _ = self.lstm(x)
        # 마지막 타임스텝만 사용
        last = out[:, -1, :]  # (batch, hidden_dim)
        y = self.fc(last)     # (batch, 1)
        return y.squeeze(-1)  # (batch,)


def predict_lstmB(model: nn.Module, series):
    """단일 시퀀스(series)에 대해 다음 error 값을 예측.

    series: shape (seq_len, input_dim)
    return: float (예측 error)
    """
    if model is None:
        raise RuntimeError("LSTM-B 모델이 로드되지 않았습니다.")

    x = torch.tensor(series, dtype=torch.float32).unsqueeze(0)  # (1, seq_len, input_dim)
    model.eval()
    with torch.no_grad():
        pred = model(x)
    return float(pred.item())
