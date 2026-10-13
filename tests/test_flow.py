# SPDX-License-Identifier: GPL-2.0-or-later
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kodi_mock  # noqa: E402
from fake_engine import FakeProc  # noqa: E402
from resources.lib import flow as F  # noqa: E402
from resources.lib.engine import Engine  # noqa: E402


def make(answers, script, settings=None, first=({"event": "ready"},)):
    procs = []

    def popen(argv, **kw):
        p = FakeProc(script, first)
        p.argv = argv
        procs.append(p)
        return p
    dialog = kodi_mock.FakeDialog(answers)
    f = F.Flow(kodi_mock.FakeAddon(settings or {}), dialog, Engine("vinylrip", "/cfg.toml", popen=popen))
    return f, dialog, procs


FACE = {"start_face": [{"event": "recording", "face": "A"}],
        "stop_face": [{"event": "face_done", "face": "A", "overruns": 0}]}


class FlowTest(unittest.TestCase):
    def setUp(self):
        kodi_mock.WINDOW_PROPS.clear()

    def kinds(self, d):
        return [k for k, _, _ in d.log]

    def test_two_sides_then_process(self):
        script = {"start_face": [{"event": "recording"}],
                  "stop_face": [{"event": "face_done", "overruns": 0}],
                  "finish": [{"event": "stage", "stage": "split"},
                             {"event": "done", "album_dir": "/m/A", "warnings": [], "faces_to_check": []}]}
        # start A, finish A, next, start B, finish B, disc done
        f, d, procs = make([0, 0, 0, 0, 0, 1], script)
        f.record(1)
        sent = [c["cmd"] for c in procs[0].stdin.sent]
        self.assertEqual(sent, ["start_face", "stop_face", "start_face", "stop_face", "finish"])
        self.assertEqual(d.log[-1][0], "ok")
        self.assertIn("S30020", d.log[-1][1][1])
        self.assertNotIn("vinylrip.busy", kodi_mock.WINDOW_PROPS)

    def test_argv_has_device_quality_discs(self):
        f, d, procs = make([1], {}, {"device": "Device", "quality": "192000:S32_LE:2"})
        f.record(2)
        a = procs[0].argv
        self.assertEqual(a[:5], ["vinylrip", "--config", "/cfg.toml", "--json", "session"])
        self.assertIn("2", a)
        self.assertIn("Device", a)
        self.assertIn("192000:S32_LE:2", a)

    def test_cancel_before_start_asks_delete(self):
        f, d, procs = make([1, 1], {"cancel": [{"event": "cancelled"}]})
        f.record(1)
        cancel = [c for c in procs[0].stdin.sent if c["cmd"] == "cancel"]
        self.assertEqual(cancel, [{"cmd": "cancel", "delete": True}])
        self.assertIn("yesno", self.kinds(d))

    def test_cancel_during_face_keep(self):
        f, d, procs = make([0, 2, 0], dict(FACE, cancel=[{"event": "cancelled"}]))
        f.record(1)
        self.assertEqual(procs[0].stdin.sent[-1], {"cmd": "cancel", "delete": False})

    def test_escape_during_face_is_a_cancel_not_a_loss(self):
        f, d, procs = make([0, -1, 0], dict(FACE, cancel=[{"event": "cancelled"}]))
        f.record(1)
        self.assertIn("yesno", self.kinds(d))

    def test_listen_toggle_during_face(self):
        script = dict(FACE, listen=lambda c: [{"event": "listening", "on": c["on"]}])
        f, d, procs = make([0, 1, 1, 0, 1], dict(script, finish=[{"event": "done", "album_dir": "/x"}]))
        f.record(1)
        listens = [c["on"] for c in procs[0].stdin.sent if c["cmd"] == "listen"]
        self.assertEqual(listens, [True, False])
        labels = [a[1] for k, a, _ in d.log if k == "select"]
        self.assertIn("S30010", labels[2])  # "stop listening" shown once listening

    def test_error_shows_kept_dir_hint(self):
        script = {"start_face": [{"event": "error", "message": "boom", "kept": "/jobs/1"}]}
        f, d, procs = make([0], script)
        f.record(1)
        ok = [a for k, a, _ in d.log if k == "ok"][-1]
        self.assertIn("boom", ok[1])
        self.assertIn("S30017", ok[1])

    def test_engine_missing(self):
        def popen(argv, **kw):
            raise FileNotFoundError()
        d = kodi_mock.FakeDialog()
        f = F.Flow(kodi_mock.FakeAddon(), d, Engine("nope", None, popen=popen))
        f.record(1)
        self.assertEqual(d.log[-1][0], "ok")
        self.assertIn("S30023", d.log[-1][1][1])

    def test_engine_dies_at_start(self):
        f, d, procs = make([], {}, first=({"event": "error", "message": "no device", "kept": None},))
        f.record(1)
        self.assertIn("no device", d.log[-1][1][1])

    def test_manual_choice(self):
        cands = [{"index": 0, "artist": "X", "album": "Y", "year": 1980, "tracks": 9},
                 {"index": 1, "artist": "X", "album": "Z", "year": 1981, "tracks": 10}]
        script = dict(FACE, finish=[{"event": "choose_release", "candidates": cands}],
                      choose=lambda c: [{"event": "done", "album_dir": "/ok", "index": c["index"]}])
        f, d, procs = make([0, 0, 1, 1], script)
        f.record(1)
        ch = [c for c in procs[0].stdin.sent if c["cmd"] == "choose"]
        self.assertEqual(ch, [{"cmd": "choose", "index": 1}])
        lists = [a[1] for k, a, _ in d.log if k == "select"]
        self.assertEqual(len(lists[-1]), 3)  # two albums + "none of these"

    def test_manual_choice_none(self):
        cands = [{"index": 0, "artist": "X", "album": "Y", "year": None, "tracks": 9}]
        script = dict(FACE, finish=[{"event": "choose_release", "candidates": cands}],
                      choose=[{"event": "done", "album_dir": "/ok"}])
        f, d, procs = make([0, 0, 1, 1], script)
        f.record(1)
        self.assertEqual([c for c in procs[0].stdin.sent if c["cmd"] == "choose"],
                         [{"cmd": "choose", "index": None}])

    def test_faces_to_check_reported(self):
        script = dict(FACE, finish=[{"event": "done", "album_dir": "/a", "faces_to_check": ["B"],
                                     "warnings": ["raw recordings kept"]}])
        f, d, procs = make([0, 0, 1], script)
        f.record(1)
        msg = d.log[-1][1][1]
        self.assertIn("raw recordings kept", msg)
        self.assertIn("S30024", msg)

    def test_busy_guard(self):
        kodi_mock.WINDOW_PROPS["vinylrip.busy"] = "1"
        f, d, procs = make([0], {})
        f.record(1)
        self.assertEqual(procs, [])

    def test_multi_asks_number(self):
        f, d, procs = make([], {})
        d.answers = ["3", 1]
        f.record_multi()
        self.assertIn("3", procs[0].argv)

    def test_multi_invalid_number(self):
        f, d, procs = make([""], {})
        f.record_multi()
        self.assertEqual(procs, [])

    def test_quality_choice_saved(self):
        out = '{"cards": [{"id": "Device", "name": "Sony", "qualities": [{"key": "192000:S32_LE:2", "label": "192 kHz / 32 bits"}, {"key": "96000:S24_3LE:2", "label": "96 kHz / 24 bits"}]}]}'

        class R:
            returncode, stdout, stderr = 0, out, ""
        d = kodi_mock.FakeDialog([2])
        a = kodi_mock.FakeAddon()
        f = F.Flow(a, d, Engine("vinylrip", None, run=lambda *x, **k: R))
        f.choose_quality()
        self.assertEqual(a.settings["quality"], "96000:S24_3LE:2")
        d.answers = [0]
        f.choose_quality()
        self.assertEqual(a.settings["quality"], "")

    def test_listen_stops_engine(self):
        f, d, procs = make([0], {})
        f.listen()
        self.assertEqual(procs[0].argv[-1], "listen")


if __name__ == "__main__":
    unittest.main()
