# app/ml/train_pipeline.py

from app.ml.generate_initial_cycles import generate_initial_cycles
from app.ml.train_lstm_a import train_lstm_a

def run_pipeline(sku="CIDER_500"):
    print("========== LSTM-A TRAINING PIPELINE ==========\n")

    print("[1/2] Generating initial cycles...")
    generate_initial_cycles(sku=sku)

    print("\n[2/2] Training LSTM-A model...")
    train_lstm_a(sku=sku)

    print("\n========== PIPELINE COMPLETE ==========")
    print("Model saved in models/")
    print("=======================================\n")


if __name__ == "__main__":
    run_pipeline()