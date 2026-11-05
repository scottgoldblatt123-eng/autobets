"""Settled results. A market's result is booked once, when Betfair settles it (the market is CLOSED and one runner is the winner).
Day and week boundaries follow UK time. Commission is not modelled in practice mode."""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")


def uk_date(t: float) -> dt.date:
    return dt.datetime.fromtimestamp(t, UK).date()


class Ledger:
    def __init__(self, entries: list[dict] | None = None) -> None:
        self.entries: list[dict] = list(entries or [])

    def add(self, market_id: str, event: str, t: float, result: float, winner: str | None, staked: float = 0.0, parts: dict | None = None) -> bool:
        if any(e["market_id"] == market_id for e in self.entries):
            return False                                                # a market is only ever booked once
        self.entries.append({"market_id": market_id, "event": event, "t": t, "result": round(result, 2), "winner": winner, "staked": round(staked, 2), "parts": {k: round(v, 2) for k, v in (parts or {}).items()}})
        return True

    def _sum(self, since: dt.date, until: dt.date | None = None) -> float:
        return round(sum(e["result"] for e in self.entries if uk_date(e["t"]) >= since and (until is None or uk_date(e["t"]) <= until)), 2)

    def window(self, since: float, until: float | None = None) -> list[dict]:
        return [e for e in self.entries if e["t"] >= since and (until is None or e["t"] < until)]

    def periods(self, now: float) -> dict:
        d = uk_date(now)
        week_start = d - dt.timedelta(days=d.weekday())
        month = [e for e in self.entries if uk_date(e["t"]).replace(day=1) == d.replace(day=1)]
        wins = sum(1 for e in month if e["result"] > 0)
        staked = sum(e.get("staked", 0.0) for e in month)
        return {"today": self._sum(d, d), "week": self._sum(week_start), "month": round(sum(e["result"] for e in month), 2),
                "last7": self._sum(d - dt.timedelta(days=6)), "month_markets": len(month), "month_win_rate": round(100 * wins / len(month)) if month else None,
                "month_staked": round(staked, 2), "month_roi": round(100 * sum(e["result"] for e in month) / staked, 1) if staked > 0 else None}
