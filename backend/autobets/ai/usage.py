"""Spend tracking for the AI layer. Costs are ESTIMATES from token counts and configurable rates; the Console's own spend limit is the
hard stop. This in-app cap (default £50 a month) refuses new requests once the estimate reaches it."""
from __future__ import annotations

import datetime as dt
import os
import sqlite3
import threading
import time


class Usage:
    def __init__(self, path: str = ":memory:") -> None:
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.execute("CREATE TABLE IF NOT EXISTS usage(t REAL, month TEXT, purpose TEXT, model TEXT, in_tok INT, out_tok INT, gbp REAL)")
            self.db.commit()
        self.usd_in = float(os.environ.get("AUTOBETS_AI_USD_PER_MTOK_IN", "3"))
        self.usd_out = float(os.environ.get("AUTOBETS_AI_USD_PER_MTOK_OUT", "15"))
        self.gbp_per_usd = float(os.environ.get("AUTOBETS_AI_GBP_PER_USD", "0.8"))
        self.cap = float(os.environ.get("AUTOBETS_AI_MONTHLY_GBP", "50"))

    @staticmethod
    def month(t: float | None = None) -> str:
        return dt.datetime.fromtimestamp(t or time.time(), dt.timezone.utc).strftime("%Y-%m")

    def cost(self, in_tok: int, out_tok: int) -> float:
        return (in_tok * self.usd_in + out_tok * self.usd_out) / 1e6 * self.gbp_per_usd

    def record(self, purpose: str, model: str, in_tok: int, out_tok: int) -> float:
        gbp = self.cost(in_tok, out_tok); t = time.time()
        with self.lock:
            self.db.execute("INSERT INTO usage VALUES(?,?,?,?,?,?,?)", (t, self.month(t), purpose, model, in_tok, out_tok, gbp)); self.db.commit()
        return gbp

    def month_gbp(self) -> float:
        with self.lock:
            return self.db.execute("SELECT COALESCE(SUM(gbp),0) FROM usage WHERE month=?", (self.month(),)).fetchone()[0]

    def allowed(self) -> bool:
        return self.month_gbp() < self.cap

    def status(self) -> dict:
        with self.lock:
            n, i, o = self.db.execute("SELECT COUNT(*), COALESCE(SUM(in_tok),0), COALESCE(SUM(out_tok),0) FROM usage WHERE month=?", (self.month(),)).fetchone()
        return {"month": self.month(), "requests": n, "input_tokens": i, "output_tokens": o, "estimated_gbp": round(self.month_gbp(), 2), "cap_gbp": self.cap}
