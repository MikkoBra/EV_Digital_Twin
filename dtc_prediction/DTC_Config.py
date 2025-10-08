from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import os
from os import path


@dataclass
class Config:
    cwd = os.getcwd()
    data_dir = path.join(cwd, "data")
    files: Tuple[str, ...] = ("daily_user.csv", "moderate_user.csv", "rare_user.csv")
    # test_file:str= "heavy_user.csv"
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

    batch_size: int = 256
    epochs: int = 40
    lr: float = 1e-3
    hidden: int = 128
    dropout: float = 0.2
    bidirectional: bool = True

    seed: int = 47
    model_dir: str = "models"
    model_name: str = "lstm_dtc_v3.keras"  # New Keras 3 format
    scaler_name: str = "scaler_dtc.npy"
    config_name: str = "config_dtc.json"

ROBUST_COLS = {
    "rpm_pos_log", "torque_pos_log",
    "Charging_Cycles_diff", "Brake_Pad_Wear_diff",
}

PASSTHROUGH_COLS = {
    "is_moving", "has_torque", 
    "voltage_tier",
}

MASKED_COLS = {
    "rpm_pos_log": "is_moving",
    "torque_pos_log": "has_torque",
}

def get_model_path() -> str:
    # Use absolute path relative to this file's location
    base_dir = path.dirname(path.dirname(path.abspath(__file__)))
    return path.join(base_dir, Config.model_dir, Config.model_name)

def get_scaler_path() -> str:
    # Use absolute path relative to this file's location
    base_dir = path.dirname(path.dirname(path.abspath(__file__)))
    return path.join(base_dir, Config.model_dir, Config.scaler_name)  