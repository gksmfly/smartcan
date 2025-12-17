# app/ml/lstm_a.py

import joblib
import torch
import numpy as np
from pathlib import Path
from app.ml.ml_a_model import LSTMA

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


class LstmAController:
    def __init__(self):
        self.device = torch.device("cpu")
        self.model = None
        self.scaler = None
        self.loaded_sku = None     # 어떤 SKU 모델이 로드되었는지 기억

    # ---------------------------------------------------
    # 모델 자동 로드
    # ---------------------------------------------------
    def ensure_loaded(self, sku):
        """sku별 LSTM-A 모델과 스케일러 자동 로드"""
        if self.loaded_sku == sku and self.model is not None:
            return  # 이미 로드됨

        model_path = MODEL_DIR / f"lstm_a_{sku}.pt"
        scaler_path = MODEL_DIR / f"lstm_a_{sku}_scaler.pkl"

        self.model = LSTMA()
        self.model.load_state_dict(torch.load(model_path, map_location="cpu"))
        self.model.eval()

        self.scaler = joblib.load(scaler_path)

        self.loaded_sku = sku
        print(f"[LSTM-A] loaded model for {sku}")

    # ---------------------------------------------------
    # LSTM-A 기반 예측 핵심 함수
    # ---------------------------------------------------
    def predict_next(self, recipe, recent_cycles):
        """
        recent_cycles: 최근 충전 cycle list
        recipe: 레시피 객체
        """

        sku = recipe.sku_id

        # ⭐ COKE는 고정 충전이므로 LSTM 적용 안 함
        if sku == "COKE_355":
            return recipe.base_valve_ms

        # ⭐ CIDER만 LSTM 적용
        if sku != "CIDER_500":
            return recipe.base_valve_ms

        # ⭐ 최근 cycle이 부족하면 기본값 사용
        if len(recent_cycles) < 5:
            print("[LSTM-A] insufficient history, using base")
            return recipe.base_valve_ms

        # ⭐ 모델 자동 로딩
        self.ensure_loaded(sku)

        # ---------------------------------------------------
        # 입력 윈도우 생성 (최근 5개)
        # ---------------------------------------------------
        window = recent_cycles[-5:]
        seq = []

        for c in window:
            actual = float(c.actual_ml or recipe.target_amount)
            seq.append([
                actual,           # 실제 충전량
                c.valve_ms,       # 밸브 ms
                c.target_ml       # 목표 ml
            ])

        x = np.array(seq, dtype=np.float32).reshape(1, 5, 3)

        # 스케일 변환
        x_scaled = self.scaler.transform(
            x.reshape(1, -1)
        ).reshape(1, 5, 3)

        x_tensor = torch.tensor(x_scaled, dtype=torch.float32)

        # ---------------------------------------------------
        # LSTM 예측
        # ---------------------------------------------------
        pred = self.model(x_tensor).item()

        # ---------------------------------------------------
        # 오차 기반 강화 보정 (너의 로직 유지)
        # ---------------------------------------------------
        last = recent_cycles[-1]
        err = last.actual_ml - last.target_ml  # 양수면 과충전

        pred_adj = pred - err * 0.9  # 보정 적용
        pred_adj = max(80, min(pred_adj, 2000))  # 범위 제한

        print(f"[LSTM-A] raw={pred:.1f}, adj={pred_adj:.1f}")

        return pred_adj

    # ---------------------------------------------------
    # ⭐ 백엔드에서 요구하는 이름 (호환성 유지)
    # ---------------------------------------------------
    def predict_next_amount(self, recipe, recent_cycles):
        """백엔드 MQTT 핸들러가 요구하는 함수명"""
        return self.predict_next(recipe, recent_cycles)


# ---------------------------------------------------
# 싱글톤 제공
# ---------------------------------------------------
_lstmA = LstmAController()

def get_lstm_a_model():
    return _lstmA
# -------------------------------------------------------------
# Backward-compatible helper (DB signature)
# -------------------------------------------------------------
def compute_next_valve_time(db, sku_id: str, target_amount: float | None = None) -> float:
    """
    기존 코드(REST/control.py, mqtt/client.py)가 호출하던 DB 기반 시그니처 호환용 함수.
    - DB에서 recipe / recent cycles를 로드한 뒤
    - services.r2r.compute_next_valve_time(recipe, recent_cycles, ...)로 계산한다.
    """
    # 지연 import로 순환참조 방지
    from app.services import cycles_service, recipes_service
    from app.services.r2r import compute_next_valve_time as _r2r_compute

    # recipe 로드(서비스 시그니처 차이 방어)
    recipe = None
    try:
        recipe = recipes_service.get_recipe_by_sku_id(db, sku_id)
    except TypeError:
        recipe = recipes_service.get_recipe_by_sku_id(db, sku_id=sku_id)

    if recipe is None:
        raise ValueError(f"Recipe not found for sku_id={sku_id}")

    # recent cycles 로드(서비스 시그니처 차이 방어)
    try:
        recent = cycles_service.get_recent_cycles_for_sku(db, sku=sku_id, limit=50)
    except TypeError:
        recent = cycles_service.get_recent_cycles_for_sku(db, sku_id, 50)

    # target_amount가 '예측값'이 아니라 '목표값'일 수 있어서, 없으면 None 처리
    predicted_next_amount = None
    if target_amount is not None:
        predicted_next_amount = float(target_amount)

    return float(_r2r_compute(recipe=recipe, recent_cycles=recent, predicted_next_amount=predicted_next_amount))
