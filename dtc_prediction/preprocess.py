import numpy as np
import pandas as pd
from collections import defaultdict
from typing import Dict, List,Tuple, Any, Optional

import tensorflow as tf
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, RobustScaler
from . import DTC_Config as DTC_Config
from .DTC_Config import PASSTHROUGH_COLS, ROBUST_COLS


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
    # fit imputers and scalers for a single group and store in bundle
    for f in bundle["features"]:
        policy    = bundle["policy"][f]

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
            bundle["policy"][f] = "passthrough"
            continue

        scaler = RobustScaler() if policy == "robust" else StandardScaler()
        scaler.fit(s_imp)
        bundle["imputers"][g_key][f] = imp
        bundle["scalers"][g_key][f]  = scaler

def _apply_to_index(df: pd.DataFrame, idx, features: List[str], bundle, g_key) -> None:
    # transforms data at given index for a single group using bundle scalar and imputer
    for f in features:
        policy    = bundle["policy"][f]
        sc        = bundle["scalers"][g_key][f]
        imp       = bundle["imputers"][g_key][f]

        col = pd.to_numeric(df.iloc[idx][f], errors="coerce").values.reshape(-1, 1)

        if policy == "passthrough":
            df.iloc[idx, df.columns.get_loc(f)] = imp.transform(col).ravel()
            continue

        col_imp = imp.transform(col)
        val = sc.transform(col_imp) if sc is not None else col_imp
        df.iloc[idx, df.columns.get_loc(f)] = val.ravel()

def fit_scaler(
    df: pd.DataFrame,
    features: List[str],
    group_col: Optional[str] = "vehicle_id",
) -> Dict[str, Any]:

    if group_col is not None and group_col not in df.columns:
        raise KeyError(f"Group column '{group_col}' not found in df.")

    feat_list = list(features)
    print(f"Fitting scaler for features: {feat_list}")

    def _policy_for(f: str) -> str:
        if f in PASSTHROUGH_COLS:
            print(f"{f} -> passthrough")
            return "passthrough"
        if f in ROBUST_COLS:
            print(f"{f} -> robust")
            return "robust"
        print(f"{f} -> standard")
        return "standard"

    policy = {f: _policy_for(f) for f in feat_list}

    bundle: Dict[str, Any] = {
        "group_col": group_col,
        "features": feat_list,
        "policy": policy,
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

def transform_df(df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
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
        print("no group_col")
        _apply_to_index(out, out.index.tolist(), feat_list, bundle, g_key=None)

    out[feat_list] = out[feat_list].astype("float32")
    return out
