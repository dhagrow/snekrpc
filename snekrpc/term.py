# encoding: utf-8

"""
Terminal utilities for the CLI.

These functions are meant to provide useful functionality for output modules.
(Set on the CLI with the --output-module flag.)
"""

import calendar
import datetime
import math
from shutil import get_terminal_size

try:
    import colorama
    from colorama import Back, Fore, Style
except ImportError:
    colorama = None
else:
    colorama.init()

##
## colors
##

_enable_color = bool(colorama)


def set_color_enabled(enabled=True):
    global _enable_color
    _enable_color = enabled


def color(s, fore=None, back=None, style=None):
    if _enable_color and colorama:
        fore = getattr(Fore, fore.upper()) if fore else ''
        back = getattr(Back, back.upper()) if back else ''
        style = getattr(Style, style.upper()) if style else ''
        reset = Style.RESET_ALL
    else:
        fore, back, style, reset = [''] * 4
    return '{fore}{back}{style}{s}{reset}'.format(
        fore=fore, back=back, style=style, s=s, reset=reset
    )


##
## text alignment
##


def align(s, width, alignment='left'):
    try:
        alignment = {'left': '<', 'center': '^', 'right': '>'}[alignment]
    except KeyError:
        raise ValueError('invalid alignment: {}'.format(alignment)) from None
    return '{:{}{}}'.format(s, alignment, width)


def elide(s, width=None, align='right', ellipsis='…'):
    """Append ellipsis to *s* if longer than *width*.

    Defaults to terminal width.
    """
    width = width or get_terminal_size().columns
    if len(s) <= width:
        return s

    ellipsis_len = len(ellipsis)
    if align == 'right':
        return s[: width - ellipsis_len] + ellipsis
    elif align == 'left':
        return ellipsis + s[-width + ellipsis_len :]
    elif align == 'center':
        w_2 = width / 2
        l_2 = ellipsis_len / 2
        return (
            s[: math.ceil(w_2) - math.ceil(l_2)]
            + ellipsis
            + s[-math.floor(w_2) + math.floor(l_2) :]
        )
    else:
        raise ValueError('invalid alignment choice: {}'.format(align))


##
## date/time
##


# from: http://stackoverflow.com/a/13287083
def utc_to_local(utc_dt):
    """Convert a UTC datetime object to local time."""
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= datetime.timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)


def to_formatted_localtime(dt):
    return utc_to_local(dt).strftime('%Y-%m-%d %H:%M:%S')
