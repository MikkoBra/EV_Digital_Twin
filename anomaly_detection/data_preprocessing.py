import pandas
import numpy as np
import System_State
import anomaly_detection.model_configure as ad_config

def compute_window_features(data):
    # These features do not need lag/window features
    features_excluded = ["DTC", "TimeStamp"]
    ev_reduced_cols = [col for col in data.columns if col not in features_excluded]

    for col in ev_reduced_cols:
        
        # add the rolling features
        data[f"{col}_rolling-{ad_config.WINDOW_SIZE}_std"] = data[col].rolling(window=ad_config.WINDOW_SIZE, min_periods=ad_config.WINDOW_SIZE).std()
        data[f"{col}_rolling-{ad_config.WINDOW_SIZE}_mean"] = data[col].rolling(window=ad_config.WINDOW_SIZE, min_periods=ad_config.WINDOW_SIZE).mean()
        
        # add the lag features
        for i in range(1, ad_config.WINDOW_SIZE + 1):
            data[f"{col}_lag-{i}"] = data[col].shift(i)

    # this drops all the rows except the most recent one containing all the lag and rolling window features
    data.dropna(inplace=True)

    return data


def compute_temporal_features(data):
    n_months = 12
    n_days = 7
    n_hours = 24

    # extract series containing temporal info, i.e. month day of the week, and the hour
    months = data["TimeStamp"].dt.month
    days = data["TimeStamp"].dt.dayofweek
    hours = data["TimeStamp"].dt.hour

    # To maintain some temporal information we do cyclic encoding on the month day and hour extracted from the timestamp. This is cleaner and represents the cyclic pattern better.
    # Both the sine and cosine necessary to maintain the full info 
    data["Cosine_Month"] = np.cos((2 * np.pi / n_months) * months)
    data["Sine_Month"] = np.sin((2 * np.pi / n_months) * months)

    data["Cosine_Day"] = np.cos((2 * np.pi / n_days) * days)
    data["Sine_Day"] = np.sin((2 * np.pi / n_days) * days)

    data["Cosine_Hour"] = np.cos((2 * np.pi / n_hours) * hours)
    data["Sine_Hour"] = np.sin((2 * np.pi / n_hours) * hours)

    return data

def feature_engineering(data):
    # small value to prevent divisions by zero
    safe_div = 1e-4

    # captures ratio between the temperature and the torque of the motor
    data["Temp_Torque"] =  data["Motor_Temp"] / (data["Motor_Torque"] + safe_div)

    # captures ratio between the temperature and the RPM of the motor
    data["Temp_RPM"] =  data["Motor_Temp"] / (data["Motor_RPM"] + safe_div)

    # captures ratio between temperature and state of health of the battery
    data["Temp_Health"] =  data["Battery_Temp"] / (data["SOH"] + safe_div)

    #  captures temperature ratio between motor and battery
    data["Temp_Ratio"] = data["Motor_Temp"] / (data["Battery_Temp"] + safe_div)

    # captures ratio between the temperature and state of charge of the battery
    data["Temp_Charge"] =  data["Battery_Temp"] / (data["SOC"] + safe_div)

    return data


def preprocess_data(data, scaler):
    # the charging voltage is a constant so not informative for the AI models
    data.drop("Charging_Voltage", axis=1, inplace=True)

    # add lag and rolling features
    data = compute_window_features(data)

    # add temporal features
    data = compute_temporal_features(data)

    # drop the columns we do not need for the model
    data.drop(columns=["DTC", "TimeStamp"], inplace=True)

    # add domain specefic features
    data = feature_engineering(data)

    scaled_data = scaler.transform(data)

    return scaled_data





    