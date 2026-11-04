"""Betfair Exchange adapter. Read-only for now: prices and markets. Order placing is deliberately
not implemented until the safety suite and the live key are in place."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from ..domain import MarketBook, Order, OrderRequest, PriceLevel, SelectionBook
from .base import ExchangeAdapter, ExchangeError

API = "https://api.betfair.com/exchange/betting/rest/v1.0/"
CERT_LOGIN = "https://identitysso-cert.betfair.com/api/certlogin"


class HttpTransport:
    """Thin urllib wrapper so tests can substitute a fake."""

    def __init__(self, cert: str | None = None, key: str | None = None) -> None:
        self.ctx = None
        if cert and key:
            self.ctx = ssl.create_default_context()
            self.ctx.load_cert_chain(cert, key)

    def post(self, url: str, headers: dict, form: dict | None = None, body: dict | None = None):
        h = dict(headers)
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body or {}).encode()
            h["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=20, context=self.ctx) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read())
            except Exception:
                return e.code, {}


class BetfairAdapter(ExchangeAdapter):
    def __init__(self, app_key: str, username: str, password: str, transport=None) -> None:
        self.app_key, self.username, self.password = app_key, username, password
        self.http = transport or HttpTransport()
        self.token: str | None = None

    @classmethod
    def from_env_file(cls, path: str) -> "BetfairAdapter":
        env = {}
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        return cls(env["BETFAIR_APP_KEY"], env["BETFAIR_USERNAME"], env["BETFAIR_PASSWORD"],
                   HttpTransport(env.get("BETFAIR_CERT"), env.get("BETFAIR_KEY")))

    # ---- session -------------------------------------------------------
    def login(self) -> None:
        code, res = self.http.post(CERT_LOGIN, {"X-Application": self.app_key, "Accept": "application/json"},
                                   form={"username": self.username, "password": self.password})
        if res.get("loginStatus") != "SUCCESS":
            raise ExchangeError(f"login failed: {res.get('loginStatus') or res}")
        self.token = res["sessionToken"]

    def _call(self, op: str, body: dict, _retry: bool = True):
        if not self.token:
            self.login()
        code, res = self.http.post(API + op + "/", {"X-Application": self.app_key,
                                   "X-Authentication": self.token, "Accept": "application/json"}, body=body)
        if code == 200:
            return res
        text = json.dumps(res)
        if _retry and ("INVALID_SESSION_INFORMATION" in text or "NO_SESSION" in text):
            self.token = None
            return self._call(op, body, _retry=False)       # re-login once, then give up
        raise ExchangeError(f"{op} failed: HTTP {code} {text[:200]}")

    # ---- discovery -----------------------------------------------------
    @staticmethod
    def _cat(m: dict) -> dict:
        return {
            "market_id": m["marketId"], "name": m.get("marketName", ""), "start": m.get("marketStartTime"),
            "event": m.get("event", {}).get("name", ""), "event_id": m.get("event", {}).get("id", ""),
            "competition": m.get("competition", {}).get("name", ""),
            "market_type": (m.get("description") or {}).get("marketType", ""), "matched": m.get("totalMatched"),
            "runners": {str(r["selectionId"]): r["runnerName"] for r in sorted(m.get("runners", []), key=lambda r: r.get("sortPriority", 0))},
        }

    _PROJ = ["EVENT", "COMPETITION", "MARKET_START_TIME", "RUNNER_DESCRIPTION", "MARKET_DESCRIPTION"]

    def list_markets(self, event_type_id: str, market_type: str = "MATCH_ODDS", max_results: int = 50,
                     in_play_only: bool = False) -> list[dict]:
        flt = {"eventTypeIds": [event_type_id], "marketTypeCodes": [market_type]}
        if in_play_only:
            flt["inPlayOnly"] = True
        res = self._call("listMarketCatalogue", {"filter": flt, "maxResults": str(max_results),
                         "sort": "FIRST_TO_START", "marketProjection": self._PROJ})
        return [self._cat(m) for m in res]

    def event_markets(self, event_id: str, max_results: int = 100) -> list[dict]:
        """Every market Betfair offers on one event (match odds, half time, goal lines, correct score, ...)."""
        res = self._call("listMarketCatalogue", {"filter": {"eventIds": [event_id]}, "maxResults": str(max_results),
                         "sort": "FIRST_TO_START", "marketProjection": self._PROJ})
        return [self._cat(m) for m in res]

    # ---- ExchangeAdapter ----------------------------------------------
    def get_book(self, market_id: str) -> MarketBook:
        res = self._call("listMarketBook", {"marketIds": [market_id], "priceProjection":
                         {"priceData": ["EX_BEST_OFFERS", "EX_TRADED"]}})
        if not res:
            raise ExchangeError(f"unknown market {market_id}")
        return self.parse_book(res[0])

    def get_books(self, market_ids: list[str], depth: bool = False) -> list[MarketBook]:
        """Several markets in one call. Top-of-book by default (<= 40 markets per call: Betfair data-weight limit);
        depth=True adds all offers and traded volume for ladders (keep to <= 5 markets per call)."""
        data = ["EX_ALL_OFFERS", "EX_TRADED"] if depth else ["EX_BEST_OFFERS"]
        res = self._call("listMarketBook", {"marketIds": market_ids, "priceProjection": {"priceData": data}})
        return [self.parse_book(r) for r in res]

    def market_info(self, market_ids: list[str]) -> dict[str, dict]:
        res = self._call("listMarketCatalogue", {"filter": {"marketIds": market_ids}, "maxResults": str(len(market_ids)),
                         "marketProjection": self._PROJ})
        return {m["marketId"]: self._cat(m) for m in res}

    @staticmethod
    def parse_book(raw: dict) -> MarketBook:
        book = MarketBook(raw["marketId"], in_play=bool(raw.get("inplay")), status=raw.get("status", "OPEN"))
        for r in raw.get("runners", []):
            ex = r.get("ex", {})
            book.selections[str(r["selectionId"])] = SelectionBook(
                str(r["selectionId"]),
                backs=[PriceLevel(x["price"], x["size"]) for x in ex.get("availableToBack", [])],
                lays=[PriceLevel(x["price"], x["size"]) for x in ex.get("availableToLay", [])],
                last_traded=r.get("lastPriceTraded"),
                traded={x["price"]: x["size"] for x in ex.get("tradedVolume", [])},
                status=r.get("status", "ACTIVE"),
            )
        return book

    def _no_trading(self, *_a, **_k):
        raise ExchangeError("order placing is not enabled on the Betfair adapter yet (read-only)")

    place_order = cancel_order = replace_order = _no_trading

    def open_orders(self) -> list[Order]:
        return []

    def get_order(self, order_id: str) -> Order:
        raise ExchangeError("not available while read-only")

    def find_by_ref(self, client_ref: str):
        return None
