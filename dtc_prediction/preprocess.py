"""
Preprocessing utilities for DTC prediction.
Extracted from DTC_prediction_model.ipynb
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional


def _apply_to_index(out, idx, features, bundle, g_key) -> None:
    """Apply scaling and imputation to a subset of rows (by index)."""
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


def transform(df: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    """
    Transform a dataframe using fitted scalers and imputers from the bundle.
    
    Args:
        df: Input dataframe with raw features
        bundle: Dictionary containing:
            - features: List of feature columns
            - group_col: Column to group by (e.g., 'vehicle_id')
            - scalers: Dict of fitted scalers per group
            - imputers: Dict of fitted imputers per group
            - policy: Dict of scaling policy per feature
            - masked_flags: Dict of mask flag columns per feature
            
    Returns:
        Transformed dataframe with scaled and imputed features
    """
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
