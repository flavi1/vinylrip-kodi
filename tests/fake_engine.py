# SPDX-License-Identifier: GPL-2.0-or-later
"""A stand-in for ``vinylrip --json session``: replays scripted events per command."""
import json
import queue
import threading


class FakeStdin:
    def __init__(self, proc):
        self.proc = proc
        self.sent = []

    def write(self, s):
        self.sent.append(json.loads(s))
        self.proc.react(self.sent[-1])

    def flush(self):
        pass

    def close(self):
        self.proc.q.put(None)


class FakeProc:
    """``script``: command name -> list of events to emit (or callable(cmd) -> list)."""

    def __init__(self, script, first=({"event": "ready"},)):
        self.q = queue.Queue()
        self.script = script
        self.stdin = FakeStdin(self)
        self.stdout = iter(self.q.get, None)
        for e in first:
            self.q.put(json.dumps(e) + "\n")

    def react(self, cmd):
        ev = self.script.get(cmd["cmd"], [])
        for e in ev(cmd) if callable(ev) else ev:
            self.q.put(json.dumps(e) + "\n")
        if cmd["cmd"] in ("cancel",):
            self.q.put(None)

    def wait(self, timeout=None):
        return 0

    def kill(self):
        pass
