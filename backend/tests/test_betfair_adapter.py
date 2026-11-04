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
