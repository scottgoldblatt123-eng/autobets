import pytest
from autobets import ticks, pnl
from autobets.domain import OrderRequest, OrderType, Persistence, Position, Side, Status
from autobets.exchange.simulated import SimulatedExchange
from autobets.guardrails import Guardrails, Limits
from autobets.journal import CONFIRMED, FAILED, Journal
from autobets.order_service import Blocked, OrderService


def test_tick_ladder():
    assert ticks.is_valid(1.01) and ticks.is_valid(2.02) and ticks.is_valid(3.05) and ticks.is_valid(1000)
    assert not ticks.is_valid(2.01) and not ticks.is_valid(3.02)
    assert ticks.move(1.99, 1) == 2.0 and ticks.move(2.0, 1) == 2.02
    assert ticks.move(3.95, 1) == 4.0 and ticks.move(1.01, -3) == 1.01
    assert ticks.nearest(2.031) == 2.04 and ticks.ticks_between(2.0, 2.1) == 5
    assert len(ticks.LADDER) == 350


def test_hedge_locks_equal_profit():
    pos = pnl.apply_fill(Position(), Side.BACK, 4.0, 10)       # back 10 @ 4.0
    assert (pos.win, pos.lose) == (30.0, -10.0)
    side, stake, locked = pnl.hedge(pos, 3.0)                  # price shortened: lay to green
    assert side is Side.LAY and stake == 13.33 and locked == 3.33
    after = pnl.apply_fill(pos, side, 3.0, stake)
    assert abs(after.win - after.lose) < 0.05


def test_hedge_none_when_level():
    assert pnl.hedge(Position(5, 5), 2.0) is None


def book(ex, backs=((2.0, 50),), lays=((2.02, 50),)):
    ex.set_book("m1", {"A": {"backs": list(backs), "lays": list(lays)}})


def req(side=Side.BACK, price=2.0, size=10, **kw):
    return OrderRequest("m1", "A", side, price, size, **kw)


def test_full_and_partial_match_and_price_improvement():
    ex = SimulatedExchange(); book(ex, backs=[(2.0, 4)])
    o = ex.place_order(req(Side.BACK, 1.98, 10))               # asks 1.98, gets 2.0 for 4
    assert o.status is Status.PARTIAL and o.matched == 4 and o.avg_price == 2.0 and o.remaining == 6
    book(ex, backs=[(2.0, 50)])                                 # liquidity returns: resting order fills
    assert ex.get_order(o.order_id).status is Status.MATCHED


def test_unmatched_when_price_not_available():
    ex = SimulatedExchange(); book(ex)
    o = ex.place_order(req(Side.BACK, 2.1, 10))
    assert o.status is Status.UNMATCHED and o.matched == 0


def test_lay_matches_available_to_lay():
    ex = SimulatedExchange(); book(ex)
    o = ex.place_order(req(Side.LAY, 2.04, 10))
    assert o.status is Status.MATCHED and o.avg_price == 2.02


def test_invalid_price_and_min_stake_rejected():
    ex = SimulatedExchange(); book(ex)
    assert ex.place_order(req(price=2.01)).status is Status.REJECTED
    assert ex.place_order(req(size=0.5)).status is Status.REJECTED


def test_idempotent_on_client_ref():
    ex = SimulatedExchange(); book(ex)
    a = ex.place_order(req(client_ref="x")); b = ex.place_order(req(client_ref="x"))
    assert a.order_id == b.order_id and len(ex.open_orders()) == 1


def test_persistence_at_the_off():
    ex = SimulatedExchange(); book(ex)
    keep = ex.place_order(req(price=2.1, persistence=Persistence.KEEP))
    cancel = ex.place_order(req(price=2.1, persistence=Persistence.CANCEL))
    ex.go_in_play("m1")
    assert ex.get_order(keep.order_id).status is Status.UNMATCHED
    assert ex.get_order(cancel.order_id).status is Status.LAPSED


def svc(limits=None):
    ex = SimulatedExchange(); book(ex)
    g = Guardrails(limits)
    return ex, g, OrderService(ex, Journal(), g)


def test_journal_written_before_send_and_confirmed():
    ex, g, s = svc()
    o = s.place(req(client_ref="r1"))
    assert o is not None and s.j.get("r1")["state"] == CONFIRMED and s.j.get("r1")["exchange_id"] == o.order_id


def test_lost_response_is_reconciled_without_double_placing():
    ex, g, s = svc()
    ex.fail_next_place = True
    assert s.place(req(client_ref="r2")) is None
    assert s.j.get("r2")["state"] == "UNKNOWN"
    assert s.reconcile() == ["r2"]
    assert s.j.get("r2")["state"] == CONFIRMED and len(ex.open_orders()) == 1


def test_unknown_order_not_on_exchange_is_marked_failed_not_resent():
    ex, g, s = svc()
    s.j.intent("ghost", req(client_ref="ghost")); s.j.set_state("ghost", "SENT")
    s.reconcile()
    assert s.j.get("ghost")["state"] == FAILED and len(ex.open_orders()) == 0


def test_kill_switch_blocks_automation_not_manual():
    ex, g, s = svc(); g.kill_switch = True
    with pytest.raises(Blocked): s.place(req(source="script:lay-the-draw"))
    assert s.place(req(source="manual")) is not None


def test_loss_limit_zero_means_unset():
    ex, g, s = svc(Limits(daily_loss_limit=0)); g.realised_today = -1000
    assert s.place(req(source="script:x")) is not None


def test_manual_losses_count_toward_loss_limit_but_manual_not_blocked():
    ex, g, s = svc(Limits(daily_loss_limit=50)); g.realised_today = -60     # lost 60 manually
    with pytest.raises(Blocked): s.place(req(source="script:x"))
    assert s.place(req(source="manual")) is not None and s.warnings
