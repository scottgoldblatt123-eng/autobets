"""Write-ahead order journal. Every order is recorded BEFORE it is sent, so a crash or lost
response can always be reconciled against what the exchange actually holds."""
from __future__ import annotations

import sqlite3
import time

INTENT, SENT, CONFIRMED, FAILED, UNKNOWN = "INTENT", "SENT", "CONFIRMED", "FAILED", "UNKNOWN"


class Journal:
    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS orders(
            client_ref TEXT PRIMARY KEY, exchange_id TEXT, state TEXT NOT NULL,
            market_id TEXT, selection_id TEXT, side TEXT, price REAL, size REAL,
            source TEXT, note TEXT, at REAL)""")
        self.db.commit()

    def intent(self, ref, req) -> None:
        self.db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (ref, None, INTENT, req.market_id, req.selection_id, req.side.value,
                         req.price, req.size, req.source, "", time.time()))
        self.db.commit()

    def set_state(self, ref, state, exchange_id=None, note="") -> None:
        self.db.execute("UPDATE orders SET state=?, exchange_id=COALESCE(?,exchange_id), note=?, at=? WHERE client_ref=?",
                        (state, exchange_id, note, time.time(), ref))
        self.db.commit()

    def get(self, ref):
        row = self.db.execute("SELECT client_ref,exchange_id,state,source FROM orders WHERE client_ref=?", (ref,)).fetchone()
        return dict(zip(("client_ref", "exchange_id", "state", "source"), row)) if row else None

    def in_state(self, *states):
        q = ",".join("?" * len(states))
        return [r[0] for r in self.db.execute(f"SELECT client_ref FROM orders WHERE state IN ({q})", states)]
