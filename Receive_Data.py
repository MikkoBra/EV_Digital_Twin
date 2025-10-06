# ev_data_receiver.py

import json
import paho.mqtt.client as paho
from paho import mqtt
import HiveMQ_configure
from PySide6.QtCore import QObject, Signal
from System_State import DigitalTwin

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
            print(f"Message received on {msg.topic}") #: {payload}
            self.digital_twin.update_state(payload)
            state = self.digital_twin.current_state
            self.new_data.emit(state)
        except Exception as e:
            print(f"⚠️ Error processing message: {e}")

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