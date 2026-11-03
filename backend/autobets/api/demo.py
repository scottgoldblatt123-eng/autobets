"""Synthetic price feed for development, tests and screenshots. No network. Clearly fictional markets."""
from __future__ import annotations

import math
import random
import time

from .. import ticks
from ..domain import MarketBook, PriceLevel, SelectionBook

MARKETS = {
    "1.900001": {"name": "Match Odds", "event": "A. Player v B. Player", "competition": "WTA Demo Open", "sport": "tennis",
                 "runners": {"101": "A. Player", "102": "B. Player"}, "p": [0.58, 0.42], "in_play": True},
    "1.900002": {"name": "Match Odds", "event": "Riverside v Northgate", "competition": "Demo Premier League", "sport": "football",
                 "runners": {"201": "Riverside", "202": "Northgate", "203": "The Draw"}, "p": [0.46, 0.27, 0.27], "in_play": True},
    "1.900003": {"name": "Match Odds", "event": "C. Player v D. Player", "competition": "ATP Demo Cup", "sport": "tennis",
                 "runners": {"301": "C. Player", "302": "D. Player"}, "p": [0.35, 0.65], "in_play": False},
    "1.900004": {"name": "Over/Under 2.5 Goals", "event": "Eastbridge v Hillfield", "competition": "Demo Premier League", "sport": "football",
                 "runners": {"401": "Under 2.5 Goals", "402": "Over 2.5 Goals"}, "p": [0.52, 0.48], "in_play": False},
}


class DemoFeed:
    def __init__(self, seed: int = 7) -> None:
        self.t0 = time.time()
        self.seed = seed
        self.status: dict[str, str] = {}        # demo control: market_id -> OPEN | SUSPENDED | CLOSED
        self.in_play: dict[str, bool] = {}      # demo control: override a market's in-play flag

    def list_markets(self, sport: str = "tennis", **_):
        return [{"market_id": m, "name": v["name"], "event": v["event"], "competition": v["competition"], "start": None,
                 "runners": v["runners"], "in_play": v["in_play"]} for m, v in MARKETS.items() if v["sport"] == sport]

    def market_info(self, ids):
        return {m: {"market_id": m, **{k: v for k, v in MARKETS[m].items() if k != "p"}, "start": None} for m in ids if m in MARKETS}

    def _price(self, mid: str, i: int, now: float) -> float:
        base = MARKETS[mid]["p"][i]
        rng = random.Random(f"{self.seed}-{mid}-{i}-{int(now // 2)}")          # changes every 2 seconds
        wobble = 0.03 * math.sin(now / 17 + i * 2 + hash(mid) % 7) + rng.uniform(-0.006, 0.006)
        return max(1.02, min(900.0, 1 / max(0.02, min(0.97, base + wobble))))

    def get_books(self, ids, depth: bool = False):
        now = time.time()
        out = []
        for mid in ids:
            if mid not in MARKETS:
                continue
            b = MarketBook(mid, in_play=self.in_play.get(mid, MARKETS[mid]["in_play"]), status=self.status.get(mid, "OPEN"))
            for i, sid in enumerate(MARKETS[mid]["runners"]):
                ltp = ticks.nearest(self._price(mid, i, now))
                rng = random.Random(f"{mid}-{sid}-{int(now // 3)}")
                n = 8 if depth else 3
                backs = [PriceLevel(ticks.move(ltp, -k), round(rng.uniform(15, 900), 2)) for k in range(0, n)]
                lays = [PriceLevel(ticks.move(ltp, k + 1), round(rng.uniform(15, 900), 2)) for k in range(0, n)]
                traded = {ticks.move(ltp, k): round(rng.uniform(100, 5000) / (1 + abs(k)), 2) for k in range(-12, 13)} if depth else {}
                b.selections[sid] = SelectionBook(sid, backs, lays, ltp, traded)
            out.append(b)
        return out
