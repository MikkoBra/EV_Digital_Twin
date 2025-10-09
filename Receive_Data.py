import json
import paho.mqtt.client as paho
from paho import mqtt
import HiveMQ_configure
from PySide6.QtCore import QObject, Signal
from System_State import DigitalTwin
import pandas as pd
import warnings
import threading

warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=pd.errors.SettingWithCopyWarning)


class ReceiverSignals(QObject):
    new_data = Signal(object)


class EVDataReceiver(QObject):
    new_data = Signal(object)

    def __init__(self, topic="ev/data"):
        super().__init__()
        self.topic = topic
        self.digital_twin = DigitalTwin()
        self._on_message_signal = None
        self._running = False

        # --- Thread lock for shared data access ---
        self._lock = threading.Lock()

        # Initialize MQTT client
        self.client = paho.Client(client_id="EV_data_receiver", userdata=None, protocol=paho.MQTTv5)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_subscribe = self.on_subscribe

        # TLS & credentials
        self.client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
        self.client.username_pw_set(HiveMQ_configure.HIVEMQ_USER_NAME, HiveMQ_configure.HIVEMQ_PASSWORD)

    # MQTT callbacks
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"Receiver connected with code {rc}. Subscribing to '{self.topic}'...")
        client.subscribe(self.topic, qos=1)

    def on_subscribe(self, client, userdata, mid, granted_qos, properties=None):
        print(f"Subscribed: mid={mid}, qos={granted_qos}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"Message received on {msg.topic}")
            
            # --- Update Digital Twin state ---
            self.digital_twin.update_state(payload)

            # --- Perform anomaly detection + DTC prediction concurrently ---
            anomaly_thread = threading.Thread(target=self._run_anomaly_detection)
            dtc_thread = threading.Thread(target=self._run_dtc_prediction)

            anomaly_thread.start()
            dtc_thread.start()

            # --- Wait for both to finish ---
            anomaly_thread.join()
            dtc_thread.join()

            # --- Emit fully processed state ---
            state = self.digital_twin.current_state
            self.new_data.emit(state)

        except Exception as e:
            print(f"⚠️ Error processing message: {e}")

    # --- Safe threaded functions ---
    def _run_anomaly_detection(self):
        try:
            with self._lock:
                dt = self.digital_twin
                ad = getattr(dt, "ad", None)
                ad_config = getattr(dt, "ad_config", None)
                if ad is None or ad_config is None:
                    return  # anomaly detection not configured

                if len(dt.historical_dataset) <= ad_config.WINDOW_SIZE:
                    return

                data_window = dt.historical_dataset.tail(ad_config.WINDOW_SIZE + 1).copy()
                is_anomaly, anomaly_score = ad.inference(data_window, dt.anomaly_model, dt.anomaly_scaler)

                current_state = dt.current_state
                current_state.is_anomaly = is_anomaly
                current_state.anomaly_score = anomaly_score

            print(
                f"[Anomaly] On Timestamp: {current_state.timestamp}, "
                f"Is Anomaly: {current_state.is_anomaly}, "
                f"Anomaly Score: {current_state.anomaly_score:.4f}"
            )
        except Exception as e:
            print(f"⚠️ Anomaly detection error: {e}")

    def _run_dtc_prediction(self):
        try:
            with self._lock:
                dt = self.digital_twin
                dtc_pred = getattr(dt, "dtc_pred", None)
                dtc_cfg = getattr(dt, "dtc_cfg", None)
                if dtc_pred is None or dtc_cfg is None:
                    return  # DTC not configured

                if len(dt.historical_dataset) < dtc_cfg.seq_len:
                    return

                data = dt.historical_dataset.copy()
                data['vehicle_id'] = dt.vehicle_id

                dtc_score, dtc_label = dtc_pred.predict(
                    data,
                    dt.dtc_model,
                    dt.dtc_scaler,
                    seq_len=dtc_cfg.seq_len
                )

                current_state = dt.current_state
                current_state.dtc_score = dtc_score
                current_state.dtc_label = dtc_label

            print(
                f"[DTC] On Timestamp: {current_state.timestamp}, "
                f"Label: {current_state.dtc_label}, "
                f"Score: {current_state.dtc_score:.4f}"
            )
        except Exception as e:
            print(f"⚠️ DTC prediction error: {e}")

    # --- Standard receiver methods ---
    def connect(self):
        """Connect to HiveMQ and start listening."""
        print("Connecting to HiveMQ cluster...")
        self.client.connect(HiveMQ_configure.HIVEMQ_CLUSTER_URL, HiveMQ_configure.HIVEMQ_PORT)

    def run(self):
        """Start receiving messages."""
        self._running = True
        self.connect()
        print("Receiver is now listening for data...")
        while self._running:
            self.client.loop(timeout=1.0)
    
    def stop(self):
        self._running = False
        self.client.disconnect()
    
    def get_dt_state(self):
        return self.digital_twin.current_state

    def get_dt_history(self, attribute, start_date=None, end_date=None):
        return self.digital_twin.visualize_history(attribute, start_date, end_date)


if __name__ == "__main__":
    receiver = EVDataReceiver()
    receiver.run()
