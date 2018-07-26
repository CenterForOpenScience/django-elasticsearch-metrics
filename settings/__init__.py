# -*- coding: utf-8 -*-
"""Consolidates settings from defaults.py and local.py.
"""
import os
from .defaults import *  # noqa

try:
    from .local import *  # noqa
except ImportError as error:
    raise ImportError(
        "No local.py settings file found. Did you remember to "
        "copy local-dist.py to local.py?"
    )

# apply environment variables
globals().update(os.environ)
