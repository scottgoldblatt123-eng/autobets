"""Practice mode: real (delayed) Betfair prices, simulated orders. Nothing is ever sent to Betfair."""
from __future__ import annotations

from ..domain import MarketBook
from ..exchange.simulated import SimulatedExchange


class PracticeExchange(SimulatedExchange):
    """A SimulatedExchange whose books are refreshed from a price feed. Orders match against the latest
    real prices; resting orders match when later real prices cross them. Queue position and the effect of
    your own orders on the market are not modelled, so practice results flatter fast trading.
    At the off, 'cancel' orders lapse; 'take SP' orders are simply removed (SP is not simulated)."""

    def refresh(self, books: list[MarketBook]) -> None:
        for b in books:
            prev = self._books.get(b.market_id)
            was_in_play = prev.in_play if prev else b.in_play      # first sight of a market already in play is not "the off"
            sels = {sid: {"backs": [(l.price, l.size) for l in s.backs], "lays": [(l.price, l.size) for l in s.lays],
                          "last": s.last_traded, "status": s.status} for sid, s in b.selections.items()}
            self.set_book(b.market_id, sels, in_play=b.in_play, status=b.status)
            for sid, s in b.selections.items():
                self._books[b.market_id].selections[sid].traded = s.traded
            if b.in_play and not was_in_play:
                self._at_the_off(b.market_id)
