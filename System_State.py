
import pandas as pd
import plotly.express as px
import anomaly_detection.anomaly_detection as ad
import io
import joblib
import tensorflow as tf
import anomaly_detection.model_configure as ad_config
import dtc_prediction.DTC_Config as dtc_cfg
import dtc_prediction.DTC_Predictor as dtc_pred
from root_dir import ROOT_DIR
import os
DATA_PATH= os.path.join(ROOT_DIR, "data")
HEAVY_PATH = os.path.join(DATA_PATH, "heavy_user.csv") 

class State:
    def __init__(self, TimeStamp, SOC, SOH, Charging_Cycles,
                 Battery_Temp, Motor_RPM, Motor_Torque, Motor_Temp,
                 Brake_Pad_Wear, Charging_Voltage, Tire_Pressure, DTC):
        # Sensor data
        self.vehicle_id = os.path.splitext(os.path.basename(HEAVY_PATH))[0].replace("_user", "")
        self.timestamp = pd.to_datetime(TimeStamp)
        self.soc = SOC
        self.soh = SOH
        self.charging_cycles = Charging_Cycles
        self.battery_temp = Battery_Temp
        self.motor_rpm = Motor_RPM
        self.motor_torque = Motor_Torque
        self.motor_temp = Motor_Temp
        self.brake_pad_wear = Brake_Pad_Wear
        self.charging_voltage = Charging_Voltage
        self.tire_pressure = Tire_Pressure
        self.dtc = DTC

        # Anomaly data
        self.is_anomaly = False
        self.anomaly_score = None

        # DTC Prediction data
        self.dtc_score = None
        self.dtc_label = False

    def to_dict(self):  
        """Convert State to dictionary."""
        return {
            'TimeStamp': self.timestamp,
            'SOC': self.soc,
            'SOH': self.soh,
            'Charging_Cycles': self.charging_cycles,
            'Battery_Temp': self.battery_temp,
            'Motor_RPM': self.motor_rpm,
            'Motor_Torque': self.motor_torque,
            'Motor_Temp': self.motor_temp,
            'Brake_Pad_Wear': self.brake_pad_wear,
            'Charging_Voltage': self.charging_voltage,
            'Tire_Pressure': self.tire_pressure,
            'DTC': self.dtc
        }


class DigitalTwin:
    def __init__(self):
        # load the models for inference
        self.anomaly_model = joblib.load(ad_config.ANOMALY_MODEL_PATH)
        self.anomaly_scaler = joblib.load(ad_config.SCALER_PATH)
        self.anomaly_pca = joblib.load(ad_config.PCA_PATH)
        self.dtc_model = tf.keras.models.load_model(dtc_cfg.get_model_path())
        self.dtc_scaler = joblib.load(dtc_cfg.get_scaler_path())

        #initialize the data storage structures
        self.current_state = None
        self.historical_states = []
        self.historical_dataset = pd.DataFrame(columns=['TimeStamp', 'SOC', 'SOH', 'Charging_Cycles', 'Battery_Temp',
       'Motor_RPM', 'Motor_Torque', 'Motor_Temp', 'Brake_Pad_Wear',
       'Charging_Voltage', 'Tire_Pressure', 'DTC'])

        self.vehicle_id = os.path.splitext(os.path.basename(HEAVY_PATH))[0].replace("_user", "")
           
        

    # update the state of the digital twin with new sensor data
    def update_state(self, sensor_data):
        # set the sensor data in current state
        current_state = State(**sensor_data)

        self.historical_dataset.loc[len(self.historical_dataset)] = sensor_data

        self.historical_dataset["TimeStamp"] = pd.to_datetime(self.historical_dataset["TimeStamp"])

        # Anomaly detection, we first check wheter there is enough historical data to compute the features
        if len(self.historical_dataset) > ad_config.WINDOW_SIZE:
            data_window = self.historical_dataset.tail(ad_config.WINDOW_SIZE + 1).copy()
            is_anomaly, anomaly_score = ad.inference(data_window, self.anomaly_model, self.anomaly_scaler, self.anomaly_pca)
        
            # set the anomaly info in the current state
            current_state.is_anomaly = is_anomaly
            current_state.anomaly_score = anomaly_score


        ## DTC Prediction
        if len(self.historical_dataset) >= dtc_cfg.SEQUENCE_LEN:
            data = self.historical_dataset.copy()
            data['vehicle_id'] = self.vehicle_id
            current_state.dtc_score, current_state.dtc_label= dtc_pred.predict(
                data,
                self.dtc_model,
                self.dtc_scaler,
                seq_len=dtc_cfg.SEQUENCE_LEN
            )
        # add current state to the historical states
        self.historical_states.append(current_state)
        self.current_state = current_state


    # View the historical data of a specific sensor, this function can be called when an anomaly occurs such that the user can directly view the data of that
    # component. Can also be called when the user wants to view a specific timeframe of the data.
    def visualize_history(self, column, start_date=None, end_date=None):
        temp_historical_dataset = self.historical_dataset.copy()

        # Filter by date range
        if start_date is not None:
            start = pd.to_datetime(start_date)
            temp_historical_dataset = temp_historical_dataset[temp_historical_dataset['TimeStamp'] >= start]
        if end_date is not None:
            end = pd.to_datetime(end_date)
            temp_historical_dataset = temp_historical_dataset[temp_historical_dataset['TimeStamp'] <= end]

        # Create plot
        fig = px.line(temp_historical_dataset, x='TimeStamp', y=column, title=f"{column} Over Time")

        img_bytes = fig.to_image(format="png")
        return io.BytesIO(img_bytes)
    
    def get_current_state(self):
        """
        Returns the current state of the digital twin as a dictionary.
        If no state is set yet, returns None.
        """
        if self.current_state is None:
            return None
        return self.current_state.to_dict()
