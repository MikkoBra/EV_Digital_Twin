"""
Quick script to refit and save the DTC scaler with current sklearn version.
This fixes the 'keep_empty_features' compatibility issue.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import joblib
from dtc_prediction.DTC_Config import Config
from dtc_prediction.model_training import load_all, infer_features, fit_scaler

def main():
    print("=" * 60)
    print("Refitting DTC Scaler with Current sklearn Version")
    print("=" * 60)
    
    cfg = Config()
    
    print("\n1. Loading data...")
    df = load_all(cfg)
    print(f"   Loaded {len(df)} records from {df['vehicle_id'].nunique()} vehicles")
    
    print("\n2. Inferring features...")
    features = infer_features(df, cfg)
    print(f"   Features: {features}")
    
    print("\n3. Fitting scaler on full dataset...")
    scaler_bundle = fit_scaler(df, features, group_col="vehicle_id")
    print("   Scaler fitted successfully!")
    
    print("\n4. Saving scaler...")
    scaler_path = os.path.join(cfg.model_dir, cfg.scaler_name)
    joblib.dump(scaler_bundle, scaler_path)
    print(f"   ✅ Scaler saved to: {scaler_path}")
    
    print("\n" + "=" * 60)
    print("Done! The DTC scaler is now compatible with sklearn", end=" ")
    import sklearn
    print(sklearn.__version__)
    print("=" * 60)

if __name__ == "__main__":
    main()
