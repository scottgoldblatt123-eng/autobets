"""AutoBets HTTP API (practice / demo). Bind to 127.0.0.1 and reach it through an SSH tunnel until HTTPS is set up.
Environment: AUTOBETS_MODE=demo|practice, AUTOBETS_TOKEN=<secret> (required unless demo), AUTOBETS_BETFAIR_ENV=<env file>."""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..exchange.base import ExchangeError
from .engine import Engine


def make_engine() -> Engine:
    mode = os.environ.get("AUTOBETS_MODE", "demo")
    if mode == "demo":
        e = Engine.demo(); e.start_background(); return e
    if mode == "practice":
        from ..exchange.betfair import BetfairAdapter
        bf = BetfairAdapter.from_env_file(os.environ.get("AUTOBETS_BETFAIR_ENV", "/opt/autobets/secrets/betfair.env"))
        e = Engine(bf, "practice", os.environ.get("AUTOBETS_JOURNAL", "/opt/autobets/data/journal.db"),
                   os.environ.get("AUTOBETS_PRICES_DB", "/opt/autobets/data/betfair_prices.db"))
        e.start_background()
        return e
    raise SystemExit(f"unknown AUTOBETS_MODE {mode!r} (live mode is not built yet)")


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

    @app.exception_handler(ExchangeError)
    async def exchange_error(_request, exc):          # exchange problems are shown to the user, not a bare 500
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=502, content={"detail": f"Exchange error: {exc}"})

    def auth(x_auth: str = Header(default="")):
        if token and not hmac.compare_digest(x_auth, token):
            raise HTTPException(401, "bad token")

    @app.get("/api/mode")
    def mode(_=Depends(auth)):
        return {"mode": engine.mode, "needs_token": bool(token)}

    @app.get("/api/ping")
    def ping():
        return {"needs_token": bool(token), "mode": engine.mode}

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
