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

def predicted(data, model, scaler):
    # preprocess the data for the isolation forrest model
    print(scaler)

    data = transform(data, scaler)

    # model inference
    pred = model.predict(data)[0]

    return pred
