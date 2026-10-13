# SPDX-License-Identifier: GPL-2.0-or-later
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import kodi_mock  # noqa: E402
from resources.lib import detect, settings_io  # noqa: E402

CARDS = """ 0 [PCH            ]: HDA-Intel - HDA Intel PCH
                      HDA Intel PCH at 0xf7e10000 irq 30
 1 [Device         ]: USB-Audio - Sony USB Audio
                      Sony Sony USB Audio at usb-0000:00:14.0-2, high speed
"""


class DetectTest(unittest.TestCase):
    def test_parse(self):
        c = detect.parse_cards(CARDS)
        self.assertEqual([x["id"] for x in c], ["PCH", "Device"])
        self.assertEqual(c[1]["driver"], "USB-Audio")
        self.assertIn("usb-0000", c[1]["detail"])

    def test_matching(self):
        c = detect.parse_cards(CARDS)
        self.assertEqual([x["id"] for x in detect.matching(c)], ["Device"])
        self.assertEqual([x["id"] for x in detect.matching(c, "pch")], ["PCH"])
        self.assertEqual(detect.matching(c, "nothing"), [])

    def test_unreadable(self):
        self.assertEqual(detect.read_cards("/nonexistent/cards"), [])
        self.assertEqual(detect.parse_cards(""), [])


class SettingsTest(unittest.TestCase):
    def test_toml(self):
        s = {"device": "Device", "template": 'a"b', "output_rate": "96000.0", "output_bits": "0",
             "delete_raw": "true", "embed_cover": "false", "music_root": "~/Musique"}
        t = settings_io.build_toml(lambda k: s.get(k, ""))
        self.assertIn('device = "Device"', t)
        self.assertIn('template = "a\\"b"', t)
        self.assertIn("output_rate = 96000", t)
        self.assertNotIn("output_bits", t)
        self.assertIn("delete_raw = true", t)
        self.assertIn("embed_cover = false", t)
        self.assertNotIn("~", t)
        self.assertNotIn("acoustid_key", t)

    def test_toml_parses_and_keys_known_to_engine(self):
        try:
            import tomllib
        except ModuleNotFoundError:
            self.skipTest("python < 3.11")
        s = {"device": "D", "identify_mode": "manual", "output_bits": "24", "delete_raw": "true"}
        data = tomllib.loads(settings_io.build_toml(lambda k: s.get(k, "")))
        self.assertEqual(data["identify_mode"], "manual")
        engine_src = os.environ.get("VINYLRIP_SRC")
        if engine_src:
            sys.path.insert(0, engine_src)
            from vinylrip.config import Settings
            import dataclasses
            known = {f.name for f in dataclasses.fields(Settings)}
            self.assertFalse(set(data) - known)
            full = settings_io.build_toml(lambda k: "x" if not k.startswith(("delete", "embed", "cover", "portable")) else "true")
            self.assertFalse(set(tomllib.loads(full)) - known)

    def test_write(self):
        with tempfile.TemporaryDirectory() as d:
            p = settings_io.write_config(os.path.join(d, "sub", "c.toml"), lambda k: "")
            self.assertTrue(os.path.exists(p))


class ServiceTest(unittest.TestCase):
    def setUp(self):
        import service
        self.service = service
        self.launched = 0

    def watcher(self, reads, settings=None, busy=False):
        it = iter(reads)
        w = self.service.Watcher(kodi_mock.FakeAddon(settings or {}), read=lambda: detect.parse_cards(next(it)),
                                 launch=lambda: setattr(self, "launched", self.launched + 1), busy=lambda: busy)
        return w

    def test_startup_and_hotplug(self):
        w = self.watcher([CARDS, CARDS, CARDS.split(" 1 [")[0], CARDS])
        self.assertTrue(w.tick())       # present at Kodi start
        self.assertFalse(w.tick())      # still there: no repeat
        self.assertFalse(w.tick())      # unplugged
        self.assertTrue(w.tick())       # plugged again
        self.assertEqual(self.launched, 2)

    def test_disabled_and_busy(self):
        w = self.watcher([CARDS], {"auto_popup": "false"})
        self.assertFalse(w.tick())
        w = self.watcher([CARDS], busy=True)
        self.assertFalse(w.tick())
        self.assertEqual(self.launched, 0)


class AddonTest(unittest.TestCase):
    def test_menu_and_actions(self):
        import addon
        from resources.lib import flow as F
        kodi_mock.DIRECTORY.clear()
        flow = F.Flow(kodi_mock.FakeAddon(), kodi_mock.FakeDialog(), object())
        addon.route(["plugin://plugin.audio.vinylrip/", "5", ""], flow)
        self.assertEqual([u.split("=")[1] for u, _ in kodi_mock.DIRECTORY],
                         ["record", "record_multi", "listen", "quality"])
        calls = []
        flow.main = lambda: calls.append("main")
        flow.record_multi = lambda: calls.append("multi")
        addon.route(["p/", "5", "?action=main"], flow)
        addon.route(["p/", "5", "?action=record_multi"], flow)
        self.assertEqual(calls, ["main", "multi"])

    def test_main_dialog_routes(self):
        from resources.lib import flow as F
        d = kodi_mock.FakeDialog([1])
        f = F.Flow(kodi_mock.FakeAddon(), d, object())
        called = []
        f.record_multi = lambda: called.append(1)
        f.main()
        self.assertEqual(called, [1])
        self.assertEqual(len(d.log[0][1][1]), 4)


class StringsTest(unittest.TestCase):
    def test_all_ids_in_both_languages_and_settings(self):
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ids = {}
        for lang in ("fr_fr", "en_gb"):
            with open(os.path.join(root, "resources", "language", "resource.language." + lang, "strings.po"), encoding="utf-8") as fh:
                ids[lang] = set(re.findall(r'msgctxt "#(\d+)"', fh.read()))
        self.assertEqual(ids["fr_fr"], ids["en_gb"])
        with open(os.path.join(root, "resources", "settings.xml"), encoding="utf-8") as fh:
            used = set(re.findall(r'label="(\d+)"', fh.read()))
        self.assertFalse(used - ids["fr_fr"])
        from resources.lib import flow as F
        for i in range(30000, 30029):
            self.assertIn(str(i), ids["fr_fr"])


if __name__ == "__main__":
    unittest.main()
