# SPDX-License-Identifier: GPL-2.0-or-later
"""Kodi settings -> the engine's TOML configuration file."""
import os


def _q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_toml(get):
    """``get(key)`` returns the Kodi setting as a string. Empty values are left to the engine's defaults."""
    out = []

    def s(key, name=None):
        v = get(key).strip()
        if v:
            out.append("%s = %s" % (name or key, _q(os.path.expanduser(v) if key.endswith("_dir") or key.endswith("_root") else v)))

    def b(key):
        out.append("%s = %s" % (key, "true" if get(key) == "true" else "false"))

    def n(key):
        v = get(key).strip()
        if v and v != "0":
            try:
                out.append("%s = %d" % (key, int(float(v))))
            except ValueError:
                pass

    s("device")
    s("quality")
    s("listen_device")
    s("identify_mode")
    s("acoustid_key")
    s("contact")
    s("music_root")
    s("masters_root")
    s("template")
    s("multidisc_template")
    n("output_rate")
    n("output_bits")
    for k in ("delete_raw", "delete_master_after_reduce", "embed_cover", "cover_file", "portable_names"):
        b(k)
    return "\n".join(out) + "\n"


def write_config(path, get):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(build_toml(get))
    os.replace(tmp, path)
    return path
