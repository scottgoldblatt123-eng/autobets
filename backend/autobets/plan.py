"""The Plan: which markets are being watched or traded, by which script, chosen by whom.
A plan row binds a script to one runner in one market. Rows follow the script by id, so renaming a script renames the Strategy column."""
from __future__ import annotations

import time

STATES = ("armed", "running", "done", "stopped", "watching")


class Plan:
    def __init__(self, rows: list[dict] | None = None, nxt: int = 1) -> None:
        self.rows: dict[str, dict] = {r["id"]: r for r in (rows or [])}
        self._next = nxt

    def export(self) -> dict:
        return {"rows": list(self.rows.values()), "next": self._next}

    @classmethod
    def load(cls, d: dict | None) -> "Plan":
        d = d or {}
        return cls(d.get("rows"), int(d.get("next", 1)))

    def add(self, market_id: str, selection_id: str, script_id: str | None, event: str, market_name: str, runner: str, added_by: str = "you",
            stake: float | None = None, day: str = "") -> dict:
        for r in self.rows.values():
            if r["market_id"] == market_id and r["script_id"] == script_id and r["selection_id"] == selection_id and r["state"] in ("armed", "running", "watching"):
                raise ValueError("that market already has this script in the Plan")
        rid = f"p{self._next}"
        self._next += 1
        row = {"id": rid, "market_id": market_id, "selection_id": selection_id, "script_id": script_id, "event": event, "market_name": market_name,
               "runner": runner, "added_by": added_by, "stake": stake, "state": "armed" if script_id else "watching", "fired": [], "orders": [],
               "note": "", "added": time.time(), "day": day}
        self.rows[rid] = row
        return row

    def get(self, rid: str) -> dict:
        if rid not in self.rows:
            raise KeyError(rid)
        return self.rows[rid]

    def remove(self, rid: str) -> dict:
        self.get(rid)
        return self.rows.pop(rid)

    def active(self) -> list[dict]:
        return [r for r in self.rows.values() if r["state"] in ("armed", "running") and r["script_id"]]

    def clashes(self) -> list[tuple[str, list[str]]]:
        """Markets where two or more live scripts act on the same market."""
        by: dict[str, list[str]] = {}
        for r in self.rows.values():
            if r["state"] in ("armed", "running") and r["script_id"]:
                by.setdefault(r["market_id"], []).append(r["id"])
        return [(m, ids) for m, ids in by.items() if len(ids) > 1]
