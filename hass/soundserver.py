#!/usr/bin/env python3

import glob
import os
import time
import yaml

import paho.mqtt.client as mqtt
from AppKit import NSSound

sounds = dict()
basedir = os.path.dirname(__file__)

def load_sound(name, loop=False):
    f = os.path.join(basedir, 'sounds', name+'.wav')
    sounds[name] = NSSound.alloc()
    sounds[name].initWithContentsOfFile_byReference_(f, True)
    if loop:
        sounds[name].setLoops_(True)

def on_connect(client, userdata, flags, rc):
    client.subscribe("switches/set/#")

def on_message(client, userdata, msg):
    if msg.topic.startswith('switches/set/'):
        sound = msg.topic[13:]
        if sound not in sounds:
            return
        if msg.payload == b'ON':
            sounds[sound].play()
            client.publish('switches/pub/'+sound, 'ON')
        else:
            sounds[sound].stop()
            client.publish('switches/pub/'+sound, 'OFF')

# Find out where the config files are and load our HASS api password
with open(os.path.join(basedir, 'secrets.yaml'), 'r') as fp:
    config = yaml.load(fp)
    pw = config['http_password']

# Now load any sounds we want
load_sound('warning', True)
load_sound('doorbell', False)

# And start of the MQTT connection through the docker-machine
client = mqtt.Client("sound-client")
client.username_pw_set('homeassistant', pw)
client.on_connect = on_connect
client.on_message = on_message
client.connect("192.168.99.100")
client.loop_forever()

