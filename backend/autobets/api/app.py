"""AutoBets HTTP API (practice / demo). Bind to 127.0.0.1 and reach it through an SSH tunnel until HTTPS is set up.
Environment: AUTOBETS_MODE=demo|practice, AUTOBETS_TOKEN=<secret> (required unless demo), AUTOBETS_BETFAIR_ENV=<env file>."""
from __future__ import annotations

import hmac
import logging
import os
import re
import time
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
    if mode == "live":
        if os.environ.get("AUTOBETS_LIVE_CONFIRM") != "SEND-REAL-ORDERS":
            raise SystemExit("live mode needs AUTOBETS_LIVE_CONFIRM=SEND-REAL-ORDERS in the service environment (real money)")
        from ..exchange.betfair import BetfairAdapter
        from ..exchange.live import LiveExchange
        data = os.environ.get("AUTOBETS_DATA", "/opt/autobets/data")
        bf = BetfairAdapter.from_env_file(os.environ.get("AUTOBETS_BETFAIR_ENV", "/opt/autobets/secrets/betfair.env"))
        e = Engine(bf, "live", os.environ.get("AUTOBETS_JOURNAL", data + "/live_journal.db"),
                   os.environ.get("AUTOBETS_PRICES_DB", data + "/betfair_prices.db"),
                   os.environ.get("AUTOBETS_STATE", data + "/live_state.json"), exchange=LiveExchange(bf))   # separate files: practice history never mixes with real
        e.start_background()
        return e
    raise SystemExit(f"unknown AUTOBETS_MODE {mode!r} (use demo, practice or live)")


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
    engine.context_fn = match_context.for_market

    pricelog = None
    try:
        if engine.mode != "demo" and os.environ.get("AUTOBETS_PRICELOG", "1") != "0":
            from ..pricelog import PriceLogger, PriceStore
            data = os.environ.get("AUTOBETS_DATA", "/opt/autobets/data")
            pricelog = PriceLogger(engine, match_context, PriceStore(data + "/prices.db"))
            threading.Thread(target=pricelog.run_forever, name="price-logger", daemon=True).start()
    except Exception as e:      # the logger must never stop the trading app from starting
        _applog.exception("price logger not started: %s", e)
        pricelog = None

    @app.get("/api/pricelog/status")
    def pricelog_status(_=Depends(auth)):
        return pricelog.status() if pricelog else {"enabled": False}

    from ..ai.claude import AiError, Claude
    from ..ai.copilot import Copilot
    from ..ai.usage import Usage
    ai_usage = Usage((os.environ.get("AUTOBETS_DATA", "/opt/autobets/data") + "/ai.db") if engine.mode != "demo" else ":memory:")
    from ..ai.proposals import ProposalBook
    copilot = Copilot(Claude(), ai_usage, ProposalBook(float(os.environ.get("AUTOBETS_AI_MAX_STAKE", "10"))))

    def _sync_ai() -> None:
        copilot.proposals.max_stake = engine.settings.ai_max_stake
        ai_usage.cap = engine.settings.ai_monthly_cap
    _sync_ai()

    from ..ai.scriptbuilder import draft as ai_draft
    from ..scripts import ScriptError

    def _script_call(fn):
        try:
            return fn()
        except ScriptError as e:
            raise HTTPException(422, str(e))
        except KeyError:
            raise HTTPException(404, "unknown script")

    @app.get("/api/scripts")
    def scripts_list(_=Depends(auth)):
        return engine.scripts.list()

    @app.post("/api/scripts")
    def scripts_create(body: dict, _=Depends(auth)):
        origin = "ai" if body.pop("_origin", "") == "ai" else "you"
        return _script_call(lambda: engine.update_locked(lambda: engine.scripts.create(body, origin, "drafted by Claude" if origin == "ai" else "created")))

    @app.put("/api/scripts/{sid}")
    def scripts_update(sid: str, body: dict, _=Depends(auth)):
        return _script_call(lambda: engine.update_locked(lambda: engine.scripts.update(sid, body)))

    @app.post("/api/scripts/{sid}/enable")
    def scripts_enable(sid: str, body: dict, _=Depends(auth)):
        return _script_call(lambda: engine.update_locked(lambda: engine.scripts.set_enabled(sid, bool(body.get("on")))))

    @app.post("/api/scripts/{sid}/clone")
    def scripts_clone(sid: str, body: dict, _=Depends(auth)):
        return _script_call(lambda: engine.update_locked(lambda: engine.scripts.clone(sid, str(body.get("name", "")))))

    @app.delete("/api/scripts/{sid}")
    def scripts_delete(sid: str, _=Depends(auth)):
        def go():
            if any(r["script_id"] == sid and r["state"] in ("armed", "running") for r in engine.plan.rows.values()):
                raise ScriptError("this script is in use on the Plan; remove it there first")
            engine.scripts.delete(sid)
            return {"deleted": sid}
        return _script_call(lambda: engine.update_locked(go))

    @app.post("/api/scripts/build")
    def scripts_build(body: dict, _=Depends(auth)):
        try:
            return ai_draft(copilot.claude, ai_usage, str(body.get("prompt", "")))
        except AiError as e:
            raise HTTPException(502, str(e))

    @app.get("/api/plan")
    def plan_get(_=Depends(auth)):
        return engine.plan_view()

    @app.post("/api/plan")
    def plan_add(body: dict, _=Depends(auth)):
        try:
            return engine.plan_add(str(body.get("market_id", "")), body.get("selection_id"), body.get("script_id"), body.get("stake"), "ai" if body.get("added_by") == "ai" else "you")
        except (ValueError, KeyError) as e:
            raise HTTPException(422, str(e))

    @app.patch("/api/plan/{rid}")
    def plan_edit(rid: str, body: dict, _=Depends(auth)):
        try:
            return engine.plan_edit(rid, body.get("stake"), body.get("script_id"))
        except KeyError:
            raise HTTPException(404, "unknown plan row")
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.delete("/api/plan/{rid}")
    def plan_remove(rid: str, _=Depends(auth)):
        try:
            return engine.plan_remove(rid)
        except KeyError:
            raise HTTPException(404, "unknown plan row")

    @app.get("/api/plan/bets")
    def plan_bets(status: str = "", _=Depends(auth)):
        return engine.plan_bets([x for x in status.split(",") if x])

    from .. import health as health_mod

    def _statuses():
        return (football.status() if football else None, tennis.status() if tennis else None, pricelog.status() if pricelog else None)

    from .. import backup as backup_mod
    data_dir = os.environ.get("AUTOBETS_DATA", "/opt/autobets/data")
    backups = None
    if engine.mode != "demo" and os.path.isdir(data_dir) and os.environ.get("AUTOBETS_BACKUPS", "1") != "0":
        backups = backup_mod.Backups(data_dir)
        backups.start()

    def _server() -> dict | None:
        if engine.mode == "demo" or not os.path.isdir(data_dir):
            return None
        try:
            return {"disk": backup_mod.disk(data_dir), "db_mb": backup_mod.folder_mb(data_dir), "backup": backups.status() if backups else None}
        except OSError:
            return None

    def _health() -> dict:
        fb, tn, pl = _statuses()
        return health_mod.build(engine, fb, tn, pl, copilot.claude.enabled, {"estimated_gbp": ai_usage.status().get("estimated_gbp"), "cap_gbp": ai_usage.cap}, _server())

    @app.get("/api/health")
    def health(_=Depends(auth)):
        return _health()

    def _monitor() -> None:
        """Background upkeep: raise or clear health alerts, and look for recommendation ideas."""
        n = 0
        while True:
            time.sleep(60)
            n += 1
            try:
                for i in _health()["items"]:
                    if i["level"] == "bad":
                        engine.alerts.add("system" if i["key"] != "betfair" else "warning", f"{i['name']}: {i['detail']}", "Features that depend on it may act on old data", True, key="health:" + i["key"])
                    else:
                        engine.alerts.resolve("health:" + i["key"], "Recovered")
                if n % 2 == 0:
                    engine.rec_scan()
            except Exception:       # noqa: BLE001
                _applog.exception("monitor pass failed")
    if engine.mode != "demo":
        threading.Thread(target=_monitor, name="monitor", daemon=True).start()

    engine.price_store = pricelog.store if pricelog else None

    from .. import analyse, backtest as bt

    @app.get("/api/analyse/performance")
    def an_perf(days: int = 30, _=Depends(auth)):
        return analyse.performance(engine.ledger, engine.recs, ai_usage.month_gbp(), max(1, min(days, 365)))

    @app.get("/api/analyse/models")
    def an_models(_=Depends(auth)):
        return analyse.models(engine.price_store)

    @app.get("/api/analyse/ai")
    def an_ai(_=Depends(auth)):
        return analyse.ai_learning(engine.recs)

    @app.get("/api/backtests")
    def bt_list(_=Depends(auth)):
        return {"items": [{k: v for k, v in r.items() if k != "trade_list"} for r in reversed(engine.backtests)],
                "data": engine.price_store.counts() if engine.price_store else None}

    @app.get("/api/backtests/{bid}")
    def bt_get(bid: str, _=Depends(auth)):
        r = next((x for x in engine.backtests if x["id"] == bid), None)
        if r is None:
            raise HTTPException(404, "unknown backtest")
        return r

    @app.post("/api/backtests")
    def bt_run(body: dict, _=Depends(auth)):
        if engine.price_store is None:
            raise HTTPException(422, "There is no recorded price data to test on: the Betfair price log is not running.")
        try:
            sc = engine.scripts.current(str(body.get("script_id", "")))
        except KeyError:
            raise HTTPException(404, "unknown script")
        target = body.get("target", "favourite")
        if target not in bt.TARGETS:
            raise HTTPException(422, f"target must be one of {bt.TARGETS}")
        days = max(1, min(int(body.get("days", 90)), 3650))
        markets = bt.load(engine.price_store, sc["sport"], time.time() - days * 86400)
        res = bt.run(sc, markets, target, body.get("stake"), 0.05, float(body.get("oos", 0.3)))
        res.update(id=f"b{int(time.time() * 1000)}", t=time.time(), script_id=body["script_id"], version=len(engine.scripts.get(body["script_id"])["versions"]), days=days)
        res["data"] = engine.price_store.counts()
        engine.update_locked(lambda: engine.backtests.append(res))
        engine.backtests[:] = engine.backtests[-10:]
        return res

    @app.get("/api/live")
    def live_status(_=Depends(auth)):
        return engine.live_status()

    @app.post("/api/live/arm")
    def live_arm(body: dict, _=Depends(auth)):
        try:
            return engine.live_arm(str(body.get("confirm", "")))
        except (ValueError, ExchangeError) as e:
            raise HTTPException(400, str(e))

    @app.post("/api/live/disarm")
    def live_disarm(_=Depends(auth)):
        try:
            return engine.live_disarm()
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/credentials")
    def credentials(_=Depends(auth)):
        """Which secrets the server has. Only yes/no: values are never sent to the browser."""
        bf = os.environ.get("AUTOBETS_BETFAIR_ENV", "/opt/autobets/secrets/betfair.env")
        return {"items": [
            {"name": "Betfair", "set": engine.mode == "demo" or os.path.exists(bf), "detail": "delayed application key" if engine.mode != "demo" else "demo mode needs none"},
            {"name": "API-Football", "set": bool(os.environ.get("API_FOOTBALL_KEY")), "detail": "football fixtures, live scores, line-ups"},
            {"name": "api-tennis", "set": bool(os.environ.get("API_TENNIS_KEY")), "detail": "tennis matches, live scores, statistics"},
            {"name": "Anthropic (Claude)", "set": bool(os.environ.get("ANTHROPIC_API_KEY")), "detail": f"model {copilot.claude.model}"},
            {"name": "App access token", "set": bool(os.environ.get("AUTOBETS_TOKEN")), "detail": "protects this app"}],
            "where": "Keys live on the server only (/opt/autobets/secrets). To change one, edit the file there and restart the service."}

    @app.get("/api/home")
    def home(_=Depends(auth)):
        return engine.home()

    @app.get("/api/recs")
    def recs_list(kind: str = "all", status: str = "pending", _=Depends(auth)):
        return {"items": engine.recs.list(kind, status), "stats": engine.recs.stats(time.time() - 30 * 86400)}

    @app.post("/api/recs/{rid}/apply")
    def recs_apply(rid: str, body: dict | None = None, _=Depends(auth)):
        b = body or {}
        try:
            return engine.rec_apply(rid, b.get("price"), b.get("stake"))
        except KeyError:
            raise HTTPException(404, "unknown recommendation")
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.post("/api/recs/{rid}/dismiss")
    def recs_dismiss(rid: str, body: dict | None = None, _=Depends(auth)):
        try:
            return engine.rec_dismiss(rid, str((body or {}).get("reason", "")))
        except KeyError:
            raise HTTPException(404, "unknown recommendation")

    @app.post("/api/recs/scan")
    def recs_scan(_=Depends(auth)):
        return {"created": engine.rec_scan()}

    @app.get("/api/alerts")
    def alerts_list(chip: str = "all", days: int = 30, _=Depends(auth)):
        return {"items": engine.alerts.list(chip, time.time() - max(1, min(days, 365)) * 86400), "counts": {**engine.alerts.counts(), "recs": engine.recs.stats()["pending"]}}

    @app.post("/api/alerts/read")
    def alerts_read(body: dict | None = None, _=Depends(auth)):
        return {"marked": engine.alerts.mark_read((body or {}).get("id"))}

    @app.post("/api/alerts/{aid}/resume")
    def alerts_resume(aid: str, _=Depends(auth)):
        a = next((x for x in engine.alerts.items if x["id"] == aid), None)
        if a is None:
            raise HTTPException(404, "unknown alert")
        engine.alerts.resolve(a["key"] or "", "Dismissed by you") if a["key"] else None
        a["needs_action"], a["read"], a["active"] = False, True, False
        return a

    @app.get("/api/settings")
    def get_settings(_=Depends(auth)):
        return engine.settings.to_dict()

    @app.put("/api/settings")
    def put_settings(body: dict, _=Depends(auth)):
        try:
            out = engine.update_settings(body)
        except ValueError as e:
            raise HTTPException(422, str(e))
        _sync_ai()
        return out

    @app.post("/api/automation/stop")
    def stop_automation(_=Depends(auth)):
        return engine.stop_automation()

    @app.get("/api/pnl")
    def pnl_summary(_=Depends(auth)):
        return engine.pnl_summary()

    @app.get("/api/ai/status")
    def ai_status(_=Depends(auth)):
        return {"enabled": copilot.claude.enabled, "model": copilot.claude.model, **ai_usage.status()}

    @app.post("/api/ai/proposals/{pid}/approve")
    def ai_approve(pid: str, _=Depends(auth)):
        """Place an approved copilot proposal as an 'ai' order (guardrails apply). Re-checks the live price first."""
        try:
            p = copilot.proposals.get(pid)
            st = engine.state([p["market_id"]])
            m = st["markets"].get(p["market_id"])
            if not m:
                raise ValueError("market is no longer available")
            return copilot.proposals.approve(pid, m, lambda mid, sid, side, price, size, tp, sl: engine.place(mid, sid, side, price, size, "KEEP", 0, tp, sl, source="ai"))
        except KeyError:
            raise HTTPException(404, "unknown proposal")
        except ValueError as e:
            raise HTTPException(422, str(e))

    @app.post("/api/ai/proposals/{pid}/reject")
    def ai_reject(pid: str, _=Depends(auth)):
        try:
            return copilot.proposals.reject(pid)
        except KeyError:
            raise HTTPException(404, "unknown proposal")

    @app.post("/api/ai/chat")
    def ai_chat(body: dict, _=Depends(auth)):
        """Copilot reply to the conversation so far, grounded in a snapshot of the given open markets. Advisor mode: no orders."""
        ids = [str(i) for i in (body.get("market_ids") or [])][:5]
        try:
            st = engine.state(ids) if ids else {"markets": {}}
            ctxs = {i: c for i in ids if i in st["markets"] and (c := match_context.for_market({**st["markets"][i], "market_id": i}))}
            return copilot.chat(body.get("messages") or [], st["markets"], ctxs, "supervised" if body.get("mode") == "supervised" else "advisor")
        except AiError as e:
            raise HTTPException(502, str(e))

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
    def markets(sport: str = "tennis", date: str = "", _=Depends(auth)):
        if sport not in ("tennis", "football"):
            raise HTTPException(400, "sport must be tennis or football")
        if date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise HTTPException(400, "date must be YYYY-MM-DD")
        try:
            return engine.markets(sport, date or None)
        except ValueError:
            raise HTTPException(400, "date must be a real calendar date")

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
