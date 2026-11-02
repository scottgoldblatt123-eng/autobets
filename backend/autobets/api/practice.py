"""Practice mode: real (delayed) Betfair prices, simulated orders. Nothing is ever sent to Betfair."""
from __future__ import annotations

from ..domain import MarketBook
from ..exchange.simulated import SimulatedExchange


class PracticeExchange(SimulatedExchange):
    """A SimulatedExchange whose books are refreshed from a price feed. Orders match against the latest
    real prices; resting orders match when later real prices cross them. Queue position and the effect of
    your own orders on the market are not modelled, so practice results flatter fast trading."""

    def refresh(self, books: list[MarketBook]) -> None:
        for b in books:
            sels = {sid: {"backs": [(l.price, l.size) for l in s.backs], "lays": [(l.price, l.size) for l in s.lays], "last": s.last_traded}
                    for sid, s in b.selections.items()}
            self.set_book(b.market_id, sels, in_play=b.in_play)
            for sid, s in b.selections.items():
                self._books[b.market_id].selections[sid].traded = s.traded
