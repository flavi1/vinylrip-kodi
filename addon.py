# SPDX-License-Identifier: GPL-2.0-or-later
"""Plugin entry point: Music > Add-ons > Vinylrip."""
import os
import sys
from urllib.parse import parse_qs

import xbmcgui
import xbmcplugin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from resources.lib.flow import (S_LISTEN, S_QUALITY, S_RECORD, S_RECORD_MULTI, Flow)  # noqa: E402

ACTIONS = ("main", "record", "record_multi", "listen", "quality")


def route(argv, flow=None):
    handle = int(argv[1]) if len(argv) > 1 else -1
    params = {k: v[0] for k, v in parse_qs((argv[2] if len(argv) > 2 else "").lstrip("?")).items()}
    action = params.get("action")
    flow = flow or Flow()
    if action is None:
        for act, sid in (("record", S_RECORD), ("record_multi", S_RECORD_MULTI),
                         ("listen", S_LISTEN), ("quality", S_QUALITY)):
            item = xbmcgui.ListItem(flow.t(sid))
            xbmcplugin.addDirectoryItem(handle, "%s?action=%s" % (argv[0], act), item, False)
        xbmcplugin.endOfDirectory(handle)
        return
    if action == "main":
        flow.main()
    elif action == "record":
        flow.record(1)
    elif action == "record_multi":
        flow.record_multi()
    elif action == "listen":
        flow.listen()
    elif action == "quality":
        flow.choose_quality()


if __name__ == "__main__":
    route(sys.argv)
