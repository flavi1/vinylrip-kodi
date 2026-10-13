# SPDX-License-Identifier: GPL-2.0-or-later
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fake_engine import FakeProc  # noqa: E402
from resources.lib.engine import Engine, EngineError, Session  # noqa: E402


class R:
    def __init__(self, rc, out, err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


class EngineTest(unittest.TestCase):
    def test_devices(self):
        e = Engine("python3 -m vinylrip", "/c.toml", run=lambda argv, **k: (
            self.assertEqual(argv, ["python3", "-m", "vinylrip", "--config", "/c.toml", "--json", "devices", "--qualities"]),
            R(0, json.dumps({"cards": [{"id": "x"}]})))[1])
        self.assertEqual(e.devices(True), [{"id": "x"}])

    def test_devices_errors(self):
        for run in (lambda *a, **k: R(1, "", "bad"), lambda *a, **k: R(0, "not json")):
            with self.assertRaises(EngineError):
                Engine(run=run).devices()

        def missing(*a, **k):
            raise FileNotFoundError()
        with self.assertRaises(EngineError):
            Engine(run=missing).devices()

        def slow(*a, **k):
            raise subprocess.TimeoutExpired("x", 1)
        with self.assertRaises(EngineError):
            Engine(run=slow).devices()

    def test_session_events_and_exit(self):
        p = FakeProc({"x": [{"event": "a"}]})
        s = Session(p)
        self.assertEqual(s.wait_for("ready", timeout=2)["event"], "ready")
        s.send("x")
        seen = []
        ev = s.wait_for("never", timeout=0.5, on_other=seen.append)
        self.assertEqual(seen, [{"event": "a"}])
        self.assertIsNone(ev)
        s.close()
        self.assertEqual(s.wait_for("exit", timeout=2)["event"], "exit")
        with self.assertRaises(EngineError):
            s.proc.stdin = type("X", (), {"write": lambda self, s: (_ for _ in ()).throw(BrokenPipeError())})()
            s.send("y")

    def test_garbage_line_is_logged_not_fatal(self):
        class P(FakeProc):
            pass
        p = FakeProc({}, first=())
        p.q.put("not json\n")
        s = Session(p)
        self.assertEqual(s.get(2)["event"], "log")
        p.q.put(None)


@unittest.skipUnless(os.environ.get("VINYLRIP_SRC"), "set VINYLRIP_SRC to the engine's src/ to run the real-engine test")
class RealEngine(unittest.TestCase):
    def test_protocol_against_real_engine(self):
        env = dict(os.environ, PYTHONPATH=os.environ["VINYLRIP_SRC"])
        e = Engine("%s -m vinylrip" % sys.executable, None, popen=lambda argv, **k: subprocess.Popen(argv, env=env, **k))
        s = e.session(device="doesnotexist")
        ev = s.wait_for("ready", timeout=30)
        self.assertEqual(ev["event"], "error")
        self.assertIn("not found", ev["message"])
        s.close()


if __name__ == "__main__":
    unittest.main()
