"""Trade proposals from the copilot (Supervised mode). The model writes proposals as fenced ```proposal JSON blocks; this module parses and
validates them in plain code, holds them pending, and only places an order when Scott approves. Approval re-checks the live price, and the
order goes through the normal order service as source 'ai', so the guardrails (kill switch, limits) apply. The AI is never in that path."""
from __future__ import annotations

import json
import re
import threading
import time
import uuid

from .. import ticks

EXPIRES_S = 180.0
MAX_DRIFT_TICKS = 3
FENCE = re.compile(r"```proposal\s*(\{.*?\})\s*```", re.S)


def split_reply(text: str) -> tuple[str, list[dict]]:
    """-> (reply text without the proposal blocks, raw proposal dicts)."""
    raw = []
    for m in FENCE.finditer(text or ""):
        try:
            raw.append(json.loads(m.group(1)))
        except ValueError:
            pass
    return FENCE.sub("", text or "").strip(), raw


class ProposalBook:
    def __init__(self, max_stake: float = 10.0) -> None:
        self.max_stake = max_stake
        self.items: dict[str, dict] = {}
        self.lock = threading.RLock()

    def validate(self, raw: dict, markets: dict) -> dict:
        """Turn one raw proposal into a checked one, or raise ValueError saying why it is not acceptable."""
        mid = str(raw.get("market_id", ""))
        m = markets.get(mid)
        if not m:
            raise ValueError("market is not one of the open markets")
        sid = next((k for k, n in m.get("runners", {}).items() if n.strip().lower() == str(raw.get("runner", "")).strip().lower()), None)
        if sid is None:
            raise ValueError(f"no runner called {raw.get('runner')!r}")
        side = str(raw.get("side", "")).upper()
        if side not in ("BACK", "LAY"):
            raise ValueError("side must be BACK or LAY")
        price = float(raw.get("price", 0))
        if not ticks.is_valid(price):
            price = ticks.nearest(price)
        stake = round(float(raw.get("stake", 0)), 2)
        if stake < 1:
            raise ValueError("minimum stake is £1")
        if stake > self.max_stake:
            raise ValueError(f"stake £{stake:g} is above the AI proposal limit of £{self.max_stake:g}")
        tp, sl = int(raw.get("take_profit_ticks") or 0), int(raw.get("stop_loss_ticks") or 0)
        if not (0 <= tp <= 40 and 0 <= sl <= 40):
            raise ValueError("take-profit and stop-loss must be 0-40 ticks")
        if m.get("status") != "OPEN":
            raise ValueError("market is not open")
        return {"market_id": mid, "event": m.get("event"), "runner": m["runners"][sid], "selection_id": sid, "side": side, "price": price, "stake": stake,
                "take_profit_ticks": tp, "stop_loss_ticks": sl, "reason": str(raw.get("reason", ""))[:400]}

    def add(self, raw_list: list[dict], markets: dict, now: float | None = None) -> tuple[list[dict], list[str]]:
        now = now or time.time(); made, rejected = [], []
        for raw in raw_list[:3]:
            try:
                p = self.validate(raw, markets)
            except (ValueError, TypeError) as e:
                rejected.append(str(e)); continue
            p.update(id=uuid.uuid4().hex[:10], status="pending", created=now)
            with self.lock:
                self.items[p["id"]] = p
            made.append(p)
        return made, rejected

    def get(self, pid: str, now: float | None = None) -> dict:
        now = now or time.time()
        with self.lock:
            p = self.items.get(pid)
            if not p:
                raise KeyError("unknown proposal")
            if p["status"] == "pending" and now - p["created"] > EXPIRES_S:
                p["status"] = "expired"
            return p

    def reject(self, pid: str) -> dict:
        p = self.get(pid)
        if p["status"] == "pending":
            p["status"] = "rejected"
        return p

    def check_price(self, p: dict, market: dict) -> None:
        """The market must not have moved against the proposal by more than MAX_DRIFT_TICKS since it was made."""
        s = (market.get("selections") or {}).get(p["selection_id"], {})
        side_levels = s.get("backs" if p["side"] == "BACK" else "lays", [])
        if not side_levels:
            raise ValueError("no price available on that side right now")
        cur = side_levels[0][0]
        # a back at P needs the market back price to still be about P or better (higher); a lay needs the lay price at P or lower
        moved = ticks.ticks_between(cur, p["price"]) if p["side"] == "BACK" else ticks.ticks_between(p["price"], cur)
        if moved > MAX_DRIFT_TICKS:
            raise ValueError(f"the price has moved: best {p['side'].lower()} is now {cur:g} against the proposed {p['price']:g}. Ask again for a fresh idea.")

    def approve(self, pid: str, market: dict, place, now: float | None = None) -> dict:
        """Place the order through `place(...)` (Engine.place with source 'ai') if the proposal is still pending and the price holds."""
        p = self.get(pid, now)
        if p["status"] != "pending":
            raise ValueError(f"this proposal is {p['status']}")
        self.check_price(p, market)
        res = place(p["market_id"], p["selection_id"], p["side"], p["price"], p["stake"], p["take_profit_ticks"], p["stop_loss_ticks"])
        p["status"] = "approved"; p["order"] = res.get("order")
        return {"proposal": p, "warnings": res.get("warnings", [])}
