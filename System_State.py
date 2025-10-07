import pandas as pd
import plotly.express as px
import io


class State:
    def __init__(self, TimeStamp, SOC, SOH, Charging_Cycles,
                Battery_Temp, Motor_RPM, Motor_Torque, Motor_Temp,
                Brake_Pad_Wear, Charging_Voltage, Tire_Pressure, DTC):
        self.timestamp = TimeStamp
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
        self.current_state = None
        self.historical_states = []
        self.historical_dataset = pd.DataFrame(columns=['TimeStamp', 'SOC', 'SOH', 'Charging_Cycles', 'Battery_Temp',
       'Motor_RPM', 'Motor_Torque', 'Motor_Temp', 'Brake_Pad_Wear',
       'Charging_Voltage', 'Tire_Pressure', 'DTC'])
        

    # update the state of the digital twin with new sensor data
    def update_state(self, sensor_data):
        current_state = State(**sensor_data)
        self.historical_states.append(current_state)
        self.current_state = current_state
        self.historical_dataset.loc[len(self.historical_dataset)] = sensor_data


    # View the historical data of a specific sensor, this function can be called when an anomaly occurs such that the user can directly view the data of that
    # component. Can also be called when the user wants to view a specific timeframe of the data.
    def visualize_history(self, column, start_date=None, end_date=None):
        temp_historical_dataset = self.historical_dataset.copy()
        temp_historical_dataset['TimeStamp'] = pd.to_datetime(temp_historical_dataset['TimeStamp'])

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
    
    