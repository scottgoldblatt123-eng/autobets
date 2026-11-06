"""Recommendations: ideas the AutoBets models surface for you to accept, edit, discuss or dismiss. Nothing here places a bet by itself.

Honest by construction: a trade recommendation is a gap between the model's probability and the market's price. The models are still
being tested against the market (tennis picked about 63% of winners against roughly 68-70% for the market), so confidence is never
shown as High, and every recommendation records the closing price so the evidence builds: CLV (did the market move our way) is measured
on every recommendation, whether or not you act on it. Auto-apply stays locked until 300 recommendations show positive CLV."""
from __future__ import annotations

import time

from . import ticks
from . import setups as _setups
from .ai.snapshot import _model_odds

EDGE_MIN = 0.04            # probability points between model and market before a trade is suggested
MAX_PENDING = 12                     # per sport, so a busy football list cannot crowd tennis out
EVIDENCE_NEEDED = 300
SPREAD_MAX_TICKS = 6
PRICE_MAX = 8.0            # long shots are where model noise is largest; not suggested
HORIZON_S = 8 * 3600
CAVEAT = {"tennis": "The tennis model has not yet beaten the market in testing, so treat this as an idea to check, not a signal.",
          "football": "The football model beat a league-average baseline in testing but has not been tested against market prices, so treat this as an idea to check."}


class Recs:
    def __init__(self, items: list[dict] | None = None, nxt: int = 1) -> None:
        self.items: dict[str, dict] = {r["id"]: r for r in (items or [])}
        self._next = nxt

    def export(self) -> dict:
        keep = sorted(list(self.items.values()), key=lambda r: r["created"])[-600:]
        return {"items": keep, "next": self._next}

    @classmethod
    def load(cls, d: dict | None) -> "Recs":
        d = d or {}
        return cls(d.get("items"), int(d.get("next", 1)))

    # ---- generation -------------------------------------------------------------------------------------------
    @staticmethod
    def candidate(kind: str, info: dict, book, ctx: dict | None) -> dict | None:
        """Best trade idea in one pre-match market, or None. `book` is a MarketBook."""
        fair = _model_odds(ctx, info.get("runners", {}))
        if not fair:
            return None
        best = None
        for sid, fo in fair.items():
            sel = book.selections.get(sid)
            if not sel or not sel.backs or not sel.lays:
                continue
            back, lay = sel.backs[0].price, sel.lays[0].price
            try:
                if ticks.ticks_between(back, lay) > SPREAD_MAX_TICKS:
                    continue
            except Exception:       # noqa: BLE001
                continue
            p = 1.0 / fo
            for side, price in (("BACK", back), ("LAY", lay)):
                if price > PRICE_MAX:
                    continue
                edge = (p - 1.0 / price) if side == "BACK" else (1.0 / price - p)
                if edge >= EDGE_MIN and (best is None or edge > best["edge"]):
                    best = {"selection_id": sid, "runner": info["runners"][sid], "side": side, "price": price, "model_p": round(p, 4),
                            "market_p": round(1.0 / price, 4), "edge": round(edge, 4), "back": back, "lay": lay, "sport": kind}
        return best

    def upsert(self, market_id: str, info: dict, cand: dict, stake: float) -> tuple[dict, bool]:
        """Create or refresh the pending recommendation for this market. Returns (rec, is_new)."""
        for r in list(self.items.values()):
            if r["status"] == "pending" and r["market_id"] == market_id and r["kind"] == "trade":
                if (r["selection_id"], r["side"]) == (cand["selection_id"], cand["side"]):
                    r.update(price=cand["price"], model_p=cand["model_p"], market_p=cand["market_p"], edge=cand["edge"], last_back=cand["back"], last_lay=cand["lay"], seen=time.time())
                    return r, False
                r["status"] = "expired"
        rid = f"c{self._next}"
        self._next += 1
        liab = stake if cand["side"] == "BACK" else round(stake * (cand["price"] - 1), 2)
        conf = "Medium" if cand["edge"] >= 0.08 else "Low"
        side_txt = "Back" if cand["side"] == "BACK" else "Lay"
        reason = (f"Model {cand['model_p'] * 100:.1f}% vs market {cand['market_p'] * 100:.1f}% for {cand['runner']}. {CAVEAT[cand['sport']]}")
        r = {"id": rid, "kind": "trade", "market_id": market_id, "event": info.get("event", ""), "market_name": info.get("name", ""), "start": info.get("start"),
             "selection_id": cand["selection_id"], "runner": cand["runner"], "side": cand["side"], "price": cand["price"], "model_p": cand["model_p"],
             "market_p": cand["market_p"], "edge": cand["edge"], "stake": stake, "max_loss": liab, "confidence": conf, "sport": cand["sport"],
             "title": f"{side_txt} {cand['runner']} · {info.get('event', '')}", "reason": reason, "status": "pending", "created": time.time(), "seen": time.time(),
             "entry_price": cand["price"], "last_back": cand["back"], "last_lay": cand["lay"], "clv": None, "dismiss_reason": ""}
        self.items[rid] = r
        return r, True

    def add_proposal(self, idea: dict) -> dict | None:
        """A new-script proposal from the AI. One per title: an idea already pending, saved or dismissed is not proposed again."""
        if any(r["kind"] == "script" and r["title"].lower() == idea["title"].lower() for r in self.items.values()):
            return None
        rid = f"c{self._next}"
        self._next += 1
        sc = idea["script"]
        r = {"id": rid, "kind": "script", "proposal": True, "market_id": "", "event": "", "market_name": "", "start": None, "status": "pending", "created": time.time(), "seen": time.time(),
             "confidence": "Low", "clv": None, "dismiss_reason": "", "sport": sc.get("sport", "any"), "edge": 0.0, "title": idea["title"], "side": "", "runner": "", "price": 0, "model_p": 0, "market_p": 0,
             "reason": idea["why"] + (f" Risk: {idea['risk']}" if idea.get("risk") else "") + " Not backtested: a hypothesis to test in practice mode.", "script": sc, "script_id": None}
        self.items[rid] = r
        return r

    def upsert_setup(self, market_id: str, info: dict, cand: dict) -> tuple[dict, bool]:
        """One pending setup per market and template. A refresh keeps the id (and what the user is looking at) but updates the live numbers."""
        for r in self.items.values():
            if r["kind"] == "setup" and r["status"] == "pending" and r["market_id"] == market_id and r["template"] == cand["template"]:
                r.update(price=cand["price"], model_p=cand["model_p"], market_p=cand["market_p"], edge=cand["edge"], seen=time.time())
                return r, False
            if r["kind"] == "setup" and r["status"] == "pending" and r["market_id"] == market_id:
                r["status"] = "expired"
        rid = f"c{self._next}"
        self._next += 1
        r = {"id": rid, "kind": "setup", "market_id": market_id, "event": info.get("event", ""), "market_name": cand.get("market_name") or info.get("name", ""),
             "start": info.get("start"), "status": "pending", "created": time.time(), "seen": time.time(), "confidence": "Low", "clv": None, "dismiss_reason": "",
             "entry_price": cand["price"], "plan_row": None, "script_id": None, "result": None,
             **{k: cand[k] for k in ("template", "sport", "selection_id", "runner", "side", "price", "model_p", "market_p", "edge", "title", "reason", "watch", "script", "stake", "max_loss")}}
        self.items[rid] = r
        return r, True

    def scan(self, engine, stake: float) -> list[dict]:
        """One pass over upcoming pre-match markets. Returns the recommendations created this pass."""
        created = []
        now = time.time()
        seen_markets = set()
        for sport in ("tennis", "football"):
            try:
                markets = engine.markets(sport)
            except Exception:       # noqa: BLE001
                continue
            soon = []
            for m in markets:
                st = m.get("start")
                try:
                    import datetime as dt
                    t0 = dt.datetime.fromisoformat(str(st).replace("Z", "+00:00")).timestamp() if st else None
                except ValueError:
                    t0 = None
                if t0 and 0 < t0 - now < HORIZON_S and not m.get("in_play"):
                    soon.append(m)
            for i in range(0, len(soon), 40):
                try:
                    books = engine.feed.get_books([m["market_id"] for m in soon[i:i + 40]], depth=False)
                except Exception:   # noqa: BLE001
                    continue
                bk = {b.market_id: b for b in books}
                for m in soon[i:i + 40]:
                    b = bk.get(m["market_id"])
                    if b is None or b.status != "OPEN":
                        continue
                    seen_markets.add(m["market_id"])
                    for r in list(self.items.values()):               # keep the latest pre-play quote on every idea, applied or not: it becomes the closing price
                        if r["kind"] == "trade" and r["clv"] is None and r["market_id"] == m["market_id"] and r["selection_id"] in b.selections:
                            q = b.selections[r["selection_id"]]
                            if q.backs and q.lays:
                                r["last_back"], r["last_lay"] = q.backs[0].price, q.lays[0].price
                    try:
                        ctx = engine.context_fn({**m, "market_id": m["market_id"]}) if engine.context_fn else None
                    except Exception:   # noqa: BLE001
                        ctx = None
                    if not ctx:
                        continue
                    try:
                        cand = None
                        if sport == "tennis":
                            cand = _setups.tennis(m, b, ctx, stake)
                        else:
                            ou = _setups.goals_market(engine.event_markets(m.get("event_id", ""))) if m.get("event_id") and (ctx.get("pre_model") or {}).get("over_2.5") is not None else None
                            if ou:
                                seen_markets.add(ou["market_id"])
                                ob = engine.feed.get_books([ou["market_id"]], depth=False)[0]
                                cand = _setups.football(m, ou, ob, ctx, stake) if ob.status == "OPEN" else None
                    except Exception:   # noqa: BLE001
                        cand = None
                    if cand:
                        r, new = self.upsert_setup(cand.get("market_id", m["market_id"]), m, cand)
                        if new:
                            created.append(r)
        # pending ideas that no longer qualify (edge gone, market off the board) expire; CLV is captured as markets go in play
        for r in list(self.items.values()):
            if r["kind"] not in ("trade", "setup"):
                continue
            if r["status"] == "pending" and r["market_id"] not in seen_markets and (now - r["seen"] > 300):
                r["status"] = "expired"
        self._pending_cap()
        return created

    def _pending_cap(self) -> None:
        for sport in ("tennis", "football"):
            pend = sorted((r for r in list(self.items.values()) if r["status"] == "pending" and r["kind"] in ("trade", "setup") and r.get("sport") == sport), key=lambda r: -r["edge"])
            for r in pend[MAX_PENDING:]:
                r["status"] = "expired"

    def measure_clv(self, engine) -> int:
        """Record the closing price for recommendations whose market has gone in play: did the market move our way?"""
        todo = [r for r in list(self.items.values()) if r["kind"] == "trade" and r["clv"] is None and r.get("start")]
        if not todo:
            return 0
        n = 0
        try:
            import datetime as dt
            books = {}
            mids = sorted({r["market_id"] for r in todo})
            for i in range(0, len(mids), 40):
                for b in engine.feed.get_books(mids[i:i + 40], depth=False):
                    books[b.market_id] = b
        except Exception:       # noqa: BLE001
            return 0
        for r in todo:
            b = books.get(r["market_id"])
            if b is None or not (b.in_play or b.status == "CLOSED"):
                continue
            # the last pre-play price we saw is the closing price
            mid = (r["last_back"] + r["last_lay"]) / 2 if r.get("last_back") and r.get("last_lay") else None
            if not mid:
                continue
            qe, qc = 1.0 / r["entry_price"], 1.0 / mid
            r["clv"] = round((qc - qe) if r["side"] == "BACK" else (qe - qc), 4)
            r["closing_mid"] = round(mid, 3)
            if r["status"] == "pending":
                r["status"] = "expired"
            n += 1
        return n

    # ---- reading ----------------------------------------------------------------------------------------------
    def stats(self, since: float = 0.0) -> dict:
        trades = [r for r in list(self.items.values()) if r["kind"] in ("trade", "setup") and r["created"] >= since]
        applied = [r for r in trades if r["status"] == "applied"]
        measured = [r for r in list(self.items.values()) if r["kind"] == "trade" and r["clv"] is not None]
        avg_clv = round(100 * sum(r["clv"] for r in measured) / len(measured), 2) if measured else None
        decided = len(applied) + sum(1 for r in trades if r["status"] == "dismissed")
        pend = [r for r in list(self.items.values()) if r["status"] == "pending"]
        return {"pending": len(pend), "applied": len(applied), "acceptance": round(100 * len(applied) / decided) if decided else None,
                "avg_edge_applied": round(100 * sum(r["edge"] for r in applied) / len(applied), 1) if applied else None,
                "evidence": len(measured), "evidence_needed": EVIDENCE_NEEDED, "avg_clv_pts": avg_clv,
                "auto_apply_unlocked": len(measured) >= EVIDENCE_NEEDED and (avg_clv or 0) > 0,
                "setups": sum(1 for r in self.items.values() if r["kind"] == "setup" and r["status"] == "applied"),
                "setup_results": {"n": sum(1 for r in self.items.values() if r["kind"] == "setup" and r.get("result") is not None),
                                  "net": round(sum(r["result"] for r in self.items.values() if r["kind"] == "setup" and r.get("result") is not None), 2)},
                "counts": {"all": len(pend), "setups": sum(1 for r in pend if r["kind"] == "setup"), "trades": sum(1 for r in pend if r["kind"] == "trade"), "scripts": sum(1 for r in pend if r["kind"] == "script"),
                           "models": sum(1 for r in pend if r["kind"] == "model")}}

    def list(self, kind: str = "all", status: str = "pending") -> list[dict]:
        rows = [r for r in list(self.items.values()) if (status == "all" or r["status"] == status) and (kind == "all" or r["kind"] == kind.rstrip("s"))]
        return sorted(rows, key=lambda r: (r["kind"] == "script", -r["edge"] if r["kind"] in ("trade", "setup") else 0))
