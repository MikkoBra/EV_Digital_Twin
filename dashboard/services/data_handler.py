import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
import threading
from PySide6.QtCore import QObject, Signal, QMetaObject, Qt
from Publish_Data import EVDataPublisher
from Receive_Data import EVDataReceiver

class DataHandler(QObject):
    # Signals for all EV parameters
    new_data_signal = Signal(object)
    # soc_changed = Signal(float)
    # soh_changed = Signal(float)
    # charging_cycles_changed = Signal(int)
    # battery_temp_changed = Signal(float)
    # motor_rpm_changed = Signal(float)
    # motor_torque_changed = Signal(float)
    # motor_temp_changed = Signal(float)
    # brake_pad_wear_changed = Signal(float)
    # charging_voltage_changed = Signal(float)
    # tire_pressure_changed = Signal(float)
    # dtc_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.publisher = EVDataPublisher(csv_path="data/heavy_user.csv")
        self.receiver = EVDataReceiver()
        self.receiver.new_data.connect(self.handle_new_data)
        self._threads = []

    def start_run(self, playback_speed, data_window):
        self.publisher.playback_rate = playback_speed

        # Start receiver in background thread
        receiver_thread = threading.Thread(target=self.receiver.run, daemon=True)
        receiver_thread.start()

        # Start publisher in background thread
        publisher_thread = threading.Thread(target=self.publisher.run, daemon=True)
        publisher_thread.start()

        self._threads = [receiver_thread, publisher_thread]

    def handle_new_data(self, current_state):
        """Thread-safe emission of all signals to GUI thread"""
        self.new_data_signal.emit(current_state)

    def _emit_signals(self, current_state):
        self.timestamp_changed.emit(str(current_state.timestamp))
        self.soc_changed.emit(current_state.soc)
        self.soh_changed.emit(current_state.soh)
        self.charging_cycles_changed.emit(current_state.charging_cycles)
        self.battery_temp_changed.emit(current_state.battery_temp)
        self.motor_rpm_changed.emit(current_state.motor_rpm)
        self.motor_torque_changed.emit(current_state.motor_torque)
        self.motor_temp_changed.emit(current_state.motor_temp)
        self.brake_pad_wear_changed.emit(current_state.brake_pad_wear)
        self.charging_voltage_changed.emit(current_state.charging_voltage)
        self.tire_pressure_changed.emit(current_state.tire_pressure)
        self.dtc_changed.emit(str(current_state.dtc))

    def stop_run(self):
        """Stop publisher and receiver threads cleanly"""
        self.publisher.stop()
        self.receiver.stop()
        for t in self._threads:
            t.join()
