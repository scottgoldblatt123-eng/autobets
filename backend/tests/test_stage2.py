import pytest
from autobets import ticks
from autobets.api.engine import Engine
from autobets.domain import MarketBook, PriceLevel, SelectionBook, Status

MID = "1.5"


class FakeFeed:
    """A feed whose prices the test controls. Two runners; best back / lay per runner, set with price()."""
    def __init__(self):
        self.p = {"A": (2.0, 2.02), "B": (1.96, 1.98)}
        self.last = {"A": 2.0, "B": 1.97}

    def price(self, sid, back, lay, last):
        self.p[sid] = (back, lay); self.last[sid] = last

    def get_books(self, ids, depth=False):
        b = MarketBook(MID)
        for sid, (bk, ly) in self.p.items():
            b.selections[sid] = SelectionBook(sid, backs=[PriceLevel(bk, 1000.0)], lays=[PriceLevel(ly, 1000.0)], last_traded=self.last[sid])
        return [b]

    def market_info(self, ids):
        return {MID: {"market_id": MID, "name": "Match Odds", "event": "A v B", "competition": "T", "start": None, "runners": {"A": "A", "B": "B"}}}


@pytest.fixture
def eng():
    return Engine(FakeFeed(), "demo")


def open_orders(e):
    return [o for o in e.ex.open_orders() if o.status in (Status.UNMATCHED, Status.PARTIAL)]


def test_offset_places_the_closing_bet_the_right_number_of_ticks_away(eng):
    eng.place(MID, "A", "BACK", 2.0, 20.0, "KEEP", offset=3)
    (close,) = open_orders(eng)
    r = close.request
    assert r.side.value == "LAY" and r.price == ticks.move(2.0, -3)                 # back at 2.00 -> lay 3 ticks lower (1.97)
    assert r.size == pytest.approx(20.0 * 2.0 / 1.97, abs=0.02)                      # stake that equalises the two bets


def test_lay_entry_offsets_upwards(eng):
    eng.place(MID, "A", "LAY", 2.02, 20.0, "KEEP", offset=2)
    (close,) = open_orders(eng)
    assert close.request.side.value == "BACK" and close.request.price == ticks.move(2.02, 2)


def test_stop_arms_against_the_entry_and_fires_cancelling_the_offset(eng):
    eng.place(MID, "A", "BACK", 2.0, 20.0, "KEEP", offset=3, stop=4)
    (stop,) = eng.triggers.values()
    assert stop.direction == "ge" and stop.price == ticks.move(2.0, 4) and stop.label == "stop loss"
    (close,) = open_orders(eng)
    feed = eng.feed
    feed.price("A", 2.06, 2.08, 2.08)                                                # price drifts 4 ticks against the back bet
    feed.price("B", 1.91, 1.93, 1.92)
    eng.state([MID])
    assert not eng.triggers and not eng.entries
    assert eng.ex.get_order(close.order_id).status is Status.CANCELLED               # the resting offset bet was cancelled
    assert any("Stop loss fired" in e["text"] for e in eng.events)
    pos = eng.positions()[MID]["A"]
    assert abs(pos.win - pos.lose) < 1.0                                             # position closed out (to within the hedge)


def test_matched_offset_removes_the_stop(eng):
    eng.place(MID, "A", "BACK", 2.0, 20.0, "KEEP", offset=3, stop=4)
    (close,) = open_orders(eng)
    eng.feed.price("A", 1.94, 1.97, 1.96)                                            # market moves our way: the lay at 1.97 is matched
    eng.state([MID])
    assert eng.ex.get_order(close.order_id).status is Status.MATCHED
    assert not eng.triggers and not eng.entries


def test_busy_counts_entries_and_market_triggers(eng):
    eng.place(MID, "A", "BACK", 2.0, 20.0, "KEEP", offset=3, stop=4)
    eng.add_market_trigger(MID, 5.0)
    assert eng.busy()["triggers"] == 3                                               # stop + entry + market auto-green


def test_market_auto_green_fires_when_the_profit_can_be_locked(eng):
    eng.place(MID, "A", "BACK", 20.0 and 2.0, 20.0)
    fig = eng._market_figure(MID)
    t = eng.add_market_trigger(MID, fig + 1.0)
    assert t["direction"] == "ge"
    eng.feed.price("A", 1.80, 1.82, 1.81); eng.feed.price("B", 2.4, 2.46, 2.44)
    eng.state([MID])
    assert not eng.mtriggers and any("Auto-green fired" in e["text"] for e in eng.events)
    out = list(eng.ex.get_order(o.order_id).status for o in eng.ex.open_orders())
    assert all(s is Status.MATCHED for s in out)
    with pytest.raises(ValueError):
        Engine(FakeFeed(), "demo").add_market_trigger(MID, 1.0)                       # no position at all: nothing to protect


def test_partial_green_hedges_part_of_the_way(eng):
    eng.place(MID, "A", "BACK", 2.0, 40.0)
    eng.feed.price("A", 1.80, 1.82, 1.81)
    full = eng.green_market.__wrapped__(eng, MID, False, 1.0)
    assert full["greened"] and full["level"]
    eng2 = Engine(FakeFeed(), "demo"); eng2.place(MID, "A", "BACK", 2.0, 40.0); eng2.feed.price("A", 1.80, 1.82, 1.81)
    half = eng2.green_market.__wrapped__(eng2, MID, False, 0.5)
    assert half["greened"] and half["level"] is False
    assert half["placed"][0]["stake"] == pytest.approx(full["placed"][0]["stake"] * 0.5, abs=0.02)
