import pytest
from autobets import setups
from autobets.api.engine import Engine
from autobets.domain import MarketBook, PriceLevel, SelectionBook
from autobets.recs import Recs
from autobets.scripts import check, evaluate, validate

RUN = {"A": "Alpha Smith", "B": "Beta Jones"}
INFO = {"market_id": "1.5", "runners": RUN, "event": "Alpha Smith v Beta Jones", "name": "Match Odds", "start": "2030-01-01T10:00:00Z", "event_id": "e1"}


def mk(prices):
    sel = lambda i, b, l: SelectionBook(i, backs=[PriceLevel(b, 100)], lays=[PriceLevel(l, 100)], last_traded=b)
    return MarketBook("1.5", in_play=False, status="OPEN", selections={k: sel(k, *v) for k, v in prices.items()})


def ctx(pa):
    return {"kind": "tennis", "players": ["Alpha Smith", "Beta Jones"], "model": {"p": [pa, 1 - pa], "odds": [1 / pa, 1 / (1 - pa)]}}


def test_tennis_setup_backs_the_underrated_player_after_a_break_and_script_is_valid():
    c = setups.tennis(INFO, mk({"A": (2.2, 2.24), "B": (1.8, 1.82)}), ctx(0.50), 10)          # model 50% vs market ~45%
    assert c["template"] == "tennis_swing_back" and c["selection_id"] == "A" and c["side"] == "BACK"
    s = validate(c["script"])
    entry = s["rules"][0]
    assert {"type": "set_games_diff", "op": "<=", "value": -1.0} in entry["when"]
    px = next(x for x in entry["when"] if x["type"] == "price")
    assert px["value"] > 2.24                                                                       # waits for the price to lengthen
    assert "not a prediction" in c["reason"]


def test_tennis_setup_lays_the_overrated_player_when_the_underrated_one_is_a_heavy_favourite():
    c = setups.tennis(INFO, mk({"A": (1.2, 1.21), "B": (5.0, 5.2)}), ctx(0.80), 10)           # market ~83% for A, model 80%: B is under-rated... A over-rated
    c = setups.tennis(INFO, mk({"A": (1.3, 1.31), "B": (3.6, 3.7)}), ctx(0.70), 10)           # A market ~77%, model 70%: B has the positive gap, price 3.6 -> back B on a break
    assert c["selection_id"] == "B" and c["side"] == "BACK"
    c = setups.tennis(INFO, mk({"A": (1.2, 1.21), "B": (7.2, 7.4)}), ctx(0.80), 10)           # best gap is on a price too short to be worth it and the other is out of range
    assert c is None


def test_tennis_setup_needs_a_real_gap_and_a_model():
    assert setups.tennis(INFO, mk({"A": (2.0, 2.02), "B": (2.0, 2.02)}), ctx(0.505), 10) is None
    assert setups.tennis(INFO, mk({"A": (2.0, 2.02), "B": (2.0, 2.02)}), None, 10) is None


def test_new_tennis_conditions():
    view = {"player_idx": 0, "ctx": {"sets": [[1, 3]], "sets_won": ["0", "0"]}}
    assert check({"type": "set_games_diff", "op": "<=", "value": -1}, view, set())
    assert not check({"type": "set_games_diff", "op": ">=", "value": 0}, view, set())
    assert check({"type": "set_games_diff", "op": ">=", "value": 1}, {**view, "player_idx": 1}, set())      # the same score seen from the other player
    assert not check({"type": "set_games_diff", "op": "<=", "value": -1}, {**view, "player_idx": None}, set())
    assert check({"type": "sets_diff", "op": "<", "value": 0}, {"player_idx": 0, "ctx": {"sets_won": ["0", "1"]}}, set())


def ou_info():
    return {"market_id": "1.6", "name": "Over/Under 2.5 Goals", "market_type": "OVER_UNDER_25", "runners": {"O": "Over 2.5 Goals", "U": "Under 2.5 Goals"}}


def ou_book(o, u):
    sel = lambda i, b, l: SelectionBook(i, backs=[PriceLevel(b, 100)], lays=[PriceLevel(l, 100)], last_traded=b)
    return MarketBook("1.6", in_play=False, status="OPEN", selections={"O": sel("O", *o), "U": sel("U", *u)})


FINFO = {"market_id": "1.7", "event": "Home FC v Away FC", "name": "Match Odds", "start": "2030-01-01T15:00:00Z"}


def test_football_over_setup_waits_until_minute_15_and_never_enters_worse_than_the_pre_match_price():
    c = setups.football(FINFO, ou_info(), ou_book((2.2, 2.24), (1.8, 1.82)), {"pre_model": {"over_2.5": 0.55, "mu": [1.5, 1.4]}}, 10)   # market ~45% vs model 55%
    assert c["template"] == "football_over_wait" and c["market_id"] == "1.6" and c["selection_id"] == "O"
    s = validate(c["script"])
    when = s["rules"][0]["when"]
    assert {"type": "minute", "op": ">=", "value": 15.0} in when and any(x["type"] == "price" and x["value"] == 2.2 for x in when)
    assert len(s["rules"]) == 1                                                                     # held to the end: no hedge rule


def test_football_under_scalp_setup_repeats_and_keeps_scalping_after_a_loss_exit():
    c = setups.football(FINFO, ou_info(), ou_book((2.0, 2.02), (1.9, 1.92)), {"pre_model": {"over_2.5": 0.42, "mu": [1.1, 1.0]}}, 10)
    assert c["template"] == "football_under_scalp" and c["selection_id"] == "U"
    s = validate(c["script"])
    assert s["rules"][0]["repeat"] == 10
    kinds = {r["id"]: r["kind"] for r in s["rules"]}
    assert kinds["r3"] == "exit"                       # a loss hedge is an exit, so the script re-arms after it
    assert kinds["r4"] == "safety"                     # the second goal ends it
    assert setups.football(FINFO, ou_info(), ou_book((2.0, 2.02), (1.9, 1.92)), {"pre_model": {"over_2.5": 0.60, "mu": [1.6, 1.6]}}, 10)["template"] == "football_over_wait"
    assert setups.football(FINFO, ou_info(), ou_book((1.4, 1.42), (3.0, 3.1)), {"pre_model": {"over_2.5": 0.80, "mu": [2.0, 1.8]}}, 10) is None    # Over too short to be worth waiting for
    assert setups.football(FINFO, ou_info(), ou_book((2.0, 2.02), (1.9, 1.92)), None, 10) is None


def test_accepting_a_setup_saves_the_script_switches_it_on_and_adds_the_plan_row_without_betting():
    e = Engine.demo()
    mid = "1.900004"                                                                                   # demo Over/Under 2.5
    info = e.info([mid])[mid]
    over = next(k for k, v in info["runners"].items() if v.lower().startswith("over"))
    cand = {"template": "football_over_wait", "sport": "football", "selection_id": over, "runner": info["runners"][over], "side": "BACK", "price": 2.0, "model_p": 0.55,
            "market_p": 0.5, "edge": 0.05, "title": "t", "reason": "r", "watch": [], "stake": 10, "max_loss": 10,
            "script": {"name": "Setup: test", "sport": "football", "description": "d", "rules": [
                {"id": "r1", "kind": "entry", "when": [{"type": "in_play", "value": True}], "then": [{"type": "back", "price": "best", "stake": 10, "basis": "stake", "persistence": "CANCEL"}]}]}}
    rec, new = e.recs.upsert_setup(mid, info, cand)
    assert new and rec["kind"] == "setup"
    assert e.recs.upsert_setup(mid, info, {**cand, "edge": 0.06})[1] is False                         # a refresh keeps the same idea
    out = e.rec_apply(rec["id"], None, 5)
    assert out["order"] is None and out["row"]["state"] == "armed" and out["row"]["stake"] == 5 and out["script"]["enabled"] is True
    assert not e.ex.open_orders() or all(o.request.source != "ai" for o in e.ex.open_orders())
    with pytest.raises(ValueError, match="applied"):
        e.rec_apply(rec["id"])
    rec2, _ = e.recs.upsert_setup(mid, info, cand)                                                    # same name again gets a distinct script
    assert e.rec_apply(rec2["id"])["script"]["name"] == "Setup: test #2"


def test_scan_produces_setups_not_winner_picks_and_expires_them_when_the_market_leaves():
    import time, datetime as dt
    start = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    tennis = {**INFO, "start": start}
    fb = {"market_id": "1.7", "event": "Home FC v Away FC", "name": "Match Odds", "start": start, "event_id": "e9", "in_play": False}

    class Feed:
        def get_books(self, ids, depth=False):
            out = []
            for i in ids:
                if i == "1.5": b = mk({"A": (2.2, 2.24), "B": (1.8, 1.82)}); b.market_id = i
                elif i == "1.6": b = ou_book((2.0, 2.02), (1.9, 1.92))
                else: b = mk({"A": (2.0, 2.02), "B": (3.0, 3.1)}); b.market_id = i
                out.append(b)
            return out

    class Eng:
        feed = Feed()
        def markets(self, sport): return [tennis] if sport == "tennis" else [fb]
        def event_markets(self, eid): return [ou_info()]
        def context_fn(self, m): return ctx(0.50) if m["market_id"] == "1.5" else {"kind": "football", "pre_model": {"over_2.5": 0.40, "mu": [1.0, 1.0]}}
    r = Recs()
    made = r.scan(Eng(), 10)
    assert sorted(x["template"] for x in made) == ["football_under_scalp", "tennis_swing_back"]
    assert all(x["kind"] == "setup" and x["confidence"] != "High" for x in made)
    assert next(x for x in made if x["template"] == "football_under_scalp")["market_id"] == "1.6"       # lives on the goals market, not Match Odds
    assert r.scan(Eng(), 10) == []                                                                    # a second pass refreshes, it does not duplicate
    assert r.stats()["counts"]["setups"] == 2
