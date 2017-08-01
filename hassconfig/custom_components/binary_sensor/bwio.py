""" Minimal interface back to main module """
from functools import partial
import custom_components.bwio as bwio
DEPENDENCIES = ['bwio']
PLATFORM_SCHEMA = bwio.BWIO_INPUT_SCHEMA
setup_platform = partial(bwio.setup_pins, bwio.create_input)
