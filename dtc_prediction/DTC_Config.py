from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import os
from os import path
import sys
from pathlib import Path

PARENT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(PARENT))

from root_dir import ROOT_DIR


PASSTHROUGH_COLS = {
    'Charging_Voltage', 'vehicle_id', 'anomaly_score', 'is_anomaly',
}

ROBUST_COLS = {
    "Battery_Temp", 
    "Motor_RPM", "Motor_Torque", "Motor_Temp",
}
@dataclass
class Config:
    cwd = os.getcwd()
    data_dir = f"{ROOT_DIR}/data"
    files: Tuple[str, ...] = (path.join(data_dir,"daily_user.csv"), path.join(data_dir,"moderate_user.csv"), path.join(data_dir,"rare_user.csv"))

    time_col: str | None = None
    target: str = "DTC_final"
    features: List[str] | None = None
    timestamp_format_try: str = "%d-%m-%y %H:%M"

    seq_len: int = 168
    horizon: int = 24
    stride: int = 1

    val_ratio_last: float = 0.1
    test_ratio_last: float = 0.2
    optimizer: str = 'Adam'
    loss: str = 'binary_crossentropy'

    batch_size: int = 256
    epochs: int = 40
    lr: float = 1e-3
    hidden: int = 128
    dropout: float = 0.2
    bidirectional: bool = True
    stateful: bool = False
    threshold: float = 0.5

    seed: int = 47
    model_dir: str = path.join(ROOT_DIR,"models")
    model_name: str = "lstm_dtc"
    scaler_name: str = "scaler_dtc.npy"
    config_name: str = "config_dtc.json"
    
    def set_threshold(self, thresh: float) -> None:
        self.threshold = thresh



def get_model_path() -> str:
    return path.join(Config.model_dir, Config.model_name)
def get_scaler_path() -> str:
    return path.join(Config.model_dir, Config.scaler_name)  