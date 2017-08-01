"""
    Group all the locks info together so we can set the same code on each lock.  The Schlage
    locks do not let you download the user codes though I really don't care to store them
    anyhow, I just want to assign a name to each entry location (a la Vera handling) so I can
    remember which ones to delete/reassign later.

    We also have to resort to ugliness to get the data about UserCode availability.

    Not sure what can be reused.
"""

import logging
import collections
import operator
import yaml
import time
from datetime import datetime, timedelta

import homeassistant.components.zwave.const as zconst
from homeassistant.components import zwave
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_change

from pydispatch import dispatcher
from openzwave.network import ZWaveNetwork

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['zwave' ]
DOMAIN = 'locksinterface'

USER_CODE_STATUS_BYTE   = 8
NOT_USER_CODE_INDEXES   = (0, 254, 255)  # Enrollment code, refresh and code count
CODE_UNASSIGNED         = "_unassigned"
CODE_UNKNOWN            = "_unknown"

LOCKSI = None

def setup(hass, config):
    """ Set up our service call interface, a refresher task that stops itself and hook into the zwave events """
    global LOCKSI
    LOCKSI = LocksInterface(hass)
    LOCKSI.schedule_update_ha_state()

    hass.services.register(DOMAIN, "setusercode", LOCKSI.set_user_code,
                { 'description': "Sets a user code on all locks",
                       'fields': { 'newname': {'description': 'A name for reference'},
                                      'code': {'description': 'The code to use as an ascii string of [0-9]'}}})
    hass.services.register(DOMAIN, "clearusercode", LOCKSI.clear_user_code,
                { 'description': "Clear a user code on all locks using name",
                       'fields': { 'oldname': {'description': 'The name of the code'}}})
    hass.services.register(DOMAIN, "renameusercode", LOCKSI.rename_user_code,
                { 'description': "Rename a user code on all locks",
                       'fields': { 'oldname': {'description': 'The present name for the code'},
                                   'newname': {'description': 'The new name for the code'}}})

    dispatcher.connect(LOCKSI.value_added, ZWaveNetwork.SIGNAL_VALUE_ADDED) #, weak=False)
    dispatcher.connect(LOCKSI.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED) #, weak=False)
    track_time_change(hass, LOCKSI.refresh_unknown, second='/5')
    return True


class LocksInterface(Entity):
    """ A singleton interface for setting the same code by name on all locks """
    """ Also resort to some hackery to get the available/assigned bit from the ZWave CommandClass """

    CONFIG_NAME = 'locksinterface.yaml'

    def __init__(self, hass):
        self.hass = hass
        self.entity_id = "locksinterface.singleton"
        self.modtime = 0
        self.refresh = set()
        self.load_state()

    @property
    def hidden(self) -> bool:          return True
    @property
    def state(self) -> str:            return "{} of {}".format(len(self.refresh), sum(len(x) for x in self.values.values()))
    @property
    def device_state_attributes(self): return { 'values': self.values, 'modtime': self.modtime }  # HASS does shallow change check so we add modtime here

    def load_state(self):
        try:
            with open(self.hass.config.path(LocksInterface.CONFIG_NAME), 'r') as fp:
                self.values = yaml.load(fp) or {}
                return
        except Exception as e:
            _LOGGER.info("Unable to load old state: {}".format(e), e)
        self.values = {}

    def save_state(self):
        try:
            with open(self.hass.config.path(LocksInterface.CONFIG_NAME), 'w') as fp:
                fp.write(yaml.dump(self.values))
            self.modtime = int(time.time())
            self.schedule_update_ha_state()
        except Exception as e:
            _LOGGER.info("Unable to save state: " + e, e)

    def verify_present(self, value):
        if value.parent_id not in self.values:
            self.values[value.parent_id] = { value.index: CODE_UNKNOWN }
        elif value.index not in self.values[value.parent_id]: 
            self.values[value.parent_id][value.index] = CODE_UNKNOWN
        else:
            return # Already know this one
        _LOGGER.debug("new user code location {}, {}".format(value.parent_id, value.index))
        self.save_state()

    def value_added(self, value):
        """ New ZWave Value added (generally on network start), make note of any user code entries on generic locks """
        if (value.command_class == zconst.COMMAND_CLASS_USER_CODE and value.index not in NOT_USER_CODE_INDEXES):
            _LOGGER.debug("add: {}".format(value))
            self.verify_present(value)
            self.refresh.add(value)

    def value_changed(self, value):
        """ We got a code update, data is probably just '****' but there is a status byte in the command class """
        if (value.command_class == zconst.COMMAND_CLASS_USER_CODE and value.index not in NOT_USER_CODE_INDEXES):
            self.verify_present(value)
            if value in self.refresh:
                self.refresh.remove(value)

            # PyOZW doesn't expose command class data, we reach into the raw message data and get it ourselves
            assigned = bool(value.network.manager.getNodeStatistics(value.home_id, value.parent_id)['lastReceivedMessage'][USER_CODE_STATUS_BYTE])
            current  = self.values[value.parent_id][value.index]
            _LOGGER.debug("{} code {} assigned {}".format(value.parent_id, value.index, assigned))
            # Update our label if necessary (don't have one or its no longer set on the lock)
            if not assigned:
                self.values[value.parent_id][value.index] = CODE_UNASSIGNED
            elif current == CODE_UNKNOWN:
                # we didn't load a previous state
                self.values[value.parent_id][value.index] = "Unnamed Entry {}".format(value.index) 
            elif current.startswith('_'):
                # remove the precursor to indicate that it succeeded
                self.values[value.parent_id][value.index] = current[1:]
            else:
                # skip state update as nothing changed
                return
            self.save_state()

    def refresh_unknown(self, now):
        """
            We need to query ZWave UserCode values that we don't have any previous state for to see if they
            are available or occupied.  Using OZW Option RefreshAllUserCodes doesn't always work for me.
        """
        for value in self.refresh:
            # Make a single request now, don't spam zwave network, gets removed when it replies
            _LOGGER.debug("refresh {},{}".format(value.parent_id, value.index))
            value.refresh()
            return

    def set_user_code(self, service):
        """ Set the ascii number string code to index X on each selected lock """
        newname = service.data.get('newname')
        code = service.data.get('code')
        locksused = set()

        if not all([ord(x) in range(0x30, 0x39+1) for x in code]):
            _LOGGER.error("Invalid code provided to setcode ({})".format(code))
            return

        # Assign to one free space on each lock
        for nodeid, labels in self.values.items():
            for index, label in labels.items():
                if label == CODE_UNASSIGNED:
                    labels[index] = "_"+newname
                    self.hass.services.call('lock', 'set_usercode', {'node_id':nodeid, 'code_slot':index, 'usercode':code})
                    locksused.add(nodeid)
                    break 
            
        self.save_state()
        locksskipped = self.values.keys() - locksused
        if len(locksskipped) > 0:
            _LOGGER.error("Failed to set the code on the following locks {}".format(locksskipped))


    def clear_user_code(self, service):
        """ Clear a code on each lock based on name """
        oldname = service.data.get('oldname')
        _LOGGER.debug("clear code {}".format(oldname))
        for nodeid, labels in self.values.items():
            for index, label in labels.items():
                if label == oldname:
                    labels[index] = '_'+labels[index]
                    self.hass.services.call('lock', 'clear_usercode', {'node_id':nodeid, 'code_slot':index})
        self.save_state()


    def rename_user_code(self, service):
        """ Rename a code whereever we find it """
        oldname = service.data.get('oldname')
        newname = service.data.get('newname')
        _LOGGER.debug("rename {} to {}".format(oldname, newname))
        for nodeid, labels in self.values.items():
            for index, label in labels.items():
                if label == oldname:
                    labels[index] = newname
        self.save_state()

