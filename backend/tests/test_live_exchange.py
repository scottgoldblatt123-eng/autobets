"""LiveExchange against a fake Betfair: arming, order mirror, fills from matched deltas, reconcile, restart state."""
import pytest

from autobets.domain import MarketBook, Order, OrderRequest, Persistence, PriceLevel, SelectionBook, Side, Status
from autobets.exchange.base import ExchangeError
from autobets.exchange.live import LiveExchange


class FakeBF:
    """Just enough of BetfairAdapter: holds orders as Betfair would."""
    def __init__(self):
        self.trading_enabled, self.orders, self.n, self.down = False, {}, 0, False

    def enable_trading(self, c):
        self.trading_enabled = True

    def place_order(self, req):
        assert self.trading_enabled
        self.n += 1
        o = Order(f"B{self.n}", req, Status.UNMATCHED)
        self.orders[o.order_id] = o
        return self._copy(o)

    def _copy(self, o):
        r = o.request
        return Order(o.order_id, OrderRequest(r.market_id, r.selection_id, r.side, r.price, r.size, r.order_type, r.persistence, "", r.client_ref), o.status, o.matched, o.avg_price)

    def cancel_order(self, oid):
        self.orders[oid].status = Status.CANCELLED
        return self._copy(self.orders[oid])

    def update_persistence(self, oid, p):
        self.orders[oid].request.persistence = p
        return self._copy(self.orders[oid])

    def open_orders(self):
        if self.down:
            raise ExchangeError("network down")
        return [self._copy(o) for o in self.orders.values() if o.status in (Status.UNMATCHED, Status.PARTIAL)]

    def get_order(self, oid):
        if oid not in self.orders:
            raise ExchangeError("unknown order")
        return self._copy(self.orders[oid])

    def find_by_ref(self, ref):
        return next((self._copy(o) for o in self.orders.values() if o.request.client_ref == ref), None)

    def match(self, oid, size, price):
        o = self.orders[oid]
        tot = o.matched + size
        o.avg_price = (o.avg_price * o.matched + price * size) / tot
        o.matched = tot
        o.status = Status.MATCHED if tot >= o.request.size - 0.001 else Status.PARTIAL


REQ = lambda **k: OrderRequest("1.1", "10", Side.BACK, 3.0, 10.0, source=k.pop("source", "manual"), client_ref=k.pop("client_ref", "r1"))   # noqa: E731


def live():
    bf = FakeBF()
    return LiveExchange(bf, sync_every=0), bf


def test_disarmed_blocks_new_orders_but_not_cancels():
    ex, bf = live()
    with pytest.raises(ExchangeError):
        ex.place_order(REQ())
    with pytest.raises(ExchangeError):
        ex.arm("nope")
    ex.arm("SEND-REAL-ORDERS")
    o = ex.place_order(REQ())
    ex.disarm()
    assert ex.cancel_order(o.order_id).status is Status.CANCELLED          # cancelling always works
    with pytest.raises(ExchangeError):
        ex.place_order(REQ(client_ref="r2"))


def test_fills_are_derived_from_matched_changes_and_keep_source():
    ex, bf = live(); ex.arm("SEND-REAL-ORDERS")
    o = ex.place_order(REQ(source="script:Scalp"))
    bf.match(o.order_id, 4.0, 3.0); ex.sync()
    bf.match(o.order_id, 6.0, 3.1); ex.sync()
    fills = ex.fills()
    assert [round(f.size, 2) for f in fills] == [4.0, 6.0] and abs(fills[1].price - 3.1) < 0.01
    assert ex.get_order(o.order_id).request.source == "script:Scalp" and ex.get_order(o.order_id).status is Status.MATCHED
    ex.sync(); assert len(ex.fills()) == 2                                  # syncing again adds nothing


def test_order_that_vanishes_from_betfair_keeps_matched_part():
    ex, bf = live(); ex.arm("SEND-REAL-ORDERS")
    o = ex.place_order(REQ())
    bf.match(o.order_id, 3.0, 3.0); ex.sync()
    del bf.orders[o.order_id]; ex.sync()
    assert ex.get_order(o.order_id).status is Status.MATCHED


def test_sync_failure_leaves_mirror_and_reports():
    ex, bf = live(); ex.arm("SEND-REAL-ORDERS")
    o = ex.place_order(REQ())
    bf.down = True
    assert ex.sync() is False and ex.sync_error
    assert ex.get_order(o.order_id).status is Status.UNMATCHED
    bf.down = False; assert ex.sync() and not ex.sync_error


def test_reconcile_adopts_external_and_survives_restart():
    ex, bf = live(); ex.arm("SEND-REAL-ORDERS")
    o = ex.place_order(REQ())
    saved = ex.export_state()
    ext = bf.place_order(OrderRequest("1.2", "20", Side.LAY, 2.0, 5.0, client_ref="x"))      # placed outside AutoBets
    bf.orders[o.order_id].status = Status.CANCELLED                                         # cancelled on the Betfair site
    ex2 = LiveExchange(bf, sync_every=0); ex2.import_state(saved)
    r = ex2.reconcile()
    assert r["ok"] and r["adopted"] == [ext.order_id] and r["closed"] == [o.order_id]
    assert ex2.get_order(ext.order_id).request.source == "external"


def test_persistence_change_and_idempotent_lookup():
    ex, bf = live(); ex.arm("SEND-REAL-ORDERS")
    o = ex.place_order(REQ())
    assert ex.set_persistence(o.order_id, Persistence.CANCEL).request.persistence is Persistence.CANCEL
    assert ex.find_by_ref("r1").order_id == o.order_id and ex.find_by_ref("nope") is None


def test_engine_in_live_mode_places_manual_order_only_when_armed():
    from autobets.api.engine import Engine
    bf = FakeBF()

    class Feed:
        def get_books(self, ids, depth=False):
            return [MarketBook(i, selections={"10": SelectionBook("10", backs=[PriceLevel(3.0, 100)], lays=[PriceLevel(3.05, 100)]),
                                              "11": SelectionBook("11", backs=[PriceLevel(1.5, 100)], lays=[PriceLevel(1.52, 100)])}) for i in ids]

        def list_markets(self, *a, **k):
            return []
        trading_enabled = False
        def enable_trading(self, c): bf.enable_trading(c)
    ex = LiveExchange(bf, sync_every=0)
    eng = Engine(Feed(), "live", exchange=ex)
    eng.ex.refresh(eng.feed.get_books(["1.1"]))
    with pytest.raises(Exception):
        eng.place("1.1", "10", "BACK", 3.0, 10.0)
    ex.arm("SEND-REAL-ORDERS")
    r = eng.place("1.1", "10", "BACK", 3.0, 10.0)
    assert r["order"]["order_id"].startswith("B")
    assert eng.live_status()["armed"] is True
