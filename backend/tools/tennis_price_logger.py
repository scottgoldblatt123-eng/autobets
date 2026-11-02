"""Record Betfair tennis MATCH_ODDS prices over time, for backtesting the model against the market.
Usage (server): nohup python3 backend/tools/tennis_price_logger.py --interval 60 >> /opt/autobets/data/price_logger.log 2>&1 &
Stores best back/lay (top 1) per runner each tick in /opt/autobets/data/betfair_prices.db. Read-only; places no orders.
NOTE: a delayed app key returns delayed prices, so timestamps are 'as seen', not exact market time."""
import argparse, datetime as dt, os, sqlite3, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from autobets.exchange.betfair import BetfairAdapter

DB, ENV = "/opt/autobets/data/betfair_prices.db", "/opt/autobets/secrets/betfair.env"


def connect(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS markets(market_id TEXT PRIMARY KEY, event TEXT, competition TEXT, start TEXT, runners TEXT)")
    db.execute("""CREATE TABLE IF NOT EXISTS prices(t TEXT, market_id TEXT, selection TEXT, back REAL, back_size REAL,
                  lay REAL, lay_size REAL, last REAL, in_play INTEGER)""")
    db.execute("CREATE INDEX IF NOT EXISTS ix_prices ON prices(market_id, t)")
    return db


def tick(bf, db, hours_ahead, max_markets):
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    markets = bf.list_markets("2", "MATCH_ODDS", max_results=max_markets)
    keep = []
    for m in markets:
        st = dt.datetime.fromisoformat(m["start"].replace("Z", "+00:00")).replace(tzinfo=None) if m["start"] else now
        if st <= now + dt.timedelta(hours=hours_ahead):
            keep.append(m)
            db.execute("INSERT OR REPLACE INTO markets VALUES(?,?,?,?,?)", (m["market_id"], m["event"], m["competition"], m["start"], str(m["runners"])))
    rows = 0
    for i in range(0, len(keep), 40):
        for b in bf.get_books([m["market_id"] for m in keep[i:i + 40]]):
            for sel, sb in b.selections.items():
                bk = sb.backs[0] if sb.backs else None; ly = sb.lays[0] if sb.lays else None
                db.execute("INSERT INTO prices VALUES(?,?,?,?,?,?,?,?,?)", (now.isoformat(timespec="seconds"), b.market_id, sel,
                           bk.price if bk else None, bk.size if bk else None, ly.price if ly else None, ly.size if ly else None,
                           sb.last_traded, 1 if b.in_play else 0))
                rows += 1
    db.commit()
    return len(keep), rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=60); ap.add_argument("--hours-ahead", type=float, default=12)
    ap.add_argument("--max-markets", type=int, default=200); ap.add_argument("--db", default=DB); ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.db), exist_ok=True)
    bf, db = BetfairAdapter.from_env_file(ENV), connect(a.db)
    while True:
        try:
            n, rows = tick(bf, db, a.hours_ahead, a.max_markets)
            print(dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"), f"markets={n} price_rows={rows}", flush=True)
        except Exception as e:
            print("tick error:", type(e).__name__, str(e)[:160], flush=True)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
