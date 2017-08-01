"""
 Ghost in the machine, move around the house and turn things off/on
"""
import logging
from datetime import timedelta as td
from random import uniform
import voluptuous as vol

from homeassistant.const import EVENT_STATE_CHANGED, STATE_ALARM_ARMED_AWAY, STATE_ON, STATE_OFF
from homeassistant.components.sun import STATE_ATTR_NEXT_SETTING
from homeassistant.helpers.event import track_point_in_time, track_utc_time_change
from homeassistant.util.dt import now
import homeassistant.components.switch as switch
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['sun']
_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    'platform':                 'gitm',
    vol.Required('wakeup'):     cv.time_period,
    vol.Required('tvtime'):     cv.time_period,
    vol.Required('bedtime'):    cv.time_period,
    vol.Required('alarm'):      cv.entity_id,
    vol.Required('bedroom'):    cv.entity_id,
    vol.Required('downstairs'): cv.entity_id
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    add_devices([Ghost(hass, config)])


class Ghost(switch.SwitchDevice):
    """ A Ghost that walks around turning things on and off """

    def __init__(self, hass, config):
        for k, v in config.items():
            setattr(self, k, v)
        self.hass = hass
        self.active = False
        self.today = now().day - 1
        self.times = {}
        # Sun provides a nice heartbeat for this process
        self.hass.bus.async_listen(EVENT_STATE_CHANGED, self.state_change_listener)

    def turn_on(self, **kwargs):
        self.active = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        self.active = False
        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool: return False
    @property
    def name(self):                return "Ghost"
    @property
    def is_on(self):               return self.active
    @property
    def device_state_attributes(self): 
        keys = sorted(self.times.keys())
        return {k: self.times[k].strftime("%H:%M:%S") for k in keys}
        
    def state_change_listener(self, event):
        state = event.data.get('new_state', None)
        if state is None:
            return

        elif state.entity_id == 'sun.sun' and self.is_on: # Sun update
            self.updatestates(state)

        elif state.entity_id == self.entity_id and self.is_on: # we turned on
            self.updatestates(self.hass.states.get('sun.sun'))

        elif state.entity_id == self.alarm: # turn on/off based on alarm
            self.active = (state.state == STATE_ALARM_ARMED_AWAY)
            self.schedule_update_ha_state()

        
    def updatestates(self, sunstate):
        cur = now()
        if cur.day != self.today: # new day, setup new times
            nextset = sunstate.attributes[STATE_ATTR_NEXT_SETTING]
            midnight = cur.replace(hour=0, minute=0, second=0, microsecond=0)

            self.times['1. wake']  = midnight + self.wakeup  + td(minutes=uniform(-20, +20))
            self.times['2. leave'] = self.times['1. wake'] + td(minutes=20) + td(minutes=uniform(-3,3))

            self.times['3. tv']    = midnight + self.tvtime  + td(minutes=uniform(-20, +20))
            self.times['4. bed']   = midnight + self.bedtime + td(minutes=uniform(-20, +20))
            self.times['5. sleep'] = self.times['4. bed'] + td(minutes=uniform(10,15))

            self.today = cur.day
            self.schedule_update_ha_state()
            _LOGGER.debug("Set new times sunset: {} {}".format(nextset, self.device_state_attributes))

        # times occur as wake [bed] leave [none] tv [liv] step [none] bed [bed] sleep [none]
        bed = liv = STATE_OFF
        if   cur > self.times['5. sleep']: pass
        elif cur > self.times['4. bed']:   bed = STATE_ON
        elif cur > self.times['3. tv']:    liv = STATE_ON
        elif cur > self.times['2. leave']: pass
        elif cur > self.times['1. wake']:  bed = STATE_ON

        if self.hass.states.get(self.bedroom).state != bed:
            _LOGGER.debug("toggle bedroom")
            switch.toggle(self.hass, self.bedroom)
        if self.hass.states.get(self.downstairs).state != liv:
            _LOGGER.debug("toggle living room")
            switch.toggle(self.hass, self.downstairs)

