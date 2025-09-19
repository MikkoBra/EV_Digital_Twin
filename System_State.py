
import pandas as pd
import plotly.express as px


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
        # copy the historical dataset so we can potentially get a subset from it 
        temp_historical_dataset = self.historical_dataset

        # convert the timestamps to datetime objects so we can compare them
        temp_historical_dataset['TimeStamp'] = pd.to_datetime(temp_historical_dataset['TimeStamp'])

        # create the subset of the data which needs to be viualized
        if start_date is not None:
            start = pd.to_datetime(start_date)
            temp_historical_dataset = temp_historical_dataset[temp_historical_dataset['TimeStamp'] >= start]
        if end_date is not None:
            end = pd.to_datetime(end_date)
            temp_historical_dataset = temp_historical_dataset[temp_historical_dataset['TimeStamp'] <= end]

        # plot the data
        fig = px.line(temp_historical_dataset, x='TimeStamp', y=column)
        fig.show()
    