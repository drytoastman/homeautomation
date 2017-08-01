"""
 Support for my little custom I/O board from years ago
"""
import logging
import re
import serial
import serial.threaded

import voluptuous as vol

from homeassistant.const import (EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.const import (CONF_PLATFORM, CONF_PORT, CONF_NAME, STATE_ON, STATE_OFF)
from homeassistant.components.switch import SwitchDevice
from homeassistant.components.binary_sensor import BinarySensorDevice
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyserial>=3.1.1']
_LOGGER = logging.getLogger(__name__)
BOARD = None
DOMAIN = 'bwio'
CONF_PINS = 'pins'
CONF_HIDE = 'hide'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)

BWIO_OUTPUT_SCHEMA = vol.Schema ({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_HIDE, default=False): cv.boolean,
    vol.Required(CONF_PINS): vol.Schema({ cv.positive_int: cv.string })
})

BWIO_INPUT_SCHEMA = vol.Schema ({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_HIDE, default=False): cv.boolean,
    vol.Required(CONF_PINS): vol.Schema({
         cv.positive_int: [ cv.string ] }) # can voluptous do array with different types?
})


def setup(hass, config):
    """ Setup the BWIO interface, there are 16 inputs and 16 relay outputs """
    global BOARD
    try:
        BOARD = BWIOBoard(config[DOMAIN][CONF_PORT])
    except (serial.serialutil.SerialException, FileNotFoundError):
        _LOGGER.exception("BWIO port (%s) is not accessible." % (config[DOMAIN][CONF_PORT]))
        return False

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, lambda e: BOARD.ping())
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, lambda e: BOARD.close())
    return True

def setup_pins(buildfunc, hass, config, add_devices, discovery_info=None):
    """ Set up the BWIO io pin, this gets used in the device file for setup_platform """
    """ buildfunc is one of create_input or create_output """
    global BOARD
    if BOARD is None:
        _LOGGER.error("A connection has not been made to the BWIO board")
        return False

    # list comprehension: build each pin device from config and pass to add_devices
    add_devices(buildfunc(pin, arg, config[CONF_HIDE]) for pin, arg in config.get(CONF_PINS).items())

def create_input(pin, arg, hide):
    dev = BWIOInput(BOARD, pin, arg[0], arg[1], hide) # args = name and sensortype
    BOARD._inputs.append(dev)
    return dev

def create_output(pin, arg, hide):
    dev = BWIOOutput(BOARD, pin, arg, hide)
    BOARD._outputs.append(dev)
    return dev


class BWIOBoard(serial.threaded.LineReader):
    """ Representation of an BWIO board. """

    def __init__(self, port):
        """ Connect to the board. """
        super(serial.threaded.LineReader, self).__init__()
        self._inputs = list()
        self._outputs = list()
        self._thread = serial.threaded.ReaderThread(serial.Serial(port), self)
        self._thread.start()

    def __call__(self):
        """ Force pyserial ReaderThread to just keep using us as the protocol object """
        return self  

    def ping(self):
        self.ping_input()
        self.ping_output()
        self.ping_debouncerate()

    def ping_input(self):
        self.send("I")
        
    def ping_output(self):
        self.send("O")

    def ping_debouncerate(self):
        self.send("S")

    def set_output(self, pin, val):
        self.send("O%X=%X" % (pin, val))

    def set_debouncerate(self, ms):
        self.send("S=%X", ms)

    def send(self, data):
        _LOGGER.debug("Sending data (%s)", data)
        self.write_line(data)

    def handle_line(self, line):
        _LOGGER.debug("Received data (%s)", line.strip())

        # Check for input report
        ins = re.match(r"I=([0-9,A-F]+)", line)
        if ins is not None:
            val = int(ins.group(1), 16)
            for dev in self._inputs:
                dev._state = (val & (1 << dev._pin)) != 0
                dev.schedule_update_ha_state()

        # Check for output report
        outs = re.match(r"O=([0-9,A-F]+)", line)
        if outs is not None:
            val = int(outs.group(1), 16)
            for dev in self._outputs:
                dev._state = (val & (1 << dev._pin)) != 0
                dev.schedule_update_ha_state()

        # TODO: check for sampling report (how to set from outside?)

    def close(self):
        _LOGGER.info("Closing port")
        self._thread.close()


class BWIOOutput(SwitchDevice):
    """ Switch interface to an output pin """

    def __init__(self, parent, pin, name, hide):
        _LOGGER.debug("Create %s on output pin %d" % (name, pin))
        self._parent = parent
        self._pin = pin
        self._name = name
        self._hidden = hide
        self._state = None

    def turn_on(self, **kwargs):   self._parent.set_output(self._pin, 1)
    def turn_off(self, **kwargs):  self._parent.set_output(self._pin, 0)
    def update(self):              self._parent.ping_output()

    @property
    def should_poll(self) -> bool: return False
    @property
    def name(self):                return self._name
    @property
    def is_on(self):               return self._state != 0
    @property
    def hidden(self):              return self._hidden


class BWIOInput(BinarySensorDevice):
    """ Binary sensor interface to an input pin """

    def __init__(self, parent, pin, name, sensortype, hide):
        _LOGGER.debug("Create %s on input pin %d, type %s" % (name, pin, sensortype))
        self._parent = parent
        self._pin = pin
        self._name = name
        self._type = sensortype
        self._hidden = hide
        self._state = None

    def update(self):              self._parent.ping_input()

    @property
    def should_poll(self) -> bool: return False
    @property
    def device_class(self):        return self._type
    @property
    def name(self):                return self._name
    @property
    def is_on(self):               return self._state != 0
    @property
    def hidden(self):              return self._hidden

