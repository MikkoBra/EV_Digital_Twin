# dtc_prediction.py
from __future__ import annotations
from .preprocess import transform_df
THRESHOLD=0.5

def predict(data, model, scaler, seq_len=48):
    features = ['SOC', 'SOH', 'Charging_Cycles', 'Battery_Temp', 'Motor_RPM', 'Motor_Torque', 'Motor_Temp', 'Brake_Pad_Wear', 'Tire_Pressure']
    
    data = transform_df(data, scaler)
    X = data[features].tail(seq_len).to_numpy(dtype="float32")[None, ...]
    prob = float(model.predict(X, verbose=0).ravel()[0])
    label = int(prob >= THRESHOLD)

    return prob, label
