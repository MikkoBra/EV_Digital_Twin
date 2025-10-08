# dtc_prediction.py
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import json
from typing import Any, Dict

import joblib
import numpy as np
import pandas as pd
import tensorflow as tf

from preprocess import transform 
THRESHOLD=0.5

def predict(data, model, scaler, seq_len=48):
    features = ['SOC', 'SOH', 'Charging_Cycles', 'Battery_Temp', 'Motor_RPM', 'Motor_Torque', 'Motor_Temp', 'Brake_Pad_Wear', 'Tire_Pressure']
    
    data = transform(data, scaler)
    X = data[features].tail(seq_len).to_numpy(dtype="float32")[None, ...]
    prob = float(model.predict(X, verbose=0).ravel()[0])
    label = int(prob >= THRESHOLD)

    return prob, label
