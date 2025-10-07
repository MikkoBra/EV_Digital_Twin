import time
import json
import pandas as pd
import paho.mqtt.client as paho
from paho import mqtt
import HiveMQ_configure


class EVDataPublisher:
    def __init__(self, csv_path="data/heavy_user.csv", topic="ev/data", playback_rate=0.1):
        self.csv_path = csv_path
        self.topic = topic
        self.playback_rate = playback_rate
        self._running = False

        # Initialize MQTT client
        self.client = paho.Client(client_id="EV_data_publisher", userdata=None, protocol=paho.MQTTv5)
        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish

        # TLS & credentials
        self.client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
        self.client.username_pw_set(HiveMQ_configure.HIVEMQ_USER_NAME, HiveMQ_configure.HIVEMQ_PASSWORD)

    # MQTT callbacks
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"Publisher connected with code {rc}.")

    def on_publish(self, client, userdata, mid, properties=None):
        # print(f"Published message with mid: {mid}")
        pass

    def connect(self):
        """Connect to the HiveMQ cluster."""
        print("Connecting to HiveMQ cluster...")
        self.client.connect(HiveMQ_configure.HIVEMQ_CLUSTER_URL, HiveMQ_configure.HIVEMQ_PORT)
        self.client.loop_start()

    def disconnect(self):
        """Disconnect cleanly from MQTT broker."""
        print("Disconnecting from HiveMQ...")
        self._running = False
        self.client.loop_stop()
        self.client.disconnect()

    def publish_data(self):
        """Read CSV and publish rows as MQTT messages."""
        df = pd.read_csv(self.csv_path)
        df.rename(columns={"Unnamed: 0": "TimeStamp"}, inplace=True)

        for _, row in df.iterrows():
            if not self._running:
                print("⏹️ Publishing stopped.")
                break

            data = row.to_dict()
            payload = json.dumps(data)

            result = self.client.publish(self.topic, payload=payload, qos=1)
            if result.rc != 0:
                print("⚠️ Publish failed!")
            time.sleep(self.playback_rate)

    def run(self):
        """Main method to connect, publish, and disconnect."""
        try:
            self._running = True
            self.connect()
            self.publish_data()
        finally:
            self.disconnect()
    
    def stop(self):
        """Signal the publisher to stop publishing."""
        self._running = False


if __name__ == "__main__":
    publisher = EVDataPublisher()
    publisher.run()