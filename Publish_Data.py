import time
import pandas as pd
import json

#import MQTT
import paho.mqtt.client as paho
from paho import mqtt

# import the environment variables
import HiveMQ_configure

PLAYBACK_RATE = 0.1

def on_connect(client, userdata, flags, rc, properties=None):
    print("CONNACK received with code %s." % rc)

def on_publish(client, userdata, mid, properties=None):
    print("Published message with mid: " + str(mid))


client = paho.Client(client_id="EV_data_publisher", userdata=None, protocol=paho.MQTTv5)
client.on_connect = on_connect

client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)

client.username_pw_set(HiveMQ_configure.HIVEMQ_USER_NAME, HiveMQ_configure.HIVEMQ_PASSWORD)

client.connect(HiveMQ_configure.HIVEMQ_CLUSTER_URL, HiveMQ_configure.HIVEMQ_PORT)

client.loop_start()

#client.on_subscribe = on_subscribe
#client.on_message = on_message
client.on_publish = on_publish

# TODO: maybe create separate file for the preprocessing of the data, the preprocessing should probably done on the digital twin side
#  as in real life scenario we could not preprocess al the data at once but only the data that is received at each timestamp.
# Things as renaming the column and converting to datetime objects casn be done on publisher side.
# Read the data into pandas dataframe
heavy_user_data = pd.read_csv("data/heavy_user.csv")

# Give the timestamp column a name
heavy_user_data.rename(columns={"Unnamed: 0": "TimeStamp"}, inplace=True)

# TODO: convert the timestamps to datetime, this has to be done in later stage on receiver side as json does not accept datetime objects
#heavy_user_data["TimeStamp"] = pd.to_datetime(heavy_user_data["TimeStamp"])



for index, row in heavy_user_data.iterrows():
    # Extract the data from the row
    data = {
        "TimeStamp": row["TimeStamp"],
        "SOC": row["SOC"],
        "SOH": row["SOH"],
        "Charging_Cycles": row["Charging_Cycles"],
        "Battery_Temp": row["Battery_Temp"],
        "Motor_RPM": row["Motor_RPM"],
        "Motor_Torque": row["Motor_Torque"],
        "Motor_Temp": row["Motor_Temp"],
        "Brake_Pad_Wear": row["Brake_Pad_Wear"],
        "Charging_Voltage": row["Charging_Voltage"],
        "Tire_Pressure": row["Tire_Pressure"],
        "DTC": row["DTC"] 
    }

    # convert to json string
    data = json.dumps(data)

    # publish the data to the HiveMQ cluster
    publish_status = client.publish("ev/data", payload=data, qos=1)

    # check if publishing the data failed
    if publish_status[0] != 0:
        print("The publication has failed")

    time.sleep(PLAYBACK_RATE)

# we need to manually loop over a finite number of states and do not get a continuous stream of data therefore when the for loop is finished,
# the mqtt loop can stop and we can disconnect the client. 
client.loop_stop()
client.disconnect()

# need this in the receiver i think
#client.loop_forever()







