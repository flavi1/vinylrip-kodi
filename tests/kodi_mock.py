# SPDX-License-Identifier: GPL-2.0-or-later
"""Minimal fakes of xbmc, xbmcgui, xbmcaddon, xbmcplugin, xbmcvfs for unit tests."""
import sys
import types

WINDOW_PROPS = {}
BUILTINS = []
DIRECTORY = []


class FakeAddon:
    def __init__(self, settings=None):
        self.settings = dict(settings or {})

    def getSetting(self, k):
        return self.settings.get(k, "")

    def setSetting(self, k, v):
        self.settings[k] = v

    def getLocalizedString(self, i):
        return "S%d{0}" % i if i in (30007, 30008, 30014, 30017, 30020, 30023, 30024) else "S%d" % i

    def getAddonInfo(self, k):
        return "/tmp/vinylrip-kodi-test-profile" if k == "profile" else ""


class FakeDialog:
    """Scripted dialog: ``answers`` is consumed in order; every call is logged."""

    def __init__(self, answers=()):
        self.answers = list(answers)
        self.log = []

    def _next(self, kind, *a, **k):
        self.log.append((kind, a, k))
        return self.answers.pop(0) if self.answers else -1

    def select(self, heading, items, **k):
        return self._next("select", heading, list(items))

    def yesno(self, heading, message, **k):
        return self._next("yesno", heading, message)

    def ok(self, heading, message):
        self.log.append(("ok", (heading, message), {}))
        return True

    def numeric(self, kind, heading, default=""):
        return self._next("numeric", heading, default)

    def notification(self, *a, **k):
        self.log.append(("notification", a, k))


class FakeWindow:
    def __init__(self, id_=0):
        pass

    def getProperty(self, k):
        return WINDOW_PROPS.get(k, "")

    def setProperty(self, k, v):
        WINDOW_PROPS[k] = v

    def clearProperty(self, k):
        WINDOW_PROPS.pop(k, None)


class FakeBG:
    def create(self, *a): pass
    def update(self, *a, **k): pass
    def close(self): pass


class FakeListItem:
    def __init__(self, label=""):
        self.label = label


class FakeMonitor:
    def abortRequested(self): return True
    def waitForAbort(self, t): return True


def install():
    xbmc = types.ModuleType("xbmc")
    xbmc.executebuiltin = BUILTINS.append
    xbmc.Monitor = FakeMonitor
    xbmcgui = types.ModuleType("xbmcgui")
    xbmcgui.Dialog = FakeDialog
    xbmcgui.Window = FakeWindow
    xbmcgui.DialogProgressBG = FakeBG
    xbmcgui.ListItem = FakeListItem
    xbmcaddon = types.ModuleType("xbmcaddon")
    xbmcaddon.Addon = FakeAddon
    xbmcplugin = types.ModuleType("xbmcplugin")
    xbmcplugin.addDirectoryItem = lambda h, url, item, folder: DIRECTORY.append((url, item.label))
    xbmcplugin.endOfDirectory = lambda h: None
    xbmcvfs = types.ModuleType("xbmcvfs")
    xbmcvfs.translatePath = lambda p: p
    for m in (xbmc, xbmcgui, xbmcaddon, xbmcplugin, xbmcvfs):
        sys.modules[m.__name__] = m


install()
