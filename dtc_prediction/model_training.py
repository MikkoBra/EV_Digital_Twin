"""
DTC Prediction Model Training Script
Trains an LSTM model to predict Diagnostic Trouble Codes (DTC) from EV sensor data.
"""
import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional

import tensorflow as tf
from tensorflow.keras import layers, models, callbacks
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, RobustScaler

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtc_prediction.DTC_Config import Config, PASSTHROUGH_COLS, ROBUST_COLS, MASKED_COLS

print("=" * 60)
print("DTC Prediction Model Training")
print("=" * 60)
print(f"TensorFlow version: {tf.__version__}")
print(f"GPUs available: {len(tf.config.list_physical_devices('GPU'))}")
print()


def parse_timestamp(series: pd.Series, fmt: str = None, dayfirst: bool = None, allow_mixed: bool = True) -> pd.Series:
    """Parse timestamp column with multiple format attempts."""
    s = series.astype(str).str.strip()

    if fmt:
        try:
            return pd.to_datetime(s, format=fmt, errors="raise", dayfirst=bool(dayfirst))
        except Exception:
            pass

    try:
        return pd.to_datetime(s, format="ISO8601", errors="raise", dayfirst=False)
    except Exception:
        pass

    if allow_mixed:
        ts = pd.to_datetime(s, format="mixed", errors="coerce", dayfirst=False if dayfirst is None else dayfirst)
        bad = ts.isna()
        if bad.any():
            sample = s[bad].head(5).tolist()
            raise ValueError(f"Failed to parse {bad.sum()} timestamps. Examples: {sample}")
        return ts

    raise ValueError("Unable to parse timestamps.")


def load_vehicle_csv(path: str, cfg: Config) -> pd.DataFrame:
    """Load a single vehicle CSV file."""
    df = pd.read_csv(path)
    current_target = "DTC"
    time_col = df.iloc[:, 0]
    ts = parse_timestamp(time_col, cfg.timestamp_format_try)

    df = df.drop(df.columns[0], axis=1).copy()
    df.insert(0, "timestamp", ts)
    
    if current_target not in df.columns:
        raise ValueError(f"Missing target column '{current_target}' in {path}")
    
    df[cfg.target] = df[current_target].apply(lambda x: 0 if str(x).strip() == "0" else 1).astype(int)
    df["vehicle_id"] = os.path.splitext(os.path.basename(path))[0].replace("_user", "")
    return df


def load_all(cfg: Config) -> pd.DataFrame:
    """Load all vehicle CSV files."""
    frames: List[pd.DataFrame] = []
    for f in cfg.files:
        p = os.path.join(cfg.data_dir, f)
        if not os.path.exists(p):
            print(f"  File not found, skipping: {f}")
            continue
        print(f"  Loading: {f}")
        frames.append(load_vehicle_csv(p, cfg))
    
    if not frames:
        raise FileNotFoundError("No dataset files found.")

    df = pd.concat(frames, ignore_index=True)
    df = df.dropna(subset=["timestamp"]).sort_values(["vehicle_id", "timestamp"]).reset_index(drop=True)
    df = df.drop(columns=["DTC"], errors="ignore")
    return df


def split_train_val_test_per_vehicle(
    df: pd.DataFrame, test_ratio_last: float, val_ratio_last: float
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split data per vehicle into train/val/test using time-based splits."""
    trains, vals, tests = [], [], []
    for _, g in df.groupby("vehicle_id", sort=False):
        g = g.sort_values("timestamp")
        n = len(g)
        n_test = max(1, int(n * test_ratio_last))
        test = g.iloc[-n_test:]
        remain = g.iloc[: n - n_test]
        n_val = max(1, int(len(remain) * val_ratio_last))
        val = remain.iloc[-n_val:]
        train = remain.iloc[: len(remain) - n_val]
        if len(train) < 2:
            continue
        trains.append(train)
        vals.append(val)
        tests.append(test)
    return pd.concat(trains), pd.concat(vals), pd.concat(tests)


def infer_features(df: pd.DataFrame, cfg: Config) -> List[str]:
    """Infer feature columns from dataframe."""
    if cfg.features:
        return cfg.features
    ignore = {"timestamp", cfg.target, "Charging_Voltage", "vehicle_id"}
    return [c for c in df.columns if c not in ignore]


def _fit_group(bundle: Dict[str, Any], gdf: pd.DataFrame, g_key: Any) -> None:
    """Fit scalers and imputers for a single group (vehicle)."""
    for f in bundle["features"]:
        policy = bundle["policy"][f]
        mask_flag = bundle["masked_flags"][f]

        def _fallback_constant_zero(s_arr):
            imp = SimpleImputer(strategy="constant", fill_value=0)
            imp.fit(s_arr)
            bundle["imputers"][g_key][f] = imp
            bundle["scalers"][g_key][f] = None
            bundle["zero_var"][g_key].add(f)
            bundle["policy"][f] = "passthrough"

        if policy == "passthrough":
            s = pd.to_numeric(gdf[f], errors="coerce").values.reshape(-1, 1)
            imp = SimpleImputer(strategy="constant", fill_value=0)
            imp.fit(s)
            bundle["imputers"][g_key][f] = imp
            bundle["scalers"][g_key][f] = None
            continue

        if mask_flag is not None:
            if mask_flag not in gdf.columns:
                raise KeyError(f"Masked feature '{f}' expects flag column '{mask_flag}'.")
            s_full = pd.to_numeric(gdf[f], errors="coerce").values.reshape(-1, 1)

            if np.isnan(s_full).all():
                _fallback_constant_zero(s_full)
                continue

            flag = gdf[mask_flag].values.astype(int).ravel()
            pos_idx = flag == 1

            if not np.any(pos_idx):
                _fallback_constant_zero(s_full)
                continue

            imp = SimpleImputer(strategy="median")
            s_pos = imp.fit_transform(s_full[pos_idx])

            if np.nanstd(s_pos) == 0 or np.isclose(np.nanstd(s_pos), 0.0):
                bundle["imputers"][g_key][f] = imp
                bundle["scalers"][g_key][f] = None
                bundle["zero_var"][g_key].add(f)
                bundle["policy"][f] = "passthrough"
                continue

            scaler = RobustScaler() if bundle["policy"][f] == "robust" else StandardScaler()
            scaler.fit(s_pos)
            bundle["imputers"][g_key][f] = imp
            bundle["scalers"][g_key][f] = scaler
            continue

        s = pd.to_numeric(gdf[f], errors="coerce").values.reshape(-1, 1)

        if np.isnan(s).all():
            _fallback_constant_zero(s)
            continue

        imp = SimpleImputer(strategy="median")
        s_imp = imp.fit_transform(s)

        if np.nanstd(s_imp) == 0 or np.isclose(np.nanstd(s_imp), 0.0):
            bundle["imputers"][g_key][f] = imp
            bundle["scalers"][g_key][f] = None
            bundle["zero_var"][g_key].add(f)
            bundle["policy"][f] = "passthrough"
            continue

        scaler = RobustScaler() if policy == "robust" else StandardScaler()
        scaler.fit(s_imp)
        bundle["imputers"][g_key][f] = imp
        bundle["scalers"][g_key][f] = scaler


def fit_scaler(df: pd.DataFrame, features: List[str], group_col: Optional[str] = "vehicle_id") -> Dict[str, Any]:
    """Fit scalers and imputers per vehicle group."""
    if group_col is not None and group_col not in df.columns:
        raise KeyError(f"Group column '{group_col}' not found in df.")

    feat_list = list(features)
    bundle: Dict[str, Any] = {
        "group_col": group_col,
        "features": feat_list,
        "policy": {
            f: ("passthrough" if f in PASSTHROUGH_COLS else
                "robust" if f in ROBUST_COLS else "standard")
            for f in feat_list
        },
        "masked_flags": {f: MASKED_COLS.get(f) for f in feat_list},
        "imputers": defaultdict(dict),
        "scalers": defaultdict(dict),
        "zero_var": defaultdict(set),
    }

    if group_col:
        for g, gdf in df.groupby(group_col, sort=False):
            _fit_group(bundle, gdf, g)
    else:
        _fit_group(bundle, df, g=None)

    return bundle


def _apply_to_index(out, idx, features, bundle, g_key) -> None:
    """Apply scaling and imputation to a subset of rows."""
    for f in features:
        policy = bundle["policy"][f]
        mask_flag = bundle["masked_flags"][f]
        sc = bundle["scalers"][g_key][f]
        imp = bundle["imputers"][g_key][f]

        col = pd.to_numeric(out.iloc[idx][f], errors="coerce").values.reshape(-1, 1)

        if policy == "passthrough":
            out.iloc[idx, out.columns.get_loc(f)] = imp.transform(col).ravel()
            continue

        if mask_flag is not None:
            flag = out.iloc[idx, out.columns.get_loc(mask_flag)].values.astype(int).ravel()
            pos = flag == 1
            if np.any(pos):
                col_pos = imp.transform(col[pos])
                col[pos] = sc.transform(col_pos) if sc is not None else col_pos
            col[~pos] = 0.0
            out.iloc[idx, out.columns.get_loc(f)] = col.ravel()
            continue

        col_imp = imp.transform(col)
        val = sc.transform(col_imp) if sc is not None else col_imp
        out.iloc[idx, out.columns.get_loc(f)] = val.ravel()


def transform(df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """Transform dataframe using fitted scalers and imputers."""
    out = df.copy()
    feat_list = bundle["features"]

    missing = [f for f in feat_list if f not in out.columns]
    if missing:
        raise KeyError(f"transform(): missing features in df: {missing}")

    grp_col = bundle["group_col"]
    if grp_col in feat_list:
        raise ValueError(f"transform(): group column '{grp_col}' must not be in features.")

    out[feat_list] = out[feat_list].apply(pd.to_numeric, errors="coerce").astype("float64")

    needed_flags = [fl for fl in (bundle.get("masked_flags") or {}).values() if fl]
    missing_flags = [fl for fl in needed_flags if fl not in out.columns]
    if missing_flags:
        raise KeyError(f"transform(): masked-flag columns missing: {missing_flags}")

    if grp_col:
        if grp_col not in out.columns:
            raise KeyError(f"transform(): expected group column '{grp_col}' not found.")
        scalers = bundle["scalers"]
        if not scalers:
            raise RuntimeError("transform(): empty scalers bundle.")
        fallback_key = next(iter(scalers))
        groups = out.groupby(grp_col, sort=False, dropna=False).indices
        for g, pos_idx in groups.items():
            g_key = g if g in scalers else fallback_key
            _apply_to_index(out, pos_idx.tolist(), feat_list, bundle, g_key)
    else:
        _apply_to_index(out, out.index.tolist(), feat_list, bundle, g_key=None)

    out[feat_list] = out[feat_list].astype("float32")
    return out


def make_windows(
    df: pd.DataFrame,
    features: List[str],
    target: str,
    seq_len: int,
    horizon: int,
    stride: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Create sliding windows for LSTM input."""
    Xs: List[np.ndarray] = []
    ys: List[int] = []
    for _, g in df.groupby("vehicle_id", sort=False):
        g = g.sort_values("timestamp").reset_index(drop=True)
        feat = g[features].values
        tgt = g[target].values
        end = len(g) - horizon
        if end - seq_len + 1 <= 0:
            continue
        for start in range(0, end - seq_len + 1, stride):
            stop = start + seq_len
            Xs.append(feat[start:stop])
            ys.append(int(tgt[stop - 1 + horizon]))
    if not Xs:
        return np.empty((0, seq_len, len(features))), np.empty((0,), dtype=int)
    return np.stack(Xs), np.asarray(ys, dtype=int)


def build_model(input_len: int, n_features: int, cfg: Config) -> tf.keras.Model:
    """Build LSTM model for DTC prediction."""
    inputs = layers.Input(shape=(input_len, n_features))
    x = inputs
    if cfg.bidirectional:
        x = layers.Bidirectional(
            layers.LSTM(cfg.hidden, dropout=cfg.dropout, return_sequences=False)
        )(x)
    else:
        x = layers.LSTM(cfg.hidden, dropout=cfg.dropout, return_sequences=False)(x)
    x = layers.Dense(64, activation="relu")(x)
    x = layers.Dropout(cfg.dropout)(x)
    outputs = layers.Dense(1, activation="sigmoid")(x)
    model = models.Model(inputs, outputs)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=cfg.lr),
        loss="binary_crossentropy",
        metrics=[
            tf.keras.metrics.AUC(name="roc_auc"),
            tf.keras.metrics.AUC(curve="PR", name="pr_auc"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.Precision(name="precision"),
        ],
    )
    return model


def make_tf_dataset(
    X: np.ndarray,
    y: np.ndarray,
    batch_size: int,
    *,
    shuffle: bool = False,
    seed: int = 42,
    cache: bool = True,
    drop_remainder: bool = None,
    prefetch: bool = True,
):
    """Create TensorFlow dataset."""
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"X and y length mismatch: {X.shape[0]} vs {y.shape[0]}")
    N = X.shape[0]
    if N == 0:
        raise ValueError("make_tf_dataset received empty arrays.")

    X = tf.convert_to_tensor(X, dtype=tf.float32)
    y = tf.convert_to_tensor(y, dtype=tf.float32)

    ds = tf.data.Dataset.from_tensor_slices((X, y))

    if cache:
        ds = ds.cache()

    if shuffle:
        buf = int(min(N, 10000))
        ds = ds.shuffle(buffer_size=buf, seed=seed, reshuffle_each_iteration=True)

    if drop_remainder is None:
        drop_remainder = bool(shuffle)

    ds = ds.batch(batch_size, drop_remainder=drop_remainder)

    if prefetch:
        ds = ds.prefetch(tf.data.AUTOTUNE)

    return ds


def compute_class_weights(y: np.ndarray) -> Dict[int, float]:
    """Compute class weights for imbalanced dataset."""
    pos = y.sum()
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        return {0: 1.0, 1: 1.0}
    w_pos = neg / max(1.0, pos)
    w_neg = 1.0
    return {0: w_neg, 1: w_pos}


def main():
    """Main training function."""
    cfg = Config()
    
    # Set random seeds
    np.random.seed(cfg.seed)
    tf.random.set_seed(cfg.seed)
    
    print("Step 1: Loading data...")
    df = load_all(cfg)
    print(f"  Total records: {len(df)}")
    print(f"  Vehicles: {df['vehicle_id'].nunique()}")
    print()
    
    print("Step 2: Splitting data...")
    train_df, val_df, test_df = split_train_val_test_per_vehicle(df, cfg.test_ratio_last, cfg.val_ratio_last)
    print(f"  Train: {len(train_df)} records")
    print(f"  Val:   {len(val_df)} records")
    print(f"  Test:  {len(test_df)} records")
    print()
    
    print("Step 3: Inferring features...")
    features = infer_features(train_df, cfg)
    print(f"  Features: {len(features)}")
    print(f"  {features}")
    print()
    
    print("Step 4: Fitting scalers on training data...")
    scaler_bundle = fit_scaler(train_df, features, group_col="vehicle_id")
    print("  Scalers fitted.")
    print()
    
    print("Step 5: Transforming data...")
    train_t = transform(train_df, scaler_bundle)
    val_t = transform(val_df, scaler_bundle)
    print("  Data transformed.")
    print()
    
    print("Step 6: Creating windows...")
    X_train, y_train = make_windows(train_t, features, cfg.target, cfg.seq_len, cfg.horizon, cfg.stride)
    X_val, y_val = make_windows(val_t, features, cfg.target, cfg.seq_len, cfg.horizon, cfg.stride)
    print(f"  Train windows: {X_train.shape}")
    print(f"  Val windows:   {X_val.shape}")
    print(f"  Positive rate (train): {y_train.mean():.3f}")
    print(f"  Positive rate (val):   {y_val.mean():.3f}")
    print()
    
    print("Step 7: Computing class weights...")
    class_weights = compute_class_weights(y_train)
    print(f"  Class weights: {class_weights}")
    print()
    
    print("Step 8: Creating TensorFlow datasets...")
    train_ds = make_tf_dataset(X_train, y_train, cfg.batch_size, shuffle=True, seed=cfg.seed)
    val_ds = make_tf_dataset(X_val, y_val, cfg.batch_size, shuffle=False)
    print("  Datasets created.")
    print()
    
    print("Step 9: Building model...")
    model = build_model(cfg.seq_len, len(features), cfg)
    print(model.summary())
    print()
    
    print("Step 10: Training model...")
    os.makedirs(cfg.model_dir, exist_ok=True)
    
    best_path = os.path.join(cfg.model_dir, cfg.model_name)
    
    cbs = [
        callbacks.EarlyStopping(
            monitor="val_pr_auc",
            mode="max",
            patience=6,
            restore_best_weights=True,
            verbose=1
        ),
        callbacks.ReduceLROnPlateau(
            monitor="val_pr_auc",
            mode="max",
            factor=0.5,
            patience=3,
            min_lr=1e-5,
            verbose=1
        ),
        callbacks.ModelCheckpoint(
            filepath=best_path,
            monitor="val_pr_auc",
            mode="max",
            save_best_only=True,
            save_weights_only=False,
            verbose=1
        ),
    ]
    
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=cfg.epochs,
        class_weight=class_weights,
        callbacks=cbs,
        verbose=1
    )
    print("  Training complete.")
    print()
    
    print("Step 11: Saving artifacts...")
    # Model already saved by ModelCheckpoint
    print(f"  Model saved: {best_path}")
    
    scaler_path = os.path.join(cfg.model_dir, cfg.scaler_name)
    joblib.dump(scaler_bundle, scaler_path)
    print(f"  Scaler saved: {scaler_path}")
    
    config_path = os.path.join(cfg.model_dir, cfg.config_name)
    config_dict = {
        "seq_len": cfg.seq_len,
        "horizon": cfg.horizon,
        "features": features,
        "model_path": model_path,
        "scaler_path": scaler_path,
    }
    with open(config_path, "w") as f:
        json.dump(config_dict, f, indent=2)
    print(f"  Config saved: {config_path}")
    print()
    
    print("=" * 60)
    print("Training complete!")
    print("=" * 60)
    print(f"Final val_loss: {history.history['val_loss'][-1]:.4f}")
    if 'val_roc_auc' in history.history:
        print(f"Final val_roc_auc: {history.history['val_roc_auc'][-1]:.4f}")
    print()


if __name__ == "__main__":
    main()
