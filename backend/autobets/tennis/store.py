"""Raw match store for api-tennis fixtures. Raw JSON is kept verbatim so derived tables
(service/return stats, holds) can be rebuilt whenever the model definition changes.
SQLite for now (single file, on the server, never in git); the schema moves to PostgreSQL
with the main build. Table: matches(event_key PK, date, tour, surface, raw JSON)."""
import json, sqlite3

TOURS = (("challenger", "CH"), ("atp", "ATP"), ("wta", "WTA"))


def tour_of(event_type: str):
    """Map api-tennis event_type_type to ATP/WTA/CH, or None for doubles, ITF, juniors, etc."""
    t = (event_type or "").lower()
    if "double" in t or "itf" in t or "junior" in t or "boys" in t or "girls" in t or "exhibition" in t:
        return None
    for needle, code in TOURS:
        if needle in t:
            return code
    return None


def connect(path):
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS matches(
        event_key TEXT PRIMARY KEY, date TEXT, tour TEXT, tournament_key TEXT, surface TEXT,
        status TEXT, has_stats INTEGER, has_pbp INTEGER, raw TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS ix_date ON matches(date)")
    db.execute("CREATE TABLE IF NOT EXISTS tournaments(tournament_key TEXT PRIMARY KEY, name TEXT, surface TEXT, raw TEXT)")
    return db


def upsert_match(db, r, surfaces):
    tour = tour_of(r.get("event_type_type"))
    if tour is None:
        return False
    tk = str(r.get("tournament_key"))
    db.execute("INSERT OR REPLACE INTO matches VALUES(?,?,?,?,?,?,?,?,?)", (
        str(r.get("event_key")), r.get("event_date"), tour, tk, surfaces.get(tk),
        r.get("event_status"), 1 if r.get("statistics") else 0, 1 if r.get("pointbypoint") else 0,
        json.dumps(r)))
    return True
