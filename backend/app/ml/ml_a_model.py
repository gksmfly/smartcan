# app/ml/ml_a_model.py

import torch
import torch.nn as nn

class LSTMA(nn.Module):
    def __init__(self, input_dim=3, hidden_dim=32, num_layers=1):
        super().__init__()

        self.lstm = nn.LSTM(
            input_dim, hidden_dim,
            num_layers=num_layers,
            batch_first=True
        )

        self.fc = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        out = out[:, -1, :]
        return self.fc(out).squeeze(-1)