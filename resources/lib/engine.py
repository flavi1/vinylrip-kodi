# SPDX-License-Identifier: GPL-2.0-or-later
"""Thin wrapper around the ``vinylrip`` command-line engine (subprocess + JSON lines)."""
import json
import queue
import shlex
import subprocess
import threading


class EngineError(Exception):
    pass


class Session:
    """One ``vinylrip --json session`` process."""

    def __init__(self, proc):
        self.proc = proc
        self.events = queue.Queue()
        self.exit_code = None
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                self.events.put(json.loads(line))
            except ValueError:
                self.events.put({"event": "log", "message": line})
        self.exit_code = self.proc.wait()
        self.events.put({"event": "exit", "code": self.exit_code})

    def send(self, cmd, **kw):
        try:
            self.proc.stdin.write(json.dumps(dict(cmd=cmd, **kw)) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            raise EngineError("the engine is no longer running")

    def get(self, timeout=None):
        """Next event, or None on timeout."""
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            return None

    def wait_for(self, *names, timeout=None, on_other=None):
        """Wait for one of the named events. ``error``/``exit`` are always returned."""
        while True:
            ev = self.get(timeout)
            if ev is None:
                return None
            if ev.get("event") in names or ev.get("event") in ("error", "exit"):
                return ev
            if on_other:
                on_other(ev)

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=15)
        except Exception:
            self.proc.kill()
        self._thread.join(timeout=2)
        try:
            self.proc.stdout.close()
        except Exception:
            pass


class Engine:
    def __init__(self, binary="vinylrip", config_path=None, popen=subprocess.Popen, run=subprocess.run):
        self.binary, self.config_path = binary or "vinylrip", config_path
        self._popen, self._run = popen, run

    def _argv(self, *args):
        argv = shlex.split(self.binary)
        if self.config_path:
            argv += ["--config", self.config_path]
        return argv + ["--json"] + list(args)

    def devices(self, qualities=False):
        argv = self._argv("devices", *(["--qualities"] if qualities else []))
        try:
            out = self._run(argv, capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            raise EngineError("not found: " + self.binary)
        except subprocess.TimeoutExpired:
            raise EngineError("timeout while listing devices")
        if out.returncode != 0:
            raise EngineError((out.stderr or out.stdout).strip() or "devices failed")
        try:
            return json.loads(out.stdout)["cards"]
        except (ValueError, KeyError):
            raise EngineError("unreadable answer from the engine")

    def _spawn(self, *args):
        try:
            return self._popen(self._argv(*args), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
        except FileNotFoundError:
            raise EngineError("not found: " + self.binary)

    def session(self, device="", quality="", discs=1):
        args = ["session", "--discs", str(discs)]
        if device:
            args += ["--device", device]
        if quality:
            args += ["--quality", quality]
        return Session(self._spawn(*args))

    def listen(self, device="", quality=""):
        args = ["listen"]
        if device:
            args += ["--device", device]
        if quality:
            args += ["--quality", quality]
        return self._spawn(*args)
