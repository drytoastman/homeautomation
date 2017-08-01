#!/usr/bin/env python3

import time
import os
import yaml

import paho.mqtt.client as mqtt
from AppKit import NSSound

def on_connect(client, userdata, flags, rc):
    client.subscribe("switches/set/#")

def on_message(client, userdata, msg):
    if msg.topic == 'switches/set/warning':
        if msg.payload == b'ON':
            warning.play()
            client.publish('switches/pub/warning', 'ON')
        else:
            warning.stop()
            client.publish('switches/pub/warning', 'OFF')

# Find out where the config files are and load our HASS api password
basedir = os.path.dirname(__file__)
with open(os.path.join(basedir, 'http.yaml'), 'r') as fp:
    config = yaml.load(fp)
    pw = config['api_password']

# Now load any sounds we want
warning = NSSound.alloc()
warning.initWithContentsOfFile_byReference_(os.path.join(basedir, 'sounds', 'warning.wav'), True)
warning.setLoops_(True)

# And start of the MQTT connection through the docker-machine
client = mqtt.Client("sound-client")
client.username_pw_set('homeassistant', pw)
client.on_connect = on_connect
client.on_message = on_message
client.connect("192.168.99.100")
client.loop_forever()

