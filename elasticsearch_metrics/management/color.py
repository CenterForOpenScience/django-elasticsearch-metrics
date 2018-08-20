# -*- coding: utf-8 -*-
"""
Sets up the terminal color scheme.

Adapted from django-extensions.
https://github.com/django-extensions/django-extensions/blob/master/django_extensions/management/color.py
"""

from django.core.management import color
from django.utils import termcolors


def _dummy_style_func(msg):
    return msg


def no_style():
    style = color.no_style()
    for role in ("METRIC", "ES_TEMPLATE"):
        setattr(style, role, _dummy_style_func)
    return style


def color_style():
    if color.supports_color():
        style = color.color_style()
        style.METRIC = termcolors.make_style(opts=("bold",))
        style.ES_TEMPLATE = termcolors.make_style(fg="yellow")
    else:
        style = no_style()
    return style
