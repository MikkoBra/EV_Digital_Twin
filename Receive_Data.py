import json

import paho.mqtt.client as paho
from paho import mqtt

import HiveMQ_configure

def on_connect(client, userdata, flags, rc, properties=None):
    print("CONNACK received with code %s." % rc)

    # after the client is connected we subscribe to the ev data messages 
    client.subscribe("ev/data", qos=1)

def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


def on_message(client, userdata, msg):
    print(msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    # TODO: probably need a function here that unpacks the data and sets the current state but also stores them in a 
    # dataframe with all the data up until that moment 

client = paho.Client(client_id="EV_data_receiver", userdata=None, protocol=paho.MQTTv5)
client.on_connect = on_connect

client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)

client.username_pw_set(HiveMQ_configure.HIVEMQ_USER_NAME, HiveMQ_configure.HIVEMQ_PASSWORD)

client.connect(HiveMQ_configure.HIVEMQ_CLUSTER_URL, HiveMQ_configure.HIVEMQ_PORT)

client.on_subscribe = on_subscribe
client.on_message = on_message

# the client should keep listening to incoming messages 
client.loop_forever()