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
        return Engine.demo()
    if mode == "practice":
        from ..exchange.betfair import BetfairAdapter
        bf = BetfairAdapter.from_env_file(os.environ.get("AUTOBETS_BETFAIR_ENV", "/opt/autobets/secrets/betfair.env"))
        return Engine(bf, "practice", os.environ.get("AUTOBETS_JOURNAL", "/opt/autobets/data/journal.db"))
    raise SystemExit(f"unknown AUTOBETS_MODE {mode!r} (live mode is not built yet)")


class OrderIn(BaseModel):
    market_id: str
    selection_id: str
    side: str
    price: float
    size: float
    persistence: str = "KEEP"


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
    def state(ids: str = "", _=Depends(auth)):
        return engine.state([i for i in ids.split(",") if i])

    @app.post("/api/orders")
    def place(o: OrderIn, _=Depends(auth)):
        try:
            return engine.place(o.market_id, o.selection_id, o.side, o.price, o.size, o.persistence)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except RuntimeError as e:
            raise HTTPException(502, str(e))

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

    dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")
    return app
