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

class DtcPredictor:
    def __init__(self, model_dir: str, threshold: float = 0.5, max_buffer: int = 512):
        self.model_dir = Path(model_dir).resolve()
        self.threshold = float(threshold)
        self.max_buffer = int(max_buffer)

        man_path = self.model_dir / "manifest.json"
        if not man_path.exists():
            raise FileNotFoundError(f"manifest.json not found in {self.model_dir}")

        with man_path.open("r", encoding="utf-8") as f:
            man = json.load(f)

        # resolve relative or absolute paths from manifest
        def _resolve(p: str) -> Path:
            pth = Path(p)
            return pth if pth.is_absolute() else (self.model_dir / pth)

        model_path  = _resolve(man["model_path"])
        bundle_path = _resolve(man["bundle_path"])

        if not model_path.exists():
            raise FileNotFoundError(f"Model file missing: {model_path}")
        if not bundle_path.exists():
            raise FileNotFoundError(f"Bundle file missing: {bundle_path}")

        self.model  = tf.keras.models.load_model(str(model_path))
        self.bundle: Dict[str, Any] = joblib.load(str(bundle_path))

        self.features     = list(self.bundle["features"])
        self.seq_len      = int(self.bundle["seq_len"])
        self.horizon      = int(self.bundle["horizon"])
        self.group_col    = self.bundle.get("group_col", "vehicle")
        self.masked_flags = self.bundle.get("masked_flags", {}) or {}

        self.buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max(self.max_buffer, self.seq_len)))

    def ingest(self, row: pd.Series | dict):
        if isinstance(row, dict):
            row = pd.Series(row)
        vid = row.get(self.group_col) or "__default__"
        self.buffers[vid].append(row.to_dict())

    def _coerce_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for c in self.features:
            if c not in df.columns:
                df[c] = np.nan
            df[c] = pd.to_numeric(df[c], errors="coerce")
        for flag in {fl for fl in self.masked_flags.values() if fl}:
            if flag not in df.columns:
                df[flag] = 0
            df[flag] = pd.to_numeric(df[flag], errors="coerce").fillna(0).astype(int)
        return df

    def _make_latest_window(self, df_raw: pd.DataFrame) -> np.ndarray:
        if "timestamp" in df_raw.columns:
            df_raw = df_raw.sort_values("timestamp")
        df_raw = self._coerce_schema(df_raw)
        df_t = transform(df_raw, self.features, self.bundle)
        if len(df_t) < self.seq_len:
            raise ValueError(f"Need at least {self.seq_len} rows, got {len(df_t)}")
        return df_t[self.features].tail(self.seq_len).to_numpy(dtype="float32")[None, ...]

    def predict_for(self, vehicle_id: str) -> Dict[str, Any]:
        buf = self.buffers.get(vehicle_id)
        have = 0 if not buf else len(buf)
        if not buf or have < self.seq_len:
            return {"ready": False, "vehicle": vehicle_id, "reason": f"need {self.seq_len}, have {have}"}
        X = self._make_latest_window(pd.DataFrame(list(buf)))
        prob = float(self.model.predict(X, verbose=0).ravel()[0])
        return {
            "ready": True,
            "vehicle": vehicle_id,
            "prob_dtc_next_h": prob,
            "pred_label": int(prob >= self.threshold),
            "threshold": self.threshold,
            "seq_len": self.seq_len,
            "horizon": self.horizon,
        }

    def predict_latest(self) -> Dict[str, Dict[str, Any]]:
        return {vid: self.predict_for(vid) for vid in list(self.buffers.keys())}
