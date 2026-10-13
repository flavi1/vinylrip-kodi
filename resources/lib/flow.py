# SPDX-License-Identifier: GPL-2.0-or-later
"""The dialogs: record a disc, listen, choose quality. Every choice is a ``Dialog().select``."""
import os

import xbmc  # noqa: F401
import xbmcaddon
import xbmcgui
import xbmcvfs

from . import detect, settings_io
from .engine import Engine, EngineError

ADDON_ID = "plugin.audio.vinylrip"
BUSY = "vinylrip.busy"

# string ids
(S_TITLE, S_RECORD, S_RECORD_MULTI, S_LISTEN, S_QUALITY, S_CANCEL, S_DISCS, S_START_FACE,
 S_END_FACE, S_LISTEN_REC, S_STOP_LISTEN, S_NEXT_FACE, S_DISC_DONE, S_DELETE_Q, S_DETECTED,
 S_WHAT, S_ERROR, S_MANUAL, S_CHOOSE_ALBUM, S_NONE_OF, S_DONE, S_NO_TURNTABLE, S_PROCESSING,
 S_NO_ENGINE, S_TO_CHECK, S_BEST, S_LISTENING, S_YES, S_NO) = range(30000, 30029)


class Flow:
    def __init__(self, addon=None, dialog=None, engine=None):
        self.addon = addon or xbmcaddon.Addon()
        self.dialog = dialog or xbmcgui.Dialog()
        self._engine = engine

    # -- helpers -------------------------------------------------------------------
    def t(self, sid, *args):
        text = self.addon.getLocalizedString(sid)
        return text.format(*args) if args else text

    def setting(self, key):
        return self.addon.getSetting(key)

    def engine(self):
        if self._engine is None:
            profile = xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
            cfg = settings_io.write_config(os.path.join(profile, "vinylrip.toml"), self.setting)
            self._engine = Engine(self.setting("engine_path") or "vinylrip", cfg)
        return self._engine

    def error(self, message, kept=None):
        lines = [str(message)]
        if kept:
            lines.append(self.t(S_MANUAL, kept))
        self.dialog.ok(self.t(S_ERROR), "\n".join(lines))

    def find_turntable(self):
        cards = detect.matching(detect.read_cards(), self.setting("device"))
        return cards[0] if cards else None

    # -- main popup (also opened by the service) ------------------------------------------
    def main(self):
        card = self.find_turntable()
        head = self.t(S_DETECTED, card["name"]) if card else self.t(S_NO_TURNTABLE)
        items = [self.t(S_RECORD), self.t(S_RECORD_MULTI), self.t(S_LISTEN), self.t(S_CANCEL)]
        i = self.dialog.select("%s - %s" % (self.t(S_TITLE), head), items)
        if i == 0:
            self.record(1)
        elif i == 1:
            self.record_multi()
        elif i == 2:
            self.listen()

    def record_multi(self):
        n = self.dialog.numeric(0, self.t(S_DISCS), "2")
        try:
            discs = int(n)
        except (TypeError, ValueError):
            return
        if discs >= 1:
            self.record(discs)

    # -- recording ---------------------------------------------------------------------------
    def record(self, discs=1):
        win = xbmcgui.Window(10000)
        if win.getProperty(BUSY) == "1":
            return
        win.setProperty(BUSY, "1")
        try:
            self._record(discs)
        finally:
            win.clearProperty(BUSY)

    def _record(self, discs):
        try:
            sess = self.engine().session(self.setting("device"), self.setting("quality"), discs)
        except EngineError as exc:
            self.error(self.t(S_NO_ENGINE, exc))
            return
        try:
            ev = sess.wait_for("ready", timeout=60)
            if not ev or ev.get("event") != "ready":
                self.error((ev or {}).get("message", "engine did not start"), (ev or {}).get("kept"))
                return
            face_no = 0
            while True:
                label = "ABCDEFGH"[face_no]
                i = self.dialog.select(self.t(S_TITLE), [self.t(S_START_FACE, label), self.t(S_CANCEL)])
                if i != 0:
                    return self._cancel(sess)
                sess.send("start_face")
                ev = sess.wait_for("recording", timeout=30)
                if not ev or ev.get("event") != "recording":
                    return self.error((ev or {}).get("message", "recording did not start"), (ev or {}).get("kept"))
                if not self._during_face(sess, label):
                    return
                face_no += 1
                items = [self.t(S_NEXT_FACE), self.t(S_DISC_DONE), self.t(S_CANCEL)]
                if face_no >= len("ABCDEFGH"):
                    items = items[1:]
                i = self.dialog.select(self.t(S_TITLE), items)
                if face_no >= len("ABCDEFGH") and i >= 0:
                    i += 1
                if i == 0:
                    continue
                if i == 1:
                    break
                return self._cancel(sess)
            self._finish(sess)
        finally:
            sess.close()

    def _during_face(self, sess, label):
        """Modal loop while a face records. Returns True when the face was kept."""
        listening = False
        while True:
            items = [self.t(S_END_FACE, label),
                     self.t(S_STOP_LISTEN) if listening else self.t(S_LISTEN_REC),
                     self.t(S_CANCEL)]
            i = self.dialog.select(self.t(S_TITLE), items)
            if i == 1:
                sess.send("listen", on=not listening)
                ev = sess.wait_for("listening", timeout=15)
                if ev and ev.get("event") == "listening":
                    listening = ev.get("on", False)
                elif ev:
                    self.error(ev.get("message", "?"), ev.get("kept"))
                continue
            if i == 0:
                sess.send("stop_face")
                ev = sess.wait_for("face_done", timeout=60)
                if not ev or ev.get("event") != "face_done":
                    self.error((ev or {}).get("message", "?"), (ev or {}).get("kept"))
                    return False
                if ev.get("overruns"):
                    self.dialog.notification(self.t(S_TITLE), "overruns: %d" % ev["overruns"])
                return True
            # Cancel button, Escape/back (-1): ask, never lose the recording silently
            self._cancel(sess)
            return False

    def _cancel(self, sess):
        delete = self.dialog.yesno(self.t(S_TITLE), self.t(S_DELETE_Q), nolabel=self.t(S_NO), yeslabel=self.t(S_YES))
        sess.send("cancel", delete=bool(delete))
        sess.wait_for("cancelled", timeout=30)

    def _finish(self, sess):
        bg = xbmcgui.DialogProgressBG()
        bg.create(self.t(S_TITLE), self.t(S_PROCESSING))

        def on_other(ev):
            if ev.get("event") == "choose_release":
                self._choose(sess, ev["candidates"])
            elif ev.get("event") == "stage":
                bg.update(0, self.t(S_TITLE), str(ev.get("stage", "")))
        try:
            sess.send("finish")
            while True:
                ev = sess.wait_for("done", on_other=on_other)
                if ev.get("event") == "choose_release":
                    self._choose(sess, ev["candidates"])
                    continue
                break
        except EngineError as exc:
            ev = {"event": "error", "message": str(exc)}
        finally:
            bg.close()
        if ev.get("event") == "done":
            msg = [self.t(S_DONE, ev.get("album_dir", ""))]
            for w in ev.get("warnings", []):
                msg.append(w)
            if ev.get("faces_to_check"):
                msg.append(self.t(S_TO_CHECK, ", ".join(ev["faces_to_check"])))
            self.dialog.ok(self.t(S_TITLE), "\n".join(msg))
        else:
            self.error(ev.get("message", "engine stopped (code %s)" % ev.get("code")), ev.get("kept"))

    def _choose(self, sess, candidates):
        labels = ["%s - %s (%s, %d)" % (c["artist"], c["album"], c.get("year") or "?", c.get("tracks", 0))
                  for c in candidates] + [self.t(S_NONE_OF)]
        i = self.dialog.select(self.t(S_CHOOSE_ALBUM), labels)
        sess.send("choose", index=i if 0 <= i < len(candidates) else None)

    # -- listen / quality ---------------------------------------------------------------------------
    def listen(self):
        try:
            proc = self.engine().listen(self.setting("device"), self.setting("quality"))
        except EngineError as exc:
            return self.error(self.t(S_NO_ENGINE, exc))
        try:
            self.dialog.select(self.t(S_LISTENING), [self.t(S_STOP_LISTEN)])
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()

    def choose_quality(self):
        try:
            cards = self.engine().devices(qualities=True)
        except EngineError as exc:
            return self.error(exc)
        wanted = self.setting("device")
        pool = [c for c in cards if not wanted or wanted.lower() in (c["id"] + c["name"]).lower()] or cards
        if not pool or not pool[0].get("qualities"):
            return self.error(self.t(S_NO_TURNTABLE))
        qs = pool[0]["qualities"]
        i = self.dialog.select(self.t(S_QUALITY), [self.t(S_BEST)] + [q["label"] for q in qs])
        if i == 0:
            self.addon.setSetting("quality", "")
        elif i > 0:
            self.addon.setSetting("quality", qs[i - 1]["key"])
