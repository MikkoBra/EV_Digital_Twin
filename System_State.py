from collections import deque
from typing import Optional, Sequence, Dict, Any

import pandas as pd
import plotly.express as px

class State:
    def __init__(self, timestamp, SOC, SOH, Charging_Cycles,
                 Battery_Temp, Motor_RPM, Motor_Torque, Motor_Temp,
                 Brake_Pad_Wear, Charging_Voltage, Tire_Pressure, DTC,
                 pred_dtc_prob: Optional[float] = None,
                 pred_dtc_label: Optional[int] = None):
        self.timestamp = timestamp
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
        self.pred_dtc_prob = pred_dtc_prob
        self.pred_dtc_label = pred_dtc_label

class DigitalTwin:
    def __init__(self, predictor=None):
        self.current_state = None
        self.historical_states: list[State] = []
        # use 'timestamp' column to match the predictor
        self.historical_dataset = pd.DataFrame(columns=[
            'timestamp','SOC','SOH','Charging_Cycles','Battery_Temp',
            'Motor_RPM','Motor_Torque','Motor_Temp','Brake_Pad_Wear',
            'Charging_Voltage','Tire_Pressure','DTC','pred_dtc_prob','pred_dtc_label'
        ])
        self.predictor = predictor

    def attach_predictor(self, predictor):
        self.predictor = predictor

    def update_state(self, sensor_data: Dict[str, Any]):
        if self.predictor:
            self.predictor.ingest(sensor_data)
            veh = sensor_data.get(getattr(self.predictor, "group_col"), "__default__")
            pred = self.predictor.predict_for(veh)
            pred_prob  = pred.get("prob_dtc_next_h") if pred.get("ready") else None
            pred_label = pred.get("pred_label") if pred.get("ready") else None
        else:
            pred_prob = pred_label = None

        state = State(
            timestamp=sensor_data.get("timestamp"),
            SOC=sensor_data.get("SOC"),
            SOH=sensor_data.get("SOH"),
            Charging_Cycles=sensor_data.get("Charging_Cycles"),
            Battery_Temp=sensor_data.get("Battery_Temp"),
            Motor_RPM=sensor_data.get("Motor_RPM"),
            Motor_Torque=sensor_data.get("Motor_Torque"),
            Motor_Temp=sensor_data.get("Motor_Temp"),
            Brake_Pad_Wear=sensor_data.get("Brake_Pad_Wear"),
            Charging_Voltage=sensor_data.get("Charging_Voltage"),
            Tire_Pressure=sensor_data.get("Tire_Pressure"),
            DTC=sensor_data.get("DTC"),
            pred_dtc_prob=pred_prob,
            pred_dtc_label=pred_label
        )
        self.current_state = state
        self.historical_states.append(state)

        row = dict(sensor_data)
        row["pred_dtc_prob"]  = pred_prob
        row["pred_dtc_label"] = pred_label
        # normalize to the expected schema
        if "TimeStamp" in row and "timestamp" not in row:
            row["timestamp"] = row.pop("TimeStamp")
        self.historical_dataset.loc[len(self.historical_dataset)] = {c: row.get(c) for c in self.historical_dataset.columns}

    def visualize_history(self, column, start_date=None, end_date=None):
        df = self.historical_dataset.copy()
        if not len(df):
            return
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        if start_date is not None:
            df = df[df["timestamp"] >= pd.to_datetime(start_date)]
        if end_date is not None:
            df = df[df["timestamp"] <= pd.to_datetime(end_date)]
        px.line(df, x="timestamp", y=column).show()

    def get_current_state(self):
        """
        Returns the current state of the digital twin as a dictionary.
        If no state is set yet, returns None.
        """
        if self.current_state is None:
            return None
        return self.current_state.to_dict()
