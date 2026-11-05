"""Plain-code guardrails. The AI is never in this path. Defaults follow the solution document:
manual orders are not blocked by limits (FR-U10) but manual losses count toward a loss limit
once one is set; a loss limit of 0 means 'not set'."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Limits:
    max_stake: float = 0.0          # 0 = not set
    max_open_exposure: float = 0.0  # 0 = not set
    daily_loss_limit: float = 0.0   # 0 = not set
    weekly_loss_limit: float = 0.0  # 0 = not set


class Guardrails:
    def __init__(self, limits: Limits | None = None) -> None:
        self.limits = limits or Limits()
        self.kill_switch = False
        self.realised_today = 0.0      # the day's result (settled + open positions marked to market), manual + automated together
        self.realised_week = 0.0
        self.open_exposure = 0.0

    def check(self, source: str, stake: float, liability: float | None = None) -> tuple[bool, str]:
        """Return (allowed, reason). Manual orders are warned about, not blocked, except by the kill switch."""
        automated = source != "manual"
        if self.kill_switch and automated:
            return False, "kill switch is on"
        lim = self.limits
        loss_hit = (lim.daily_loss_limit > 0 and -self.realised_today >= lim.daily_loss_limit) or (lim.weekly_loss_limit > 0 and -self.realised_week >= lim.weekly_loss_limit)
        if automated and source.endswith(":exit"):
            return True, ""                  # closing or greening only ever reduces risk, so limits never stop it (the kill switch above still does)
        if automated:
            if loss_hit:
                return False, "loss limit reached (manual and automated results combined)"
            if lim.max_stake > 0 and stake > lim.max_stake:
                return False, f"stake {stake} above max stake {lim.max_stake}"
            if lim.max_open_exposure > 0 and self.open_exposure + (stake if liability is None else liability) > lim.max_open_exposure:
                return False, "open exposure limit reached"
        elif loss_hit:
            return True, "warning: loss limit reached (manual orders are not blocked)"
        return True, ""
