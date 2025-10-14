import pandas as pd
import numpy as np
import joblib
from sklearn.preprocessing import RobustScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest
from model_configure import WINDOW_SIZE

import sys
from pathlib import Path
import json

PARENT = Path(__file__).resolve().parent.parent if "__file__" in globals() else Path.cwd().parent
sys.path.insert(0, str(PARENT))

from root_dir import ROOT_DIR

# read the data into pandas dataframe
ev_data = pd.read_csv(f"{ROOT_DIR}/data/heavy_user.csv")

# give the timestamp column a name
ev_data.rename(columns={"Unnamed: 0": "TimeStamp"}, inplace=True)

# convert the timestamps to datetime objects such that we can make comparisons
ev_data["TimeStamp"] = pd.to_datetime(ev_data["TimeStamp"])

# the charging voltage is a constant so not informative for the AI models (this step should be part of the pipeline)
ev_data.drop("Charging_Voltage", axis=1, inplace=True)

# obtain list with features that need rolling window and lag features
features_excluded = ["DTC", "TimeStamp"]
ev_reduced_cols = [col for col in ev_data.columns if col not in features_excluded]


#this is only for the training and testing of the model for runtime predictions we need to obtain the lag features via the historical states in the digital twin
# here we can just shift the columns because we already have the full dataset.
for col in ev_reduced_cols:
     
     # add the rolling features
     ev_data[f"{col}_rolling-{WINDOW_SIZE}_std"] = ev_data[col].rolling(window=WINDOW_SIZE, min_periods=WINDOW_SIZE).std()
     ev_data[f"{col}_rolling-{WINDOW_SIZE}_mean"] = ev_data[col].rolling(window=WINDOW_SIZE, min_periods=WINDOW_SIZE).mean()
     
     # add the lag features
     for i in range(1, WINDOW_SIZE + 1):
        ev_data[f"{col}_lag-{i}"] = ev_data[col].shift(i)


# this drops the first WINDOW_SIZE rows/hours of data because the lag features have missing values because there is not enough historical data available yet
ev_data.dropna(inplace=True)

n_months = 12
n_days = 7
n_hours = 24

# extract series containing temporal info, i.e. month day of the week, and the hour
months = ev_data["TimeStamp"].dt.month
days = ev_data["TimeStamp"].dt.dayofweek
hours = ev_data["TimeStamp"].dt.hour

# To maintain some temporal information we do cyclic encoding on the month day and hour extracted from the timestamp. This is cleaner and represents the cyclic pattern better.
# Both the sine and cosine necessary to maintain the full info 
ev_data["Cosine_Month"] = np.cos((2 * np.pi / n_months) * months)
ev_data["Sine_Month"] = np.sin((2 * np.pi / n_months) * months)

ev_data["Cosine_Day"] = np.cos((2 * np.pi / n_days) * days)
ev_data["Sine_Day"] = np.sin((2 * np.pi / n_days) * days)

ev_data["Cosine_Hour"] = np.cos((2 * np.pi / n_hours) * hours)
ev_data["Sine_Hour"] = np.sin((2 * np.pi / n_hours) * hours)

# drop the columns we do not need for the model
ev_data_reduced = ev_data.drop(columns=["DTC", "TimeStamp"])


# feature design based on domain knowledge

# small value to prevent divisions by zero
safe_div = 1e-4

# captures ratio between the temperature and the torque of the motor
ev_data_reduced["Temp_Torque"] =  ev_data_reduced["Motor_Temp"] / (ev_data_reduced["Motor_Torque"] + safe_div)

# captures ratio between the temperature and the RPM of the motor
ev_data_reduced["Temp_RPM"] =  ev_data_reduced["Motor_Temp"] / (ev_data_reduced["Motor_RPM"] + safe_div)

# captures ratio between temperature and state of health of the battery
ev_data_reduced["Temp_Health"] =  ev_data_reduced["Battery_Temp"] / (ev_data_reduced["SOH"] + safe_div)

#  captures temperature ratio between motor and battery
ev_data_reduced["Temp_Ratio"] = ev_data_reduced["Motor_Temp"] / (ev_data_reduced["Battery_Temp"] + safe_div)

# captures ratio between the temperature and state of charge of the battery
ev_data_reduced["Temp_Charge"] =  ev_data_reduced["Battery_Temp"] / (ev_data_reduced["SOC"] + safe_div)


# normalizing the data using the robustscaler as we do have outliers in the data that we do not remove.
scaler = RobustScaler().fit(ev_data_reduced)
scaled_data = scaler.transform(ev_data_reduced)
scaled_df = pd.DataFrame(scaled_data, columns=ev_data_reduced.columns)

# train en test split without shuffle to keep the order intact
X_train, X_test = train_test_split(scaled_df, test_size=0.2, shuffle=False)

# train the model on the trainings data
IF_model = IsolationForest(random_state=0, contamination=0.03).fit(X_train)

# store the scale and model parameters
joblib.dump(scaler, "anomaly_detection/scaler.joblib")
joblib.dump(IF_model, "anomaly_detection/IF_anomaly_model.joblib")

