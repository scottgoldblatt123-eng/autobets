"""User settings that the safety rules and the AI layer read. Saved with the engine state, so a restart keeps them.
A value of 0 for any limit means 'not set' (the default, per the approved design decisions)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

MODES = ("advisor", "supervised", "full")
LAY_BASIS = ("stake", "liability")


@dataclass
class Settings:
    automation_enabled: bool = True          # master switch for scripts and AI actions (off = the kill switch is on)
    ai_mode: str = "advisor"                 # advisor | supervised | full
    daily_loss_limit: float = 0.0            # automation stops for the day when the day's result reaches this loss. 0 = not set
    weekly_loss_limit: float = 0.0
    max_open_liability: float = 0.0          # cap on open liability for automated orders. 0 = not set
    include_manual_in_liability: bool = False
    confirm_manual_above: float = 0.0        # optional stake above which the UI asks "are you sure?" 0 = off
    lay_basis: str = "stake"                 # default for tickets and scripts: stake | liability
    ai_max_stake: float = 10.0               # cap on one AI proposal's stake
    ai_monthly_cap: float = 50.0             # estimated monthly spend at which AI calls stop (GBP)

    def to_dict(self) -> dict:
        return asdict(self)

    def update(self, patch: dict) -> None:
        """Apply a partial update; raises ValueError (changing nothing) if any value is not acceptable."""
        new = {**self.to_dict()}
        for k, v in patch.items():
            if k not in new:
                raise ValueError(f"unknown setting {k!r}")
            if isinstance(new[k], bool):
                if not isinstance(v, bool):
                    raise ValueError(f"{k} must be true or false")
            elif isinstance(new[k], float):
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise ValueError(f"{k} must be a number") from None
                if v < 0 or v != v or v > 1_000_000:
                    raise ValueError(f"{k} must be between 0 and 1,000,000")
            elif k == "ai_mode" and v not in MODES:
                raise ValueError(f"ai_mode must be one of {MODES}")
            elif k == "lay_basis" and v not in LAY_BASIS:
                raise ValueError(f"lay_basis must be one of {LAY_BASIS}")
            new[k] = v
        if new["ai_mode"] == "full":
            raise ValueError("Full AI is not available yet")
        for k, v in new.items():
            setattr(self, k, v)

    @classmethod
    def from_dict(cls, d: dict) -> "Settings":
        s = cls()
        for k, v in (d or {}).items():
            if hasattr(s, k) and type(getattr(s, k)) is type(v):
                setattr(s, k, v)
        return s
