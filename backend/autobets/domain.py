"""Core trading types shared by every exchange adapter."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Side(str, Enum):
    BACK = "BACK"
    LAY = "LAY"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    SP = "SP"                  # market on close
    SP_LIMIT = "SP_LIMIT"      # limit on close


class Persistence(str, Enum):
    CANCEL = "CANCEL"          # lapse at the off
    KEEP = "KEEP"              # stay on in play
    TAKE_SP = "TAKE_SP"        # convert to SP at the off


class Status(str, Enum):
    PENDING = "PENDING"        # journalled, not yet confirmed by the exchange
    UNMATCHED = "UNMATCHED"
    PARTIAL = "PARTIAL"
    MATCHED = "MATCHED"
    CANCELLED = "CANCELLED"
    LAPSED = "LAPSED"
    REJECTED = "REJECTED"


@dataclass
class OrderRequest:
    market_id: str
    selection_id: str
    side: Side
    price: float
    size: float                              # stake in GBP
    order_type: OrderType = OrderType.LIMIT
    persistence: Persistence = Persistence.KEEP
    source: str = "manual"                   # manual | script:<name> | ai
    client_ref: str = ""                     # idempotency key


@dataclass
class Order:
    order_id: str
    request: OrderRequest
    status: Status = Status.UNMATCHED
    matched: float = 0.0
    avg_price: float = 0.0

    @property
    def remaining(self) -> float:
        return round(self.request.size - self.matched, 2)


@dataclass
class Fill:
    order_id: str
    price: float
    size: float


@dataclass
class Position:
    """Net result for one selection: profit if it wins, profit if it loses."""
    win: float = 0.0
    lose: float = 0.0


@dataclass
class PriceLevel:
    price: float
    size: float


@dataclass
class SelectionBook:
    selection_id: str
    backs: list[PriceLevel] = field(default_factory=list)   # best first (highest)
    lays: list[PriceLevel] = field(default_factory=list)    # best first (lowest)
    last_traded: float | None = None
    traded: dict = field(default_factory=dict)             # price -> matched volume (full-depth reads only)


@dataclass
class MarketBook:
    market_id: str
    in_play: bool = False
    selections: dict[str, SelectionBook] = field(default_factory=dict)
