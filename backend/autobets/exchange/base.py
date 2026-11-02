"""The one interface the engine talks to. Betfair, simulation and replay all implement it."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..domain import MarketBook, Order, OrderRequest


class ExchangeError(Exception):
    pass


class ExchangeAdapter(ABC):
    @abstractmethod
    def get_book(self, market_id: str) -> MarketBook: ...

    @abstractmethod
    def place_order(self, req: OrderRequest) -> Order:
        """Place an order. Must be idempotent on req.client_ref."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> Order: ...

    @abstractmethod
    def replace_order(self, order_id: str, new_price: float) -> Order: ...

    @abstractmethod
    def open_orders(self) -> list[Order]:
        """All orders the exchange believes are live or have matched volume (used by the reconciler)."""

    @abstractmethod
    def get_order(self, order_id: str) -> Order: ...

    @abstractmethod
    def find_by_ref(self, client_ref: str) -> Order | None:
        """Look an order up by our idempotency key without placing anything."""
