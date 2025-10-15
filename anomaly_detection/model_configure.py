import os

import sys
from pathlib import Path
#checks for modules in folders above current one
sys.path.append(str(Path(__file__).resolve().parent.parent))

from root_dir import ROOT_DIR

# size of lag and rolling features
WINDOW_SIZE = 24

# Number of PCA components
PCA_COMPONENTS = 60

# ratio of data for testing
TEST_RATIO = 0.2

# Isolation Forest contamination param
CONTAMINATION = 0.04

# data path
DATA_PATH = os.path.join(ROOT_DIR, "data", "heavy_user.csv")

# model paths
ANOMALY_MODEL_PATH = os.path.join(ROOT_DIR, "anomaly_detection", "IF_anomaly_model.joblib")
SCALER_PATH = os.path.join(ROOT_DIR, "anomaly_detection", "scaler.joblib")
PCA_PATH = os.path.join(ROOT_DIR, "anomaly_detection", "PCA.joblib")

