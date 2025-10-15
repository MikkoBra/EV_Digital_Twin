# dtc_prediction.py
from __future__ import annotations

from .preprocess import transform_df
from dtc_prediction import DTC_Config


THRESHOLD = DTC_Config.load_threshold()

def predict(data, model, scaler, seq_len=48):
    features = ['SOC', 'SOH', 'Charging_Voltage', 'Battery_Temp', 'Motor_RPM', 'Motor_Torque', 'Motor_Temp', 'Brake_Pad_Wear', 'Tire_Pressure']
    
    data = transform_df(data, scaler)
    X = data[features].tail(seq_len).to_numpy(dtype="float32")[None, ...]
    prob = float(model.predict(X, verbose=0).ravel()[0])
    label = int(prob >= THRESHOLD)

    return prob, label
