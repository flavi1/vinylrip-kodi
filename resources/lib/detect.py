# SPDX-License-Identifier: GPL-2.0-or-later
"""Turntable detection from /proc/asound/cards (cheap enough to poll)."""
import re

_HEAD = re.compile(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s*(\S+)\s+-\s+(.*)$")


def parse_cards(text):
    """-> list of dicts(index, id, driver, name, detail)."""
    cards, lines = [], text.splitlines()
    for i, line in enumerate(lines):
        m = _HEAD.match(line)
        if m:
            detail = lines[i + 1].strip() if i + 1 < len(lines) else ""
            cards.append({"index": int(m.group(1)), "id": m.group(2), "driver": m.group(3),
                          "name": m.group(4).strip(), "detail": detail})
    return cards


def read_cards(path="/proc/asound/cards"):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return parse_cards(fh.read())
    except OSError:
        return []


def matching(cards, wanted=""):
    """Cards that look like the turntable: the configured one, or any USB audio card."""
    wanted = (wanted or "").strip().lower()
    if wanted:
        return [c for c in cards if wanted in c["id"].lower() or wanted in c["name"].lower()
                or wanted in c["detail"].lower()]
    return [c for c in cards if "usb" in c["driver"].lower()]


def new_ones(previous_ids, found):
    return [c for c in found if c["id"] not in previous_ids]
