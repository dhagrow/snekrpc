# encoding: utf-8

"""
Terminal utilities for the CLI.

These functions are meant to provide useful functionality for output modules.
(Set on the CLI or pack script with the --output-module flag.)
"""

from __future__ import unicode_literals

import calendar
import datetime
import math

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


##
## terminal
##

# Backport support for Python 3.3's `shutil.get_terminal_size()`.
# Adapted from: https://pypi.python.org/pypi/backports.shutil_get_terminal_size
# The `shutil` version is used when available.

try:
    from shutil import get_terminal_size
except ImportError:
    import collections
    import os
    import struct

    terminal_size = collections.namedtuple('terminal_size', 'columns lines')

    try:
        from ctypes import WinError, create_string_buffer, windll

        _handle_ids = {
            0: -10,
            1: -11,
            2: -12,
        }

        def _get_terminal_size(fd):
            handle = windll.kernel32.GetStdHandle(_handle_ids[fd])
            if handle == 0:
                raise OSError('handle cannot be retrieved')
            if handle == -1:
                raise WinError()
            csbi = create_string_buffer(22)
            res = windll.kernel32.GetConsoleScreenBufferInfo(handle, csbi)
            if res:
                res = struct.unpack('hhhhHhhhhhh', csbi.raw)
                left, top, right, bottom = res[5:9]
                columns = right - left + 1
                lines = bottom - top + 1
                return terminal_size(columns, lines)
            else:
                raise WinError()

    except ImportError:
        import fcntl
        import termios

        def _get_terminal_size(fd):
            try:
                res = fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\x00' * 4)
            except IOError as e:
                raise OSError(e) from e
            lines, columns = struct.unpack('hh', res)

            return terminal_size(columns, lines)

    def get_terminal_size(fallback=(80, 24)):
        """Get the size of the terminal window.
        For each of the two dimensions, the environment variable, COLUMNS
        and LINES respectively, is checked. If the variable is defined and
        the value is a positive integer, it is used.
        When COLUMNS or LINES is not defined, which is the common case,
        the terminal connected to sys.__stdout__ is queried
        by invoking os.get_terminal_size.
        If the terminal size cannot be successfully queried, either because
        the system doesn't support querying, or because we are not
        connected to a terminal, the value given in fallback parameter
        is used. Fallback defaults to (80, 24) which is the default
        size used by many terminal emulators.
        The value returned is a named tuple of type os.terminal_size.
        """
        # Try the environment first
        try:
            columns = int(os.environ['COLUMNS'])
        except (KeyError, ValueError):
            columns = 0

        try:
            lines = int(os.environ['LINES'])
        except (KeyError, ValueError):
            lines = 0

        # Only query if necessary
        if columns <= 0 or lines <= 0:
            try:
                size = _get_terminal_size(sys.__stdout__.fileno())
            except (NameError, OSError):
                size = terminal_size(*fallback)

            if columns <= 0:
                columns = size.columns
            if lines <= 0:
                lines = size.lines

        return terminal_size(columns, lines)
