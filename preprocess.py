from __future__ import annotations
import os, json, joblib
from typing import Dict, List, Tuple, Any, Optional
from matplotlib import pyplot as plt
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
    precision_recall_curve,
    roc_curve,
    auc,
)
import tensorflow as tf
from tensorflow.keras import layers, models, callbacks
from os import path
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, RobustScaler
print("TF version:", tf.__version__)
print("Num GPUs Available:", len(tf.config.list_physical_devices('GPU')))


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

def parse_timestamp(series: pd.Series,
                    fmt: str | None = None,
                    dayfirst: bool | None = None,
                    allow_mixed: bool = True) -> pd.Series:
    s = series.astype(str).str.strip()

    # Case A: explicit format provided
    if fmt:
        try:
            ts = pd.to_datetime(s, format=fmt, errors="raise", dayfirst=bool(dayfirst))
            return ts
        except Exception as e:
            # fall through to robust paths
            pass

    # Case B: ISO8601-fast path
    try:
        ts = pd.to_datetime(s, format="ISO8601", errors="raise", dayfirst=False)
        return ts
    except Exception:
        pass

    # Case C: mixed inference per element
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

def infer_features(df: pd.DataFrame, cfg: Config) -> List[str]:
    if cfg.features:
        return cfg.features
    ignore = {"timestamp", cfg.target, "Charging_Voltage", "vehicle"}
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
    group_col: Optional[str] = "vehicle",
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

def transform(df: pd.DataFrame, features: list[str], bundle: dict) -> pd.DataFrame:
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
            raise RuntimeError("transform(): empty scalers bundle. Did you run fit_scaler on TRAIN?")
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
    Xs: List[np.ndarray] = []
    ys: List[int] = []
    for _, g in df.groupby("vehicle", sort=False):
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

def build_model(input_len: int, n_features: int, cfg: Config) -> tf.keras.Model:
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
        metrics=[tf.keras.metrics.AUC(name="roc_auc"),
                 tf.keras.metrics.AUC(curve="PR", name="pr_auc")],
    )
    return model

def make_tf_dataset(
    X: np.ndarray,
    y: np.ndarray,
    batch_size: int,
    *,
    shuffle: bool = False,
    seed: int | None = 42,
    cache: bool = True,
    drop_remainder: bool | None = None,
    prefetch: bool = True,
    sample_weight: np.ndarray | None = None,
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
        # buffer size heuristic: cap to avoid huge memory while keeping good mixing
        buf = int(min(N, 10000))
        ds = ds.shuffle(buffer_size=buf, seed=seed, reshuffle_each_iteration=True)

    if drop_remainder is None:
        drop_remainder = bool(shuffle)  # True for train, False for eval

    ds = ds.batch(batch_size, drop_remainder=drop_remainder)

    if prefetch:
        ds = ds.prefetch(tf.data.AUTOTUNE)

    return ds

def compute_class_weights(y: np.ndarray) -> Dict[int, float]:
    pos = y.sum()
    neg = len(y) - pos
    if pos == 0 or neg == 0:
        return {0: 1.0, 1: 1.0}
    w_pos = neg / max(1.0, pos)
    w_neg = 1.0
    return {0: w_neg, 1: w_pos}

def _safe_get(h, k):
    return h[k] if k in h else None

def plot_training_curves(history):
    h = history.history  # dict of metric -> list
    # Derive F1 if possible
    def f1(p, r):
        return [ (2*pp*rr)/(pp+rr+1e-12) if (pp is not None and rr is not None and (pp+rr)>0) else math.nan
                 for pp, rr in zip(p or [], r or []) ]

    train_prec,  val_prec  = _safe_get(h, "precision"),   _safe_get(h, "val_precision")
    train_rec,   val_rec   = _safe_get(h, "recall"),      _safe_get(h, "val_recall")
    train_f1 = f1(train_prec, train_rec) if train_prec and train_rec else None
    val_f1   = f1(val_prec, val_rec)     if val_prec and val_rec     else None

    charts = [
        ("loss",        "val_loss",        "Loss"),
        ("pr_auc",      "val_pr_auc",      "PR AUC"),
        ("roc_auc",     "val_roc_auc",     "ROC AUC"),
        ("precision",   "val_precision",   "Precision"),
        ("recall",      "val_recall",      "Recall"),
    ]

    for train_k, val_k, title in charts:
        if train_k in h or val_k in h:
            plt.figure()
            if train_k in h: plt.plot(h[train_k], label=f"train_{train_k}")
            if val_k   in h: plt.plot(h[val_k],   label=f"val_{train_k}")
            plt.title(title); plt.xlabel("Epoch"); plt.legend(); plt.grid(True)
            plt.show()

    # F1 (derived)
    if train_f1 or val_f1:
        plt.figure()
        if train_f1: plt.plot(train_f1, label="train_f1")
        if val_f1:   plt.plot(val_f1,   label="val_f1")
        plt.title("F1 (derived from precision/recall)"); plt.xlabel("Epoch"); plt.legend(); plt.grid(True)
        plt.show()

def plot_test_curves(
    y_true,
    y_prob,
    threshold=0.5,
    title_suffix=" (test)",
    cfg=None,
    *,
    normalize_cm: bool = True,
    dpi: int = 120,
):
    """
    Plot ROC, PR, and Confusion Matrix for test predictions.
    Saves PNGs if cfg.model_dir is provided. Returns a dict of metrics and file paths.
    """
    # Governance
    y_true = np.asarray(y_true).astype(int).ravel()
    y_prob = np.asarray(y_prob).astype(float).ravel()
    if y_true.size == 0 or y_prob.size == 0:
        raise ValueError("plot_test_curves: empty inputs.")
    if y_true.shape[0] != y_prob.shape[0]:
        raise ValueError(f"Length mismatch: y_true={y_true.shape[0]}, y_prob={y_prob.shape[0]}")

    out_dir = getattr(cfg, "model_dir", None) if cfg is not None else None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    assets = {}
    metrics = {}

    # ROC
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    roc_auc_val = auc(fpr, tpr)
    metrics["roc_auc_curve"] = float(roc_auc_val)

    plt.figure(dpi=dpi)
    plt.plot(fpr, tpr, label=f"ROC AUC = {roc_auc_val:.3f}")
    plt.plot([0, 1], [0, 1], "--", linewidth=1, label="Random")
    plt.xlim(0, 1); plt.ylim(0, 1)
    plt.title("ROC" + title_suffix)
    plt.xlabel("False Positive Rate"); plt.ylabel("True Positive Rate")
    plt.legend(); plt.grid(True)
    if out_dir:
        roc_path = os.path.join(out_dir, "roc_curve.png")
        plt.savefig(roc_path, bbox_inches="tight")
        assets["roc_curve"] = roc_path
    plt.show(); plt.close()

    # PR
    prec, rec, thr = precision_recall_curve(y_true, y_prob)
    pr_auc_curve = auc(rec, prec)  # geometric AUC of the curve
    ap_score = average_precision_score(y_true, y_prob)  # standard headline
    metrics["pr_auc_curve"] = float(pr_auc_curve)
    metrics["average_precision"] = float(ap_score)

    prevalence = (y_true == 1).mean()
    plt.figure(dpi=dpi)
    plt.plot(rec, prec, label=f"PR AUC = {pr_auc_curve:.3f} | AP = {ap_score:.3f}")
    plt.hlines(prevalence, 0, 1, linestyles="--", linewidth=1, label=f"Baseline (pos={prevalence:.3f})")
    plt.xlim(0, 1); plt.ylim(0, 1)
    plt.title("Precision–Recall" + title_suffix)
    plt.xlabel("Recall"); plt.ylabel("Precision")
    plt.legend(); plt.grid(True)
    if out_dir:
        pr_path = os.path.join(out_dir, "pr_curve.png")
        plt.savefig(pr_path, bbox_inches="tight")
        assets["pr_curve"] = pr_path
    plt.show(); plt.close()

    # Confusion Matrix at threshold
    y_hat = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_hat, labels=[0, 1])
    if normalize_cm:
        with np.errstate(invalid="ignore", divide="ignore"):
            cm_norm = cm.astype(float) / cm.sum(axis=1, keepdims=True)
        cm_disp = cm_norm
        fmt = ".2f"
        title = f"Confusion Matrix (normalized, thr={threshold:.3f})"
    else:
        cm_disp = cm
        fmt = "d"
        title = f"Confusion Matrix (thr={threshold:.3f})"

    metrics["threshold"] = float(threshold)
    metrics["cm"] = cm.tolist()

    plt.figure(dpi=dpi)
    plt.imshow(cm_disp, interpolation="nearest")
    plt.title(title); plt.xlabel("Predicted"); plt.ylabel("True")
    tick_labels = ["0", "1"]
    plt.xticks([0, 1], tick_labels); plt.yticks([0, 1], tick_labels)
    for i in range(2):
        for j in range(2):
            plt.text(j, i, format(cm_disp[i, j], fmt), ha="center", va="center")
    plt.colorbar(); plt.tight_layout()
    if out_dir:
        cm_path = os.path.join(out_dir, "confusion_matrix.png")
        plt.savefig(cm_path, bbox_inches="tight")
        assets["confusion_matrix"] = cm_path
    plt.show(); plt.close()

    return {"metrics": metrics, "assets": assets}

def export_pipeline(
    cfg,
    model: tf.keras.Model,
    scaler_bundle: Dict[str, Any],
    *,
    threshold: float = 0.5
) -> Dict[str, str]:
    os.makedirs(cfg.model_dir, exist_ok=True)

    # 1) Save the full model (architecture + weights)
    model_path = os.path.join(cfg.model_dir, f"{cfg.model_name}.keras")
    model.save(model_path)  # tf 2.12+ native format

    # 2) Save the preprocessing bundle used by transform()
    bundle_path = os.path.join(cfg.model_dir, cfg.scaler_name)  # e.g. "bundle.joblib"
    joblib.dump(scaler_bundle, bundle_path)

    # 3) Persist cfg for traceability (optional, but useful)
    cfg_path = os.path.join(cfg.model_dir, cfg.config_name)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg.__dict__, f, indent=2)

    # 4) Single source of truth for the consumer
    manifest = {
        "model_path": model_path,
        "bundle_path": bundle_path,
        "config_path": cfg_path,
        "threshold": float(threshold),
        "seq_len": int(scaler_bundle["seq_len"]) if "seq_len" in scaler_bundle else int(cfg.seq_len),
        "horizon": int(scaler_bundle["horizon"]) if "horizon" in scaler_bundle else int(cfg.horizon),
        "features": scaler_bundle.get("features", []),
        "group_col": scaler_bundle.get("group_col", "vehicle"),
        "masked_flags": scaler_bundle.get("masked_flags", {}),
        "policy": scaler_bundle.get("policy", {}),
        "versions": {
            "tf": tf.__version__,
            "model_version": getattr(cfg, "version", "v1"),
        },
    }
    manifest_path = os.path.join(cfg.model_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return {"model_path": model_path, "bundle_path": bundle_path, "manifest_path": manifest_path}