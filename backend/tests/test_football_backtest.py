import os, sys, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import football_model_backtest as bt
from autobets.football.store import FootballStore


def test_walk_forward_report():
    st = FootballStore(); base = dt.datetime(2024, 8, 1, tzinfo=dt.timezone.utc); fid = 0
    for r in range(120):
        for h in range(1, 11):
            a = (h + r) % 10 + 1
            if a == h: continue
            fid += 1
            gh, ga = (3, 0) if h == 1 else (1, 1) if h % 2 else (0, 1)
            st.db.execute("INSERT INTO fixtures(id,league_id,season,kickoff,status,home_id,home,away_id,away,goals_h,goals_a) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                          (fid, 39, 2024, (base + dt.timedelta(days=r * 4)).isoformat(), "FT", h, f"T{h}", a, f"T{a}", gh, ga))
    st.db.commit()
    rows = bt.run(st, "2025-06-01")
    assert rows and all(abs(sum(r["p"]) - 1) < 1e-9 for r in rows)
    text = bt.report(rows)
    assert "model" in text and "baseline" in text and "Premier League" in text
