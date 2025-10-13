# dtc_prediction.py
from __future__ import annotations

from .preprocess import transform_df
import sys
from pathlib import Path
import json

PARENT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(PARENT))

from root_dir import ROOT_DIR
from os import path
DEF_THRESH = 0.5
def _load_threshold() -> float:
    hpo_path= path.join(ROOT_DIR,"models/hpo_summary.json")
    with hpo_path.open("r", encoding="utf-8") as f:
        hpo = json.load(f)
    
    return hpo["chosen_threshold"]

def predict(data, model, scaler, seq_len=48):
    features = ['SOC', 'SOH', 'Charging_Cycles', 'Battery_Temp', 'Motor_RPM', 'Motor_Torque', 'Motor_Temp', 'Brake_Pad_Wear', 'Tire_Pressure']
    threshold = _load_threshold(DEF_THRESH)

    data = transform_df(data, scaler)
    X = data[features].tail(seq_len).to_numpy(dtype="float32")[None, ...]
    prob = float(model.predict(X, verbose=0).ravel()[0])
    label = int(prob >= threshold)

    return prob, label
