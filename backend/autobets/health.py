"""System health: one row per thing AutoBets depends on, with a plain-English state. Feeds the health popover and the alerts centre."""
from __future__ import annotations

import datetime as dt
import time

STALE_S = 15 * 60          # a collector with no tick for this long is called stale


def _age(v) -> float | None:
    """Seconds since an ISO timestamp or epoch number; None if unknown."""
    if v in (None, ""):
        return None
    try:
        if isinstance(v, (int, float)):
            return max(0.0, time.time() - float(v))
        return max(0.0, time.time() - dt.datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _human(s: float | None) -> str:
    if s is None:
        return "no update yet"
    return f"{int(s)}s ago" if s < 90 else f"{int(s / 60)} min ago" if s < 5400 else f"{int(s / 3600)} h ago"


def collector(name: str, status: dict | None, key: str) -> dict:
    if status is None or status.get("enabled") is False:
        return {"key": key, "name": name, "level": "off", "detail": "Not running (its key is not set on the server)"}
    age = _age(status.get("last_tick"))
    err = status.get("last_error")
    if err and (age is None or age > 120):
        return {"key": key, "name": name, "level": "bad", "detail": f"Last error: {str(err)[:140]}"}
    if age is None or age > STALE_S:
        return {"key": key, "name": name, "level": "bad", "detail": f"Stale: last update {_human(age)}"}
    return {"key": key, "name": name, "level": "ok", "detail": f"Last update {_human(age)}"}


def build(engine, football: dict | None, tennis: dict | None, pricelog: dict | None, claude_enabled: bool, ai_status: dict) -> dict:
    items = []
    fe = engine.feed_health()
    items.append({"key": "betfair", "name": "Betfair prices", "level": "ok" if fe["ok"] else "bad", "detail": fe["detail"]})
    items.append(collector("Tennis data (live scores, history)", tennis, "tennis"))
    items.append(collector("Football data (live scores, team news, line-ups)", football, "football"))
    if pricelog is not None and pricelog.get("enabled") is not False:
        age = _age(pricelog.get("last"))
        items.append({"key": "pricelog", "name": "Betfair price log", "level": "bad" if pricelog.get("last_error") else "ok", "detail": pricelog.get("last_error") or f"Last recorded {_human(age)}"})
    if not claude_enabled:
        items.append({"key": "claude", "name": "Claude API", "level": "off", "detail": "No ANTHROPIC_API_KEY on the server: copilot and script builder are off"})
    else:
        cap = ai_status.get("cap_gbp") or 0
        used = ai_status.get("estimated_gbp") or 0
        over = cap and used >= cap
        items.append({"key": "claude", "name": "Claude API", "level": "bad" if over else "ok", "detail": f"Spend this month about £{used:.2f} of £{cap:g} cap" + (" (cap reached, AI calls stopped)" if over else "")})
    issues = [i for i in items if i["level"] == "bad"]
    return {"items": items, "issues": len(issues)}
