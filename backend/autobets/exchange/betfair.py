"""Betfair Exchange adapter. Read-only for now: prices and markets. Order placing is deliberately
not implemented until the safety suite and the live key are in place."""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from ..domain import MarketBook, Order, OrderRequest, OrderType, Persistence, PriceLevel, SelectionBook, Side, Status
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

    # ---- real orders: OFF unless trading_enabled is set explicitly ------------------------
    trading_enabled = False
    _PERSIST = {Persistence.CANCEL: "LAPSE", Persistence.KEEP: "PERSIST", Persistence.TAKE_SP: "MARKET_ON_CLOSE"}

    def enable_trading(self, confirm: str) -> None:
        """Real money. Only the live mode start-up calls this, and only with the exact confirmation phrase."""
        if confirm != "SEND-REAL-ORDERS":
            raise ExchangeError("real orders need the explicit confirmation phrase")
        self.trading_enabled = True

    def _require_trading(self) -> None:
        if not self.trading_enabled:
            raise ExchangeError("real order placing is switched off (practice mode never sends orders to Betfair)")

    @staticmethod
    def _status(o: dict) -> Status:
        matched, remaining = o.get("sizeMatched", 0) or 0, o.get("sizeRemaining", 0) or 0
        if o.get("status") == "EXECUTABLE":
            return Status.PARTIAL if matched > 0 else Status.UNMATCHED
        if remaining > 0 or (o.get("sizeCancelled") or 0) > 0 or (o.get("sizeLapsed") or 0) > 0:
            if matched > 0:
                return Status.MATCHED                    # the matched part stands; the rest was cancelled or lapsed
            return Status.LAPSED if (o.get("sizeLapsed") or 0) > 0 else Status.CANCELLED
        return Status.MATCHED

    def _to_order(self, o: dict) -> Order:
        ps = o.get("priceSize", {})
        req = OrderRequest(o["marketId"], str(o["selectionId"]), Side(o["side"]), ps.get("price", 0.0), ps.get("size", 0.0),
                           OrderType.LIMIT, {"LAPSE": Persistence.CANCEL, "PERSIST": Persistence.KEEP,
                                             "MARKET_ON_CLOSE": Persistence.TAKE_SP}.get(o.get("persistenceType"), Persistence.KEEP),
                           client_ref=o.get("customerOrderRef", ""))
        return Order(o["betId"], req, self._status(o), round(o.get("sizeMatched", 0) or 0, 2), o.get("averagePriceMatched", 0.0) or 0.0)

    def place_order(self, req: OrderRequest) -> Order:
        self._require_trading()
        if req.order_type is not OrderType.LIMIT:
            raise ExchangeError("only limit orders are sent to Betfair")
        if req.client_ref:
            existing = self.find_by_ref(req.client_ref)          # idempotent: never place the same reference twice
            if existing:
                return existing
        ins = {"selectionId": int(req.selection_id), "handicap": 0, "side": req.side.value, "orderType": "LIMIT",
               "limitOrder": {"size": round(req.size, 2), "price": req.price, "persistenceType": self._PERSIST[req.persistence]}}
        if req.client_ref:
            ins["customerOrderRef"] = req.client_ref[:32]
        res = self._call("placeOrders", {"marketId": req.market_id, "instructions": [ins], "customerRef": req.client_ref[:32]})
        rep = (res.get("instructionReports") or [{}])[0]
        if res.get("status") != "SUCCESS" or rep.get("status") != "SUCCESS":
            raise ExchangeError(f"placeOrders refused: {rep.get('errorCode') or res.get('errorCode') or res.get('status')}")
        matched = rep.get("sizeMatched", 0) or 0
        st = Status.MATCHED if matched >= req.size - 0.005 else Status.PARTIAL if matched > 0 else Status.UNMATCHED
        return Order(rep["betId"], req, st, round(matched, 2), rep.get("averagePriceMatched", 0.0) or 0.0)

    def cancel_order(self, order_id: str) -> Order:
        self._require_trading()
        cur = self.get_order(order_id)
        res = self._call("cancelOrders", {"marketId": cur.request.market_id, "instructions": [{"betId": order_id}]})
        rep = (res.get("instructionReports") or [{}])[0]
        if rep.get("status") != "SUCCESS":
            raise ExchangeError(f"cancelOrders refused: {rep.get('errorCode') or res.get('status')}")
        return self.get_order(order_id)

    def replace_order(self, order_id: str, new_price: float) -> Order:
        self._require_trading()
        cur = self.get_order(order_id)
        res = self._call("replaceOrders", {"marketId": cur.request.market_id, "instructions": [{"betId": order_id, "newPrice": new_price}]})
        rep = (res.get("instructionReports") or [{}])[0]
        if rep.get("status") != "SUCCESS":
            raise ExchangeError(f"replaceOrders refused: {rep.get('errorCode') or res.get('status')}")
        return self.get_order(rep["placeInstructionReport"]["betId"])

    def _current(self, **flt) -> list[dict]:
        out, start = [], 0
        while True:
            res = self._call("listCurrentOrders", {"orderProjection": "ALL", "fromRecord": start, **flt})
            out += res.get("currentOrders", [])
            if not res.get("moreAvailable"):
                return out
            start = len(out)

    def open_orders(self) -> list[Order]:
        return [self._to_order(o) for o in self._current()]

    def get_order(self, order_id: str) -> Order:
        rows = self._current(betIds=[order_id])
        if not rows:
            raise ExchangeError(f"unknown order {order_id}")
        return self._to_order(rows[0])

    def find_by_ref(self, client_ref: str):
        rows = self._current(customerOrderRefs=[client_ref[:32]])
        return self._to_order(rows[0]) if rows else None
