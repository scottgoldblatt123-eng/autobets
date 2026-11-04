"""AutoBets HTTP API (practice / demo). Bind to 127.0.0.1 and reach it through an SSH tunnel until HTTPS is set up.
Environment: AUTOBETS_MODE=demo|practice, AUTOBETS_TOKEN=<secret> (required unless demo), AUTOBETS_BETFAIR_ENV=<env file>."""
from __future__ import annotations

import hmac
import logging
import os
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..exchange.base import ExchangeError
from .engine import Engine

_applog = logging.getLogger("autobets")


def make_engine() -> Engine:
    mode = os.environ.get("AUTOBETS_MODE", "demo")
    if mode == "demo":
        e = Engine.demo(); e.start_background(); return e
    if mode == "practice":
        from ..exchange.betfair import BetfairAdapter
        bf = BetfairAdapter.from_env_file(os.environ.get("AUTOBETS_BETFAIR_ENV", "/opt/autobets/secrets/betfair.env"))
        e = Engine(bf, "practice", os.environ.get("AUTOBETS_JOURNAL", "/opt/autobets/data/journal.db"),
                   os.environ.get("AUTOBETS_PRICES_DB", "/opt/autobets/data/betfair_prices.db"),
                   os.environ.get("AUTOBETS_STATE", "/opt/autobets/data/state.json"))
        e.start_background()
        return e
    raise SystemExit(f"unknown AUTOBETS_MODE {mode!r} (live mode is not built yet)")


class DutchIn(BaseModel):
    market_id: str
    selection_ids: list[str]
    side: str = "BACK"
    total: float
    prices: dict[str, float] | None = None


class BookIn(BaseModel):
    market_id: str
    targets: dict[str, float]


class OrderIn(BaseModel):
    market_id: str
    selection_id: str
    side: str
    price: float
    size: float
    persistence: str = "KEEP"
    fok_s: float = 0
    offset: int = 0
    stop: int = 0


class EditIn(BaseModel):
    price: float | None = None
    size: float | None = None


class MarketTriggerIn(BaseModel):
    market_id: str
    level: float


class PersistIn(BaseModel):
    persistence: str
    market_ids: list[str] | None = None
    order_id: str | None = None


class TriggerIn(BaseModel):
    market_id: str
    selection_id: str
    price: float


def create_app(engine: Engine | None = None) -> FastAPI:
    engine = engine or make_engine()
    token = os.environ.get("AUTOBETS_TOKEN", "")
    if not token and engine.mode != "demo":
        raise SystemExit("AUTOBETS_TOKEN must be set outside demo mode")
    app = FastAPI(title="AutoBets")

    # Football data collector: only outside demo mode and only when a key is configured. It runs in a background thread
    # inside this process, so a deploy restart also restarts it (everything it does is safe to repeat).
    football = None
    try:
        if engine.mode != "demo" and os.environ.get("API_FOOTBALL_KEY"):
            from ..football.apifootball import ApiFootball
            from ..football.collector import Collector
            from ..football.store import FootballStore
            data = os.environ.get("AUTOBETS_DATA", "/opt/autobets/data")
            football = Collector(ApiFootball(store_dir=data + "/apifootball"), FootballStore(data + "/football.db"))
            threading.Thread(target=football.run_forever, name="football-collector", daemon=True).start()
    except Exception as e:      # a data collector must never stop the trading app from starting
        _applog.exception("football collector not started: %s", e)
        football = None

    @app.exception_handler(ExchangeError)
    async def exchange_error(_request, exc):          # exchange problems are shown to the user, not a bare 500
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=502, content={"detail": f"Exchange error: {exc}"})

    def auth(x_auth: str = Header(default="")):
        if token and not hmac.compare_digest(x_auth, token):
            raise HTTPException(401, "bad token")

    def _call(fn):
        try:
            return fn()
        except ValueError as e:
            raise HTTPException(422, str(e))
        except RuntimeError as e:
            raise HTTPException(502, str(e))

    tennis = None
    try:
        if engine.mode != "demo" and os.environ.get("API_TENNIS_KEY"):
            from ..tennis.apitennis import ApiTennis
            from ..tennis.collector import TennisCollector
            from ..tennis.livestore import TennisStore
            data = os.environ.get("AUTOBETS_DATA", "/opt/autobets/data")
            tennis = TennisCollector(ApiTennis(), TennisStore(data + "/tennis_api.db"))
            threading.Thread(target=tennis.run_forever, name="tennis-collector", daemon=True).start()
    except Exception as e:      # a data collector must never stop the trading app from starting
        _applog.exception("tennis collector not started: %s", e)
        tennis = None

    from ..context import MatchContext
    match_context = MatchContext(tennis.store if tennis else None, football.store if football else None)

    @app.get("/api/context")
    def context(ids: str = "", _=Depends(auth)):
        """Live score / clock / serve for the open markets, where the stored data matches them clearly."""
        wanted = [i for i in ids.split(",") if i][:12]
        info = engine.info(wanted) if wanted else {}
        return {i: c for i in wanted if i in info and (c := match_context.for_market(info[i]))}

    @app.get("/api/match_details")
    def match_details(market_id: str, _=Depends(auth)):
        """Rankings or league position, recent form and head-to-head for the match behind a market, where it can be matched."""
        info = engine.info([market_id]).get(market_id)
        out = match_context.details(info) if info else None
        return out or {"kind": None, "why": match_context.explain(info) if info else "market info unavailable"}

    @app.get("/api/tennis/status")
    def tennis_status(_=Depends(auth)):
        return tennis.status() if tennis else {"enabled": False}

    @app.get("/api/football/status")
    def football_status(_=Depends(auth)):
        return football.status() if football else {"enabled": False}

    @app.get("/api/mode")
    def mode(_=Depends(auth)):
        return {"mode": engine.mode, "needs_token": bool(token)}

    @app.get("/api/ping")
    def ping():
        return {"needs_token": bool(token), "mode": engine.mode}

    @app.get("/api/event_markets")
    def event_markets(event_id: str, _=Depends(auth)):
        """All the markets on one event, so the screen can offer half time, goal lines, correct score and the rest."""
        if not event_id:
            raise HTTPException(400, "event_id is required")
        return engine.event_markets(event_id)

    @app.get("/api/markets")
    def markets(sport: str = "tennis", _=Depends(auth)):
        if sport not in ("tennis", "football"):
            raise HTTPException(400, "sport must be tennis or football")
        return engine.markets(sport)

    @app.get("/api/state")
    def state(ids: str = "", short_s: int = 60, long_s: int = 300, _=Depends(auth)):
        return engine.state([i for i in ids.split(",") if i], short_s, long_s)

    @app.get("/api/busy")
    def busy(_=Depends(auth)):
        return engine.busy()

    @app.get("/api/history")
    def history(market_id: str, selection_id: str, seconds: int = 900, _=Depends(auth)):
        return engine.history(market_id, selection_id, max(60, min(seconds, 3 * 3600)))

    @app.post("/api/orders")
    def place(o: OrderIn, _=Depends(auth)):
        try:
            return engine.place(o.market_id, o.selection_id, o.side, o.price, o.size, o.persistence, o.fok_s, max(0, min(o.offset, 50)), max(0, min(o.stop, 50)))
        except ValueError as e:
            raise HTTPException(422, str(e))
        except RuntimeError as e:
            raise HTTPException(502, str(e))

    @app.patch("/api/orders/{order_id}")
    def edit(order_id: str, e: EditIn, _=Depends(auth)):
        try:
            return engine.edit_order(order_id, e.price, e.size)
        except ValueError as ex:
            raise HTTPException(422, str(ex))

    @app.post("/api/orders-persistence")
    def persistence(p: PersistIn, _=Depends(auth)):
        try:
            return {"changed": engine.set_persistence(p.persistence, p.market_ids, p.order_id)}
        except ValueError as ex:
            raise HTTPException(422, str(ex))

    @app.get("/api/log")
    def log(n: int = 100, _=Depends(auth)):
        return engine.activity(max(1, min(n, 300)))

    @app.post("/api/demo/status")
    def demo_status(market_id: str, status: str = "OPEN", in_play: bool | None = None, _=Depends(auth)):
        """Demo only: make a market suspended / closed / in play, to try the screen's handling of it."""
        if engine.mode != "demo":
            raise HTTPException(404, "demo mode only")
        engine.feed.status[market_id] = status.upper()
        if in_play is not None:
            engine.feed.in_play[market_id] = in_play
        return {"ok": True}

    @app.delete("/api/orders/{order_id}")
    def cancel(order_id: str, _=Depends(auth)):
        return engine.cancel(order_id)

    @app.post("/api/markets/{market_id}/cancel-all")
    def cancel_all(market_id: str, selection_id: str | None = None, side: str | None = None, _=Depends(auth)):
        return {"cancelled": engine.cancel_many(market_id, selection_id, side)}

    @app.post("/api/markets/{market_id}/close/{selection_id}")
    def close(market_id: str, selection_id: str, _=Depends(auth)):
        try:
            return engine.close_position(market_id, selection_id)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except RuntimeError as e:
            raise HTTPException(502, str(e))

    @app.post("/api/markets/{market_id}/green")
    def green(market_id: str, hard: bool = False, pct: float = 1.0, _=Depends(auth)):
        try:
            return engine.green_market(market_id, hard, max(0.05, min(pct, 1.0)))
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.post("/api/dutch/preview")
    def dutch_preview(b: DutchIn, _=Depends(auth)):
        return _call(lambda: engine.dutch_preview(b.market_id, b.selection_ids, b.side, b.total, b.prices))

    @app.post("/api/dutch")
    def dutch(b: DutchIn, _=Depends(auth)):
        return _call(lambda: engine.dutch_place(b.market_id, b.selection_ids, b.side, b.total, b.prices))

    @app.post("/api/book/preview")
    def book_preview(b: BookIn, _=Depends(auth)):
        return _call(lambda: engine.book_preview(b.market_id, b.targets))

    @app.post("/api/book")
    def book(b: BookIn, _=Depends(auth)):
        return _call(lambda: engine.book_place(b.market_id, b.targets))

    @app.post("/api/market-triggers")
    def add_market_trigger(t: MarketTriggerIn, _=Depends(auth)):
        try:
            return engine.add_market_trigger(t.market_id, t.level)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.delete("/api/market-triggers/{trigger_id}")
    def del_market_trigger(trigger_id: str, _=Depends(auth)):
        return {"cancelled": engine.cancel_market_trigger(trigger_id)}

    @app.post("/api/triggers")
    def add_trigger(t: TriggerIn, _=Depends(auth)):
        try:
            return engine.add_trigger(t.market_id, t.selection_id, t.price)
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.delete("/api/triggers/{trigger_id}")
    def del_trigger(trigger_id: str, _=Depends(auth)):
        return {"cancelled": engine.cancel_trigger(trigger_id)}

    dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    return app
