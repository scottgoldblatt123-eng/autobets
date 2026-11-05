"""Alerts centre: things that happened or need a decision. Alerts with a `key` are not repeated while the same problem is still active."""
from __future__ import annotations

import time

TYPES = ("warning", "suspension", "info", "recommendation", "system", "trade")
# which filter chip each type belongs to
CHIP = {"warning": "warnings", "suspension": "suspensions", "trade": "trades", "info": "trades", "system": "system", "recommendation": "recommendations"}


class Alerts:
    def __init__(self, items: list[dict] | None = None, nxt: int = 1) -> None:
        self.items: list[dict] = list(items or [])
        self._next = nxt

    def export(self) -> dict:
        return {"items": self.items[-400:], "next": self._next}

    @classmethod
    def load(cls, d: dict | None) -> "Alerts":
        d = d or {}
        return cls(d.get("items"), int(d.get("next", 1)))

    def add(self, kind: str, text: str, action: str = "", needs_action: bool = False, ref: dict | None = None, key: str = "") -> dict | None:
        if kind not in TYPES:
            raise ValueError(f"unknown alert type {kind}")
        if key and any(a.get("key") == key and a["active"] for a in self.items):
            return None
        a = {"id": f"a{self._next}", "t": time.time(), "type": kind, "text": text, "action": action, "needs_action": needs_action, "ref": ref or {},
             "key": key, "active": bool(key) or needs_action, "read": False}
        self._next += 1
        self.items.append(a)
        del self.items[:-400]
        return a

    def resolve(self, key: str, note: str = "") -> None:
        for a in self.items:
            if a.get("key") == key and a["active"]:
                a["active"] = False
                if a["type"] in ("warning", "system"):
                    a["needs_action"] = False
                if note:
                    a["action"] = note

    def resolve_ref(self, kind: str, ref_id: str, note: str = "") -> None:
        for a in self.items:
            if a["ref"].get("kind") == kind and a["ref"].get("id") == ref_id and a["needs_action"]:
                a["needs_action"] = False
                a["active"] = False
                a["read"] = True
                if note:
                    a["action"] = note

    def mark_read(self, aid: str | None = None) -> int:
        n = 0
        for a in self.items:
            if (aid is None or a["id"] == aid) and not a["read"]:
                a["read"] = True
                n += 1
        return n

    def list(self, chip: str = "all", since: float = 0.0) -> list[dict]:
        out = [a for a in reversed(self.items) if a["t"] >= since]
        if chip == "needs_action":
            return [a for a in out if a["needs_action"]]
        if chip != "all":
            return [a for a in out if CHIP.get(a["type"]) == chip]
        return out

    def counts(self) -> dict:
        return {"needs_action": sum(1 for a in self.items if a["needs_action"]), "unread": sum(1 for a in self.items if not a["read"])}
