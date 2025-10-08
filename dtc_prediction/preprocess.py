import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Dict, List,Tuple, Any, Optional

import tensorflow as tf
from tensorflow.keras import layers, models
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, RobustScaler
from .DTC_Config import PASSTHROUGH_COLS, ROBUST_COLS, MASKED_COLS
from . import DTC_Config

def parse_timestamp(series: pd.Series,
                    fmt: str = None,
                    dayfirst: bool = None,
                    allow_mixed: bool = True) -> pd.Series:
    s = series.astype(str).str.strip()

    if fmt:
        try:
            ts = pd.to_datetime(s, format=fmt, errors="raise", dayfirst=bool(dayfirst))
            return ts
        except Exception as e:
            pass

    try:
        ts = pd.to_datetime(s, format="ISO8601", errors="raise", dayfirst=False)
        return ts
    except Exception:
        pass

    if allow_mixed:
        ts = pd.to_datetime(s, format="mixed", errors="coerce",
                            dayfirst=False if dayfirst is None else dayfirst)
        bad = ts.isna()
        if bad.any():
            sample = s[bad].head(5).tolist()
            raise ValueError(
                f"Failed to parse {bad.sum()} timestamps with mixed mode. "
                f"Examples: {sample}. Consider setting cfg.datetime_format_try explicitly."
            )
        return ts

    raise ValueError("Unable to parse timestamps. Provide cfg.datetime_format_try.")

def infer_features(df: pd.DataFrame, cfg: DTC_Config.Config) -> List[str]:
    if cfg.features:
        return cfg.features
    ignore = {"timestamp", cfg.target, "Charging_Voltage", "vehicle_id"}
    feats = [c for c in df.columns if c not in ignore]

    return feats

def _fit_group(bundle: Dict[str, Any], gdf: pd.DataFrame, g_key: Any) -> None:
    for f in bundle["features"]:
        policy    = bundle["policy"][f]
        mask_flag = bundle["masked_flags"][f]

        def _fallback_constant_zero(s_arr):
            imp = SimpleImputer(strategy="constant", fill_value=0)
            imp.fit(s_arr)           
            bundle["imputers"][g_key][f] = imp
            bundle["scalers"][g_key][f]  = None
            bundle["zero_var"][g_key].add(f)
            bundle["policy"][f]          = "passthrough"

        if policy == "passthrough":
            s = pd.to_numeric(gdf[f], errors="coerce").values.reshape(-1, 1)
            imp = SimpleImputer(strategy="constant", fill_value=0) 
            imp.fit(s)
            bundle["imputers"][g_key][f] = imp
            bundle["scalers"][g_key][f]  = None
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
                bundle["scalers"][g_key][f]  = None
                bundle["zero_var"][g_key].add(f)
                bundle["policy"][f]          = "passthrough"
                continue

            scaler = RobustScaler() if bundle["policy"][f] == "robust" else StandardScaler()
            scaler.fit(s_pos)
            bundle["imputers"][g_key][f] = imp
            bundle["scalers"][g_key][f]  = scaler
            continue

        s = pd.to_numeric(gdf[f], errors="coerce").values.reshape(-1, 1)

        if np.isnan(s).all():
            _fallback_constant_zero(s)
            continue

        imp = SimpleImputer(strategy="median")
        s_imp = imp.fit_transform(s)

        if np.nanstd(s_imp) == 0 or np.isclose(np.nanstd(s_imp), 0.0):
            bundle["imputers"][g_key][f] = imp
            bundle["scalers"][g_key][f]  = None
            bundle["zero_var"][g_key].add(f)
            bundle["policy"][f]          = "passthrough"
            continue

        scaler = RobustScaler() if policy == "robust" else StandardScaler()
        scaler.fit(s_imp)
        bundle["imputers"][g_key][f] = imp
        bundle["scalers"][g_key][f]  = scaler

def _apply_to_index(out, idx, features, bundle, g_key) -> None:
    for f in features:
        policy    = bundle["policy"][f]
        mask_flag = bundle["masked_flags"][f]
        sc        = bundle["scalers"][g_key][f]
        imp       = bundle["imputers"][g_key][f]

        col = pd.to_numeric(out.iloc[idx][f], errors="coerce").values.reshape(-1, 1)

        if policy == "passthrough":
            out.iloc[idx, out.columns.get_loc(f)] = imp.transform(col).ravel()
            continue

        if mask_flag is not None:
            flag = out.iloc[idx, out.columns.get_loc(mask_flag)].values.astype(int).ravel()
            pos  = flag == 1
            if np.any(pos):
                col_pos = imp.transform(col[pos])
                col[pos] = sc.transform(col_pos) if sc is not None else col_pos
            col[~pos] = 0.0
            out.iloc[idx, out.columns.get_loc(f)] = col.ravel()
            continue

        col_imp = imp.transform(col)
        val = sc.transform(col_imp) if sc is not None else col_imp
        out.iloc[idx, out.columns.get_loc(f)] = val.ravel()

def fit_scaler(
    df: pd.DataFrame,
    features: List[str],
    group_col: Optional[str] = "vehicle_id",
) -> Dict[str, Any]:

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

def transform(df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    out = df.copy()
    feat_list = bundle["features"]
    # display(out)

    missing = [f for f in feat_list if f not in out.columns]
    if missing:
        raise KeyError(f"transform(): missing features in df: {missing}")

    grp_col = bundle["group_col"]
    # print(grp_col)
    if grp_col in feat_list:
        raise ValueError(f"transform(): group column '{grp_col}' must not be in features.")

    out[feat_list] = out[feat_list].apply(pd.to_numeric, errors="coerce").astype("float64")
    # print(out[feat_list])

    needed_flags = [fl for fl in (bundle.get("masked_flags") or {}).values() if fl]
    missing_flags = [fl for fl in needed_flags if fl not in out.columns]
    # print(needed_flags)
    if missing_flags:
        raise KeyError(f"transform(): masked-flag columns missing: {missing_flags}")

    if grp_col:
        # print(out.columns)
        if grp_col not in out.columns:
            raise KeyError(f"transform(): expected group column '{grp_col}' not found.")
        scalers = bundle["scalers"]
        if not scalers:
            raise RuntimeError("transform(): empty scalers bundle. Did you run fit_scaler on TRAIN?")
        fallback_key = next(iter(scalers))
        groups = out.groupby(grp_col, sort=False, dropna=False).indices
        for g, pos_idx in groups.items():
            g_key = g if g in scalers else fallback_key
            _apply_to_index(out, pos_idx.tolist(), feat_list, bundle, g_key)
    else:
        # print("no group_col")
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
            # label at window_end + horizon
            ys.append(int(tgt[stop - 1 + horizon]))
    if not Xs:
        return np.empty((0, seq_len, len(features))), np.empty((0,), dtype=int)
    return np.stack(Xs), np.asarray(ys, dtype=int)

def build_model(input_len: int, n_features: int, cfg: DTC_Config.Config) -> tf.keras.Model:
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
    drop_remainder: bool  = None,
    prefetch: bool = True,
    sample_weight: np.ndarray  = None,
):
    if X.shape[0] != y.shape[0]:
        raise ValueError(f"X and y length mismatch: {X.shape[0]} vs {y.shape[0]}")
    N = X.shape[0]
    if N == 0:
        raise ValueError("make_tf_dataset received empty arrays.")

    X = tf.convert_to_tensor(X, dtype=tf.float32)
    y = tf.convert_to_tensor(y, dtype=tf.float32)

    if sample_weight is not None:
        w = tf.convert_to_tensor(sample_weight, dtype=tf.float32)
        ds = tf.data.Dataset.from_tensor_slices((X, y, w))
    else:
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

