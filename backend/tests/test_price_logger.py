import sys, os, sqlite3, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from autobets.domain import MarketBook, SelectionBook, PriceLevel
import tennis_price_logger as pl


class Fake:
    def list_markets(self, *a, **k):
        soon = (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=1)).isoformat() + "Z"
        late = (dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(hours=40)).isoformat() + "Z"
        return [{"market_id": "1.1", "event": "A v B", "competition": "X", "start": soon, "runners": {"1": "A", "2": "B"}},
                {"market_id": "1.2", "event": "C v D", "competition": "X", "start": late, "runners": {"3": "C", "4": "D"}}]

    def get_books(self, ids):
        b = MarketBook("1.1", in_play=False)
        b.selections["1"] = SelectionBook("1", backs=[PriceLevel(1.9, 100)], lays=[PriceLevel(1.92, 50)], last_traded=1.9)
        b.selections["2"] = SelectionBook("2", backs=[], lays=[], last_traded=None)
        return [b]


def test_tick_logs_only_markets_inside_window():
    db = pl.connect(":memory:")
    n, rows = pl.tick(Fake(), db, hours_ahead=12, max_markets=50)
    assert (n, rows) == (1, 2)
    assert db.execute("select count(*) from markets").fetchone()[0] == 1
    assert db.execute("select back, lay from prices where selection='1'").fetchone() == (1.9, 1.92)
