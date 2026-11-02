import datetime as dt, json, os, subprocess, sys, sqlite3
from autobets.tennis import store

ROOT = os.path.join(os.path.dirname(__file__), "..")


def stats(pk, svc, ret, hold, rgw):
    mk = lambda t, n, wt: {"stat_period": "match", "player_key": pk, "stat_type": t, "stat_name": n, "stat_value": "x", "stat_won": wt[0], "stat_total": wt[1]}
    return [mk("Points", "Service Points Won", svc), mk("Points", "Return Points Won", ret), mk("Games", "Service games won", hold), mk("Games", "Return games won", rgw)]


def match(key, date, p1, p2, n1, n2, winner="First Player", surface="Hard", tn="Test Open"):
    return {"event_key": key, "event_date": date, "event_type_type": "Atp Singles", "event_status": "Finished", "event_winner": winner,
            "event_qualification": "False", "tournament_key": "1", "tournament_name": tn, "event_first_player": n1, "event_second_player": n2,
            "first_player_key": p1, "second_player_key": p2,
            "statistics": stats(p1, (66, 100), (38, 100), (10, 12), (3, 12)) + stats(p2, (62, 100), (34, 100), (9, 12), (2, 12))}


def test_end_to_end(tmp_path):
    t, p = str(tmp_path / "t.db"), str(tmp_path / "p.db")
    db = store.connect(t)
    for i in range(8):  # history: A and B play each other a lot, then a target match
        db.execute("INSERT INTO matches VALUES(?,?,?,?,?,?,?,?,?)", (f"h{i}", "2026-05-%02d" % (i + 1), "ATP", "1", "Hard", "Finished", 1, 1, json.dumps(match(f"h{i}", "2026-05-%02d" % (i + 1), 1, 2, "J. Sinner", "C. Alcaraz"))))
    m = match("t1", "2026-06-10", 1, 2, "J. Sinner", "C. Alcaraz")
    db.execute("INSERT INTO matches VALUES(?,?,?,?,?,?,?,?,?)", ("t1", "2026-06-10", "ATP", "1", "Hard", "Finished", 1, 1, json.dumps(m))); db.commit()
    pdb = sqlite3.connect(p)
    pdb.execute("CREATE TABLE markets(market_id TEXT PRIMARY KEY, event TEXT, competition TEXT, start TEXT, runners TEXT)")
    pdb.execute("CREATE TABLE prices(t TEXT, market_id TEXT, selection TEXT, back REAL, back_size REAL, lay REAL, lay_size REAL, last REAL, in_play INTEGER)")
    pdb.execute("INSERT INTO markets VALUES('1.9','Jannik Sinner v Carlos Alcaraz','x','2026-06-10T12:00:00Z',?)", (str({"11": "Jannik Sinner", "22": "Carlos Alcaraz"}),))
    pdb.execute("INSERT INTO prices VALUES('2026-06-10T11:00:00','1.9','11',1.8,10,1.82,10,1.8,0)")
    pdb.execute("INSERT INTO prices VALUES('2026-06-10T11:00:00','1.9','22',2.2,10,2.22,10,2.2,0)"); pdb.commit()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "tennis_backtest.py"), "--tennis-db", t, "--prices-db", p, "--min", "3"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    assert "markets matched and priced: 1" in r.stdout, r.stdout
    assert "model" in r.stdout and "market" in r.stdout
