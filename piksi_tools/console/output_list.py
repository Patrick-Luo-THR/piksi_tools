#!/usr/bin/env python
# Copyright (C) 2011-2014 Swift Navigation Inc.
# Contact: Fergus Noble <fergus@swift-nav.com>
#
# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.
#
# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.
"""
Contains the class OutputList
Displays Device Log messages and STDOUT/STDERR.
"""

import os
import time

from pyface.api import GUI
from traits.api import (Bool, Enum, Float, Font, HasTraits, Int, List,
                        Property, Str, Trait)
from traitsui.api import TabularEditor, UItem, View
from piksi_tools.console.gui_utils import ReadOnlyTabularAdapter

from piksi_tools.utils import sopen

# These levels are identical to sys.log levels
LOG_EMERG = 0  # system is unusable
LOG_ALERT = 1  # action must be taken immediately
LOG_CRIT = 2  # critical conditions
LOG_ERROR = 3  # error conditions
LOG_WARN = 4  # warning conditions
LOG_NOTICE = 5  # normal but significant condition
LOG_INFO = 6  # informational
LOG_DEBUG = 7  # debug-level messages

# These log levels are defined uniquely to this module to handle the
# list for stdout, stderror, and the device's log messages
# An unknown log level will end up with - 2
# A python stdout or stderr should come in as - 1

CONSOLE_LOG_LEVEL = -1
DEFAULT_LOG_LEVEL = -2

LOGFILE = time.strftime('swift-console-%Y%m%d-%H%M%S.log')
# This maps the log level numbers to a human readable string
# The unused log levels are commented out of the dict until used

# OTHERLOG_LEVELS will be unmaskable
UNMASKABLE_LEVELS = {
    CONSOLE_LOG_LEVEL: "CONSOLE",
}
# SYSLOG_LEVELS can be filtered

SYSLOG_LEVELS = {  # LOG_EMERG : "EMERG",
    # LOG_ALERT : "ALERT",
    # LOG_CRIT  : "CRIT",
    LOG_ERROR: "ERROR",
    LOG_WARN: "WARNING",
    # LOG_NOTICE: "NOTICE",
    LOG_INFO: "INFO",
    LOG_DEBUG: "DEBUG",
}

# Combine the log levels into one dict
ALL_LOG_LEVELS = SYSLOG_LEVELS.copy()
ALL_LOG_LEVELS.update(UNMASKABLE_LEVELS)

SYSLOG_LEVELS_INVERSE = {}
for key, value in SYSLOG_LEVELS.items():
    SYSLOG_LEVELS_INVERSE[value.lower()] = key
# Set default filter level
DEFAULT_LOG_LEVEL_FILTER = "WARNING"

DEFAULT_MAX_LEN = 250
LOG_LEVEL_TOOLTIP = "Log level sent from the device. "\
    "If CONSOLE, row was generated by the Console software."
TIMESTAMP_TOOLTIP = "Time at which the console software received the message,."


def str_to_log_level(level_str):
    """
    Maps a string into an integer log level
    If none can be found, uses the default
    """
    return SYSLOG_LEVELS_INVERSE.get(level_str.lower(), DEFAULT_LOG_LEVEL)


class LogItemOutputListAdapter(ReadOnlyTabularAdapter):
    """
    Tabular adapter for table of LogItems
    """
    columns = [('Host timestamp', 'timestamp'), ('Log level', 'log_level_str'),
               ('Message', 'msg')]
    font = Font('12')
    timestamp_width = Float(0.21)
    log_level_width = Float(0.07)
    msg_width = Float(0.72)
    can_drop = Bool(False)

    def get_tooltip(self, obj, name, row, column):
        """
        Define the tooltip messages for user mouse-over. Depends on column.
        Column is an integer with 0 index starting from left.
        No tooltip for the "message" column.  Parameters omitted as the
        """
        if column == 0:
            return TIMESTAMP_TOOLTIP
        if column == 1:
            return LOG_LEVEL_TOOLTIP
        else:
            return None


class LogItem(HasTraits):
    """
    This class handles items in the list of log entries
    Parameters
    ----------
    log_level  : int
      integer representing the log level
    timestamp : str
      the time that the console read the log item
    msg : str
      the text of the message
    """
    log_level = Int
    timestamp = Str
    msg = Str

    # log level string maps the int into a the string via the global ALL_LOG_LEVELS dict
    # If we can't find the int in the dict, we print "UNKNOWN"
    log_level_str = Property(
        fget=lambda self: ALL_LOG_LEVELS.get(self.log_level, "UNKNOWN"),
        depends_on='log_level')

    def __init__(self, msg, level):
        """
        Constructor for logitem
        Notes:
        ----------
        Timestamp initailzies to current system time
        msg is passed in by the user
        """
        # set constructor params
        self.log_level = level
        self.msg = msg
        # set timestamp
        self.timestamp = time.strftime("%b %d %Y %H:%M:%S")

    def matches_log_level_filter(self, log_level):
        """
        Function to perform filtering of a message based upon the loglevel passed

        Parameters
        ----------
        log_level : int
          Log level on which to filter

        Returns
        ----------
        True if message passes filter
        False otherwise
        """
        return self.log_level <= log_level

    def print_to_log(self):
        return "{0},{1},{2}\n".format(self.timestamp, self.log_level, self.msg)


class OutputList(HasTraits):
    """This class has methods to emulate an file-like output list of strings.

    The `max_len` attribute specifies the maximum number of bytes saved by
    the object.  `max_len` may be set to None.

    The `paused` attribute is a bool; when True, text written to the
    OutputList is saved in a separate buffer, and the display (if there is
    one) does not update.  When `paused` returns is set to False, the data is
    copied from the paused buffer to the main text string.
    """

    # Holds LogItems to display
    unfiltered_list = List(LogItem)
    # Holds LogItems while self.paused is True.
    _paused_buffer = List(LogItem)
    # filtered set of messages
    filtered_list = List(LogItem)
    # state of fiter on messages
    log_level_filter = Enum(list(SYSLOG_LEVELS.keys()))
    # The maximum allowed length of self.text (and self._paused_buffer).
    max_len = Trait(DEFAULT_MAX_LEN, None, Int)

    # When True, the 'write' or 'write_level' methods append to self._paused_buffer
    # When the value changes from True to False, self._paused_buffer is copied
    # back to self.unfiltered_list.
    paused = Bool(False)

    def __init__(self, tfile=False, outdir=''):
        if tfile:

            self.logfile = sopen(os.path.join(outdir, LOGFILE), 'w')
            self.tfile = True
        else:
            self.tfile = False

    def write(self, s):
        """
        Write to the lists OutputList as STDOUT or STDERR.

        This method exist to allow STDERR and STDOUT to be redirected into this
        display. It should only be called when writing to STDOUT and STDERR.
        Any log levels from this method will be LOG_LEVEL_CONSOLE
        Ignores spaces.

        Parameters
        ----------
        s : str
          string to cast as LogItem and write to tables
        """

        if s and not s.isspace():
            log = LogItem(s, CONSOLE_LOG_LEVEL)
            if self.paused:
                self.append_truncate(self._paused_buffer, log)
            else:
                self.append_truncate(self.unfiltered_list, log)
                if log.matches_log_level_filter(self.log_level_filter):
                    self.append_truncate(self.filtered_list, log)
            if self.tfile:
                self.logfile.write(log.print_to_log())

    def write_level(self, s, level):
        """
        Write to the lists in OutputList from device or user space.

        Parameters
        ----------
        s : str
          string to cast as LogItem and write to tables
        level : int
          Integer log level to use when creating log item.
        """
        if s and not s.isspace():
            log = LogItem(s, level)
            if self.paused:
                self.append_truncate(self._paused_buffer, log)
            else:
                self.append_truncate(self.unfiltered_list, log)
                if log.matches_log_level_filter(self.log_level_filter):
                    self.append_truncate(self.filtered_list, log)

    def append_truncate(self, buffer, s):
        """
        Append to a front of buffer, keeping overall size less than max_len

        Parameters
        ----------
        s : List
          Buffer to append
        s : LogItem
          Log Item to add
        """
        if len(buffer) > self.max_len:
            assert (len(buffer) -
                    self.max_len) == 1, "Output list buffer is too long"
            buffer.pop()
        buffer.insert(0, s)

    def clear(self):
        """
        Clear all Output_list buffers
        """
        self._paused_buffer = []
        self.filtered_list = []
        self.unfiltered_list = []

    def flush(self):
        GUI.process_events()

    def close(self):
        if self.tfile:
            self.logfile.close()

    def _log_level_filter_changed(self):
        """
        Copy items from unfiltered list into filtered list
        """
        self.filtered_list = [
            item for item in self.unfiltered_list
            if item.matches_log_level_filter(self.log_level_filter)
        ]

    def _paused_changed(self):
        """
        Swap buffers around when the paused boolean changes state.
        """
        if self.paused:
            # Copy the current list to _paused_buffer.  While the OutputStream
            # is paused, the write methods will append its argument to _paused_buffer.
            self._paused_buffer = self.unfiltered_list
        else:
            # No longer paused, so copy the _paused_buffer to the displayed list, and
            # reset _paused_buffer.
            self.unfiltered_list = self._paused_buffer
            # we have to refilter the filtered list too
            self._log_level_filter_changed()
            self._paused_buffer = []

    def traits_view(self):
        view = \
            View(
                UItem('filtered_list',
                      editor=TabularEditor(adapter=LogItemOutputListAdapter(), editable=False,
                                           vertical_lines=False, horizontal_lines=False))
            )
        return view
