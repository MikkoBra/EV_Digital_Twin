import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
import threading
from PySide6.QtCore import QObject, Signal
from Publish_Data import EVDataPublisher
from Receive_Data import EVDataReceiver

class DataHandler(QObject):
    """
    Facilitates communication between the model and the dashboard.
    """
    new_data_signal = Signal(object)

    def __init__(self, digital_twin=None):
        """
        Connects the event reception signal from the data receiver to a function
        that handles this reception.
        """
        super().__init__()
        self.digital_twin = digital_twin
        self.publisher = EVDataPublisher(csv_path="data/heavy_user.csv")
        self.receiver = EVDataReceiver()
        self.receiver.new_data.connect(self.handle_new_data)
        self._threads = []
        self.is_paused = False

    def start_run(self, playback_speed, data_window, start_datetime=None):
        """
        Starts replay of sensor data by activating the EVDataPublisher with a
        specified playback speed and activating the EVDataReceiver.
        """
        if self.digital_twin:
            import pandas as pd
            self.digital_twin.historical_dataset = pd.DataFrame(columns=[
                'TimeStamp', 'SOC', 'SOH', 'Charging_Cycles', 'Battery_Temp',
                'Motor_RPM', 'Motor_Torque', 'Motor_Temp', 'Brake_Pad_Wear',
                'Charging_Voltage', 'Tire_Pressure', 'DTC'
            ])
            self.digital_twin.historical_states = []
            self.digital_twin.current_state = None
        
        self.publisher.playback_rate = playback_speed
        
        # Set start datetime if provided
        if start_datetime:
            self.publisher.start_datetime = start_datetime
        else:
            self.publisher.start_datetime = None

        # Start receiver in background thread
        receiver_thread = threading.Thread(target=self.receiver.run, daemon=True)
        receiver_thread.start()

        # Start publisher in background thread
        publisher_thread = threading.Thread(target=self.publisher.run, daemon=True)
        publisher_thread.start()

        self._threads = [receiver_thread, publisher_thread]

    def handle_new_data(self, current_state):
        """
        Updates the internal representation of the digital twin with the new sensor
        data, fetches output from the ML algorithms based on this data, and emits
        the resulting system state as a signal to the user interface.
        """
        if self.digital_twin:
            sensor_data = {
                'TimeStamp': current_state.timestamp,
                'SOC': current_state.soc,
                'SOH': current_state.soh,
                'Charging_Cycles': current_state.charging_cycles,
                'Battery_Temp': current_state.battery_temp,
                'Motor_RPM': current_state.motor_rpm,
                'Motor_Torque': current_state.motor_torque,
                'Motor_Temp': current_state.motor_temp,
                'Brake_Pad_Wear': current_state.brake_pad_wear,
                'Charging_Voltage': current_state.charging_voltage,
                'Tire_Pressure': current_state.tire_pressure,
                'DTC': current_state.dtc
            }
            self.digital_twin.update_state(sensor_data)
        
        self.new_data_signal.emit(current_state)

    def pause_run(self):
        """
        Pauses the data replay by pausing the publisher.
        """
        self.is_paused = True
        self.publisher.pause()
        print("DataHandler: Simulation paused")
    
    def resume_run(self):
        """
        Continues the data replay by resuming the publisher.
        """
        self.is_paused = False
        self.publisher.resume()
        print("DataHandler: Simulation resumed")

    def stop_run(self):
        """
        Stops publisher and receiver threads.
        """
        self.is_paused = False
        self.publisher.stop()
        self.receiver.stop()
        for t in self._threads:
            t.join()
