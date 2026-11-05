import pytest
from autobets.domain import OrderRequest, Side
from autobets.exchange.base import ExchangeError
from autobets.exchange.betfair import BetfairAdapter


class Fake:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def post(self, url, headers, form=None, body=None):
        self.calls.append((url, dict(headers)))
        return self.responses.pop(0)


LOGIN_OK = (200, {"loginStatus": "SUCCESS", "sessionToken": "tok1"})
BOOK = {"marketId": "1.1", "inplay": True, "runners": [
    {"selectionId": 10, "lastPriceTraded": 3.4,
     "ex": {"availableToBack": [{"price": 3.35, "size": 120.5}], "availableToLay": [{"price": 3.4, "size": 80}]}},
    {"selectionId": 11, "ex": {"availableToBack": [], "availableToLay": []}}]}


def test_login_then_book_parsed():
    fake = Fake([LOGIN_OK, (200, [BOOK])])
    b = BetfairAdapter("k", "u", "p", fake).get_book("1.1")
    assert b.in_play and b.selections["10"].backs[0].price == 3.35 and b.selections["10"].lays[0].size == 80
    assert b.selections["10"].last_traded == 3.4 and b.selections["11"].backs == []
    assert fake.calls[1][1]["X-Authentication"] == "tok1"


def test_failed_login_raises_without_leaking_secrets():
    with pytest.raises(ExchangeError) as e:
        BetfairAdapter("secretkey", "u", "secretpw", Fake([(200, {"loginStatus": "INVALID_USERNAME_OR_PASSWORD"})])).login()
    assert "secretpw" not in str(e.value) and "secretkey" not in str(e.value)


def test_expired_session_relogs_in_once():
    fake = Fake([LOGIN_OK, (400, {"detail": {"APINGException": {"errorCode": "INVALID_SESSION_INFORMATION"}}}),
                 (200, {"loginStatus": "SUCCESS", "sessionToken": "tok2"}), (200, [BOOK])])
    a = BetfairAdapter("k", "u", "p", fake)
    assert a.get_book("1.1").market_id == "1.1" and a.token == "tok2"


def test_other_errors_not_retried():
    fake = Fake([LOGIN_OK, (400, {"detail": "TOO_MUCH_DATA"})])
    with pytest.raises(ExchangeError): BetfairAdapter("k", "u", "p", fake).get_book("1.1")


def test_trading_disabled_while_read_only():
    a = BetfairAdapter("k", "u", "p", Fake([]))
    with pytest.raises(ExchangeError): a.place_order(OrderRequest("1.1", "10", Side.BACK, 2.0, 10))


def test_list_markets_shape():
    cat = [{"marketId": "1.5", "marketName": "Match Odds", "marketStartTime": "2026-11-02T15:00:00.000Z",
            "event": {"name": "A v B"}, "competition": {"name": "League"},
            "runners": [{"selectionId": 1, "runnerName": "A"}, {"selectionId": 2, "runnerName": "B"}]}]
    m = BetfairAdapter("k", "u", "p", Fake([LOGIN_OK, (200, cat)])).list_markets("1")
    assert m[0]["event"] == "A v B" and m[0]["runners"] == {"1": "A", "2": "B"}


def test_practice_engine_on_betfair_shaped_data():
    """The practice engine works against the real adapter's response shapes: catalogue, depth book, traded volume."""
    from autobets.api.engine import Engine
    cat = [{"marketId": "1.1", "marketName": "Match Odds", "marketStartTime": "2026-11-02T18:00:00.000Z",
            "event": {"name": "A v B"}, "competition": {"name": "Cup"},
            "runners": [{"selectionId": 10, "runnerName": "A"}, {"selectionId": 11, "runnerName": "B"}]}]
    book = {"marketId": "1.1", "inplay": False, "runners": [
        {"selectionId": 10, "lastPriceTraded": 3.4, "ex": {"availableToBack": [{"price": 3.35, "size": 120.5}, {"price": 3.3, "size": 40}],
                                                         "availableToLay": [{"price": 3.4, "size": 80}], "tradedVolume": [{"price": 3.4, "size": 900}]}},
        {"selectionId": 11, "ex": {"availableToBack": [], "availableToLay": []}}]}
    fake = Fake([LOGIN_OK, (200, cat), (200, [book]), (200, [book]), (200, [book]), (200, [book])])
    eng = Engine(BetfairAdapter("k", "u", "p", fake), "practice")
    ms = eng.markets("tennis")
    assert ms[0]["runners"] == {"10": "A", "11": "B"}
    st = eng.state(["1.1"])
    sel = st["markets"]["1.1"]["selections"]["10"]
    assert sel["backs"][0] == [3.35, 120.5] and sel["traded"] == [[3.4, 900]]
    r = eng.place("1.1", "10", "BACK", 3.35, 10)
    assert r["order"]["status"] == "MATCHED"
    assert eng.state(["1.1"])["markets"]["1.1"]["positions"]["10"]["lose"] == -10
    assert not any("order" in url for url, _ in fake.calls)       # nothing was ever sent to the order endpoints


def test_market_list_carries_in_play_flag():
    from autobets.api.engine import Engine
    cat = [{"marketId": "1.1", "marketName": "Match Odds", "event": {"name": "A v B"}, "runners": []},
           {"marketId": "1.2", "marketName": "Match Odds", "event": {"name": "C v D"}, "runners": []}]
    live, pre = dict(BOOK, marketId="1.1", inplay=True), dict(BOOK, marketId="1.2", inplay=False)
    eng = Engine(BetfairAdapter("k", "u", "p", Fake([LOGIN_OK, (200, cat), (200, [live, pre])])), "practice")
    assert {m["market_id"]: m["in_play"] for m in eng.markets("tennis")} == {"1.1": True, "1.2": False}


# ---- real orders (mock transport only; nothing here touches Betfair) -------------------
from autobets.domain import Persistence, Status


def _live(responses):
    fake = Fake([LOGIN_OK] + responses)
    a = BetfairAdapter("k", "u", "p", fake)
    a.enable_trading("SEND-REAL-ORDERS")
    return a, fake


REQ = OrderRequest("1.1", "10", Side.BACK, 3.5, 10.0, client_ref="ref-1")


def test_orders_are_off_by_default_and_need_the_phrase():
    a = BetfairAdapter("k", "u", "p", Fake([]))
    with pytest.raises(ExchangeError):
        a.place_order(REQ)
    with pytest.raises(ExchangeError):
        a.enable_trading("yes")
    assert not a.trading_enabled


def test_place_order_sends_expected_instruction_and_parses_fill():
    a, fake = _live([(200, {"currentOrders": [], "moreAvailable": False}),
                     (200, {"status": "SUCCESS", "instructionReports": [{"status": "SUCCESS", "betId": "B1", "sizeMatched": 4.0, "averagePriceMatched": 3.5}]})])
    o = a.place_order(REQ)
    assert o.order_id == "B1" and o.status is Status.PARTIAL and o.matched == 4.0 and o.avg_price == 3.5
    assert [c[0].rsplit("/", 2)[-2] for c in fake.calls[1:]] == ["listCurrentOrders", "placeOrders"]


def test_place_order_is_idempotent_on_client_ref():
    cur = {"betId": "B9", "marketId": "1.1", "selectionId": 10, "side": "BACK", "priceSize": {"price": 3.5, "size": 10.0},
           "sizeMatched": 0, "sizeRemaining": 10.0, "status": "EXECUTABLE", "customerOrderRef": "ref-1"}
    a, fake = _live([(200, {"currentOrders": [cur], "moreAvailable": False})])
    assert a.place_order(REQ).order_id == "B9" and len(fake.calls) == 2      # login + lookup, no placeOrders


def test_refused_order_raises_with_code_only():
    a, _ = _live([(200, {"currentOrders": []}), (200, {"status": "FAILURE", "instructionReports": [{"status": "FAILURE", "errorCode": "BET_TAKEN_OR_LAPSED"}]})])
    with pytest.raises(ExchangeError) as e:
        a.place_order(REQ)
    assert "BET_TAKEN_OR_LAPSED" in str(e.value)


def test_cancel_and_status_mapping():
    row = {"betId": "B1", "marketId": "1.1", "selectionId": 10, "side": "LAY", "priceSize": {"price": 2.0, "size": 5.0},
           "sizeMatched": 0, "sizeRemaining": 5.0, "status": "EXECUTABLE"}
    done = dict(row, sizeRemaining=0, sizeCancelled=5.0, status="EXECUTION_COMPLETE")
    a, fake = _live([(200, {"currentOrders": [row]}), (200, {"status": "SUCCESS", "instructionReports": [{"status": "SUCCESS"}]}),
                     (200, {"currentOrders": [done]})])
    assert a.cancel_order("B1").status is Status.CANCELLED
    assert fake.calls[2][0].endswith("cancelOrders/")


def test_take_sp_persistence_maps_to_market_on_close():
    assert BetfairAdapter._PERSIST[Persistence.TAKE_SP] == "MARKET_ON_CLOSE"
