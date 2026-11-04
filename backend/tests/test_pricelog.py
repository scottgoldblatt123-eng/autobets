import threading
from types import SimpleNamespace as NS
from autobets.pricelog import PriceLogger, PriceStore


def book(mid, back, lay, in_play=False):
    return NS(market_id=mid, in_play=in_play, status="OPEN", selections={"1": NS(backs=[NS(price=back)], lays=[NS(price=lay)]), "2": NS(backs=[], lays=[])})


class Eng:
    lock = threading.RLock()
    def __init__(self): self.b = book("1.1", 2.0, 2.02); self.feed = NS(get_books=lambda ids: [self.b])
    def markets(self, sport): return [{"market_id": "1.1", "event": "A v B", "start": "2026-11-05T10:00:00Z", "runners": {"1": "A", "2": "B"}}] if sport == "tennis" else []


class Ctx:
    score = {"kind": "tennis", "sets": [["6", "4"]], "live": True, "junk": 1}
    def for_market(self, m): return self.score


def test_logs_only_changes_and_slims_context():
    eng, st = Eng(), PriceStore()
    lg = PriceLogger(eng, Ctx(), st, now=lambda: 1000.0)
    assert lg.once() is False and st.counts()["ticks"] == 1
    lg.once(); assert st.counts()["ticks"] == 1                         # nothing changed: nothing stored
    eng.b = book("1.1", 2.04, 2.06, in_play=True)
    assert lg.once() is True and st.counts()["ticks"] == 2 and st.counts()["in_play_ticks"] == 1
    assert "junk" not in st.db.execute("SELECT ctx FROM ticks").fetchone()[0]
    Ctx.score = {**Ctx.score, "sets": [["6", "4"], ["1", "0"]]}
    lg.once(); assert st.counts()["ticks"] == 3                         # a score change alone is recorded
