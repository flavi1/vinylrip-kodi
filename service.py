# SPDX-License-Identifier: GPL-2.0-or-later
"""Background service: offers the record/listen dialog when the turntable shows up."""
import os
import sys

import xbmc
import xbmcaddon
import xbmcgui

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resources.lib import detect  # noqa: E402

PLUGIN_URL = "plugin://plugin.audio.vinylrip/?action=main"
POLL_S = 3


class Watcher:
    def __init__(self, addon, read=detect.read_cards, launch=None, busy=None):
        self.addon, self.read = addon, read
        self.launch = launch or (lambda: xbmc.executebuiltin("RunPlugin(%s)" % PLUGIN_URL))
        self.busy = busy or (lambda: xbmcgui.Window(10000).getProperty("vinylrip.busy") == "1")
        self.seen = None  # None until the first scan: the startup scan counts as "appeared"

    def tick(self):
        if self.addon.getSetting("auto_popup") == "false":
            self.seen = set(c["id"] for c in self.read())
            return False
        found = detect.matching(self.read(), self.addon.getSetting("device"))
        ids = set(c["id"] for c in found)
        fresh = ids - (self.seen or set())
        self.seen = ids
        if fresh and not self.busy():
            self.launch()
            return True
        return False


def run():
    monitor = xbmc.Monitor()
    watcher = Watcher(xbmcaddon.Addon())
    while not monitor.abortRequested():
        watcher.tick()
        if monitor.waitForAbort(POLL_S):
            break


if __name__ == "__main__":
    run()
