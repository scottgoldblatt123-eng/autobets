import datetime as dt
import pytest
from autobets.football import model as m
from autobets.football.store import FootballStore


def test_price_sums_and_symmetry():
    r = m.price(1.5, 1.5)
    assert r["home"] + r["draw"] + r["away"] == pytest.approx(1)
    assert r["home"] == pytest.approx(r["away"], abs=1e-9)
    assert m.price(2.0, 0.8)["home"] > 0.6 and m.price(1.5, 1.2)["over_2.5"] > m.price(1.0, 0.8)["over_2.5"]
    assert 0 < m.price(1.4, 1.1)["btts"] < 1


def test_strong_home_team_priced_shorter():
    st = FootballStore(); base = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc); fid = 0
    for r in range(40):                                  # 10 teams round-robin-ish; team 1 scores 3 at home and concedes 0
        for h in range(1, 11):
            a = (h + r) % 10 + 1
            if a == h: continue
            fid += 1
            gh, ga = (3, 0) if h == 1 else (1, 1)
            st.db.execute("INSERT INTO fixtures(id,league_id,season,kickoff,status,home_id,home,away_id,away,goals_h,goals_a) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                          (fid, 39, 2025, (base + dt.timedelta(days=r)).isoformat(), "FT", h, f"T{h}", a, f"T{a}", gh, ga))
    st.db.commit()
    r = m.predict(st.db, st.lock, 39, "2026-06-01T15:00:00+00:00", 1, 2)
    assert r and r["home"] > 0.55 and r["version"] == m.VERSION
    assert m.predict(st.db, st.lock, 39, "2026-06-01T15:00:00+00:00", 1, 99) is None
