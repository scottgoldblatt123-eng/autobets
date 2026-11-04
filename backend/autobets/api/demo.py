"""Synthetic price feed for development, tests and screenshots. No network. Clearly fictional markets."""
from __future__ import annotations

import math
import random
import time

from .. import ticks
from ..domain import MarketBook, PriceLevel, SelectionBook

EV1, EV2, EV3, EV4 = "e-9001", "e-9002", "e-9003", "e-9004"
MARKETS = {
    "1.900001": {"name": "Match Odds", "type": "MATCH_ODDS", "event": "A. Player v B. Player", "event_id": EV1, "competition": "WTA Demo Open", "sport": "tennis",
                 "runners": {"101": "A. Player", "102": "B. Player"}, "p": [0.58, 0.42], "in_play": True},
    "1.900002": {"name": "Match Odds", "type": "MATCH_ODDS", "event": "Riverside v Northgate", "event_id": EV2, "competition": "Demo Premier League", "sport": "football",
                 "runners": {"201": "Riverside", "202": "Northgate", "203": "The Draw"}, "p": [0.46, 0.27, 0.27], "in_play": True},
    "1.900003": {"name": "Match Odds", "type": "MATCH_ODDS", "event": "C. Player v D. Player", "event_id": EV3, "competition": "ATP Demo Cup", "sport": "tennis",
                 "runners": {"301": "C. Player", "302": "D. Player"}, "p": [0.35, 0.65], "in_play": False},
    "1.900005": {"name": "Match Odds", "type": "MATCH_ODDS", "event": "Eastbridge v Hillfield", "event_id": EV4, "competition": "Demo Premier League", "sport": "football",
                 "runners": {"601": "Eastbridge", "602": "Hillfield", "603": "The Draw"}, "p": [0.40, 0.33, 0.27], "in_play": False},
    "1.900004": {"name": "Over/Under 2.5 Goals", "type": "OVER_UNDER_25", "event": "Eastbridge v Hillfield", "event_id": EV4, "competition": "Demo Premier League", "sport": "football",
                 "runners": {"401": "Under 2.5 Goals", "402": "Over 2.5 Goals"}, "p": [0.52, 0.48], "in_play": False},
    "1.900006": {"name": "Half Time", "type": "HALF_TIME", "event": "Riverside v Northgate", "event_id": EV2, "competition": "Demo Premier League", "sport": "football",
                 "runners": {"701": "Riverside", "702": "Northgate", "703": "The Draw"}, "p": [0.34, 0.20, 0.46], "in_play": True},
    "1.900007": {"name": "Over/Under 2.5 Goals", "type": "OVER_UNDER_25", "event": "Riverside v Northgate", "event_id": EV2, "competition": "Demo Premier League", "sport": "football",
                 "runners": {"801": "Under 2.5 Goals", "802": "Over 2.5 Goals"}, "p": [0.49, 0.51], "in_play": True},
    "1.900008": {"name": "First Half Goals 1.5", "type": "FIRST_HALF_GOALS_15", "event": "Riverside v Northgate", "event_id": EV2, "competition": "Demo Premier League", "sport": "football",
                 "runners": {"811": "Under 1.5 Goals", "812": "Over 1.5 Goals"}, "p": [0.66, 0.34], "in_play": True},
    "1.900009": {"name": "Correct Score", "type": "CORRECT_SCORE", "event": "Riverside v Northgate", "event_id": EV2, "competition": "Demo Premier League", "sport": "football",
                 "runners": {"500": "0 - 0", "501": "1 - 0", "502": "0 - 1", "503": "1 - 1", "504": "2 - 0", "505": "0 - 2", "506": "2 - 1", "507": "1 - 2", "508": "2 - 2", "509": "3 - 0", "510": "0 - 3", "511": "3 - 1", "512": "1 - 3", "513": "Any Other Score"}, "p": [0.1, 0.12, 0.08, 0.11, 0.09, 0.05, 0.08, 0.06, 0.05, 0.04, 0.02, 0.04, 0.02, 0.04], "in_play": True},
    "1.900010": {"name": "Both teams to Score?", "type": "BOTH_TEAMS_TO_SCORE", "event": "Riverside v Northgate", "event_id": EV2, "competition": "Demo Premier League", "sport": "football",
                 "runners": {"821": "Yes", "822": "No"}, "p": [0.55, 0.45], "in_play": True},
}


class DemoFeed:
    def __init__(self, seed: int = 7) -> None:
        self.t0 = time.time()
        self.seed = seed
        self.status: dict[str, str] = {}        # demo control: market_id -> OPEN | SUSPENDED | CLOSED
        self.in_play: dict[str, bool] = {}      # demo control: override a market's in-play flag

    @staticmethod
    def _row(m, v):
        return {"market_id": m, "name": v["name"], "market_type": v["type"], "event": v["event"], "event_id": v["event_id"],
                "competition": v["competition"], "start": None, "runners": v["runners"], "in_play": v["in_play"]}

    def list_markets(self, sport: str = "tennis", **_):
        return [self._row(m, v) for m, v in MARKETS.items() if v["sport"] == sport and v["type"] == "MATCH_ODDS"]

    def event_markets(self, event_id: str, **_):
        return [self._row(m, v) for m, v in MARKETS.items() if v["event_id"] == event_id]

    def market_info(self, ids):
        return {m: {"market_id": m, "market_type": MARKETS[m]["type"], **{k: v for k, v in MARKETS[m].items() if k not in ("p", "type")}, "start": None} for m in ids if m in MARKETS}

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
