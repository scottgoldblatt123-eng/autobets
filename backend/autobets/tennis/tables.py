"""Per-player aggregate tables from the raw api-tennis store: the inputs of the hold model.
Everything is built from exact won/total counts (match period), so aggregates are volume-weighted,
not averages of percentages. Definitions (all over the chosen tours, surfaces and dates):
  service_pts  = service points won / service points played
  return_pts   = return points won / return points played
  hold         = service games won / service games played
  opp_hold     = opponent service games won / opponent service games played  (= 1 - own return games won %)
  bp_save, bp_conv, first_serve_in, first_w, second_w
"""
import json, re, unicodedata
from collections import defaultdict

SURFACES = {"hard": ("Hard", "Hard (Indoor)"), "clay": ("Clay", "clay", "Clay (Indoor)"), "grass": ("Grass",)}
FIELDS = {  # (stat_type, stat_name) -> key
    ("Points", "Service Points Won"): "svc", ("Points", "Return Points Won"): "ret",
    ("Games", "Service games won"): "hold", ("Games", "Return games won"): "rgw",
    ("Service", "1st serve points won"): "w1", ("Service", "2nd serve points won"): "w2",
    ("Service", "Break Points Saved"): "bps", ("Return", "Break Points Converted"): "bpc",
}


def parse_match(raw):
    """-> {player_key: {name, side, svc:(won,tot), ...}} for the 'match' period, or None if incomplete."""
    m = json.loads(raw) if isinstance(raw, str) else raw
    out = {}
    for side, nk, kk in (("first", "event_first_player", "first_player_key"), ("second", "event_second_player", "second_player_key")):
        out[str(m.get(kk))] = {"name": m.get(nk), "side": side}
    for s in m.get("statistics") or []:
        if s.get("stat_period") != "match":
            continue
        k = FIELDS.get((s.get("stat_type"), s.get("stat_name")))
        pk = str(s.get("player_key"))
        if k and pk in out and s.get("stat_total") is not None and s.get("stat_won") is not None:
            out[pk][k] = (int(s["stat_won"]), int(s["stat_total"]))
    need = ("svc", "ret", "hold", "rgw")
    if len(out) != 2 or any(k not in p for p in out.values() for k in need):
        return None
    return out


def build(db, tour, surface=None, start=None, stop=None):
    """Aggregate per player. tour 'ATP'|'WTA'|'CH'; surface 'hard'|'clay'|'grass'|None(all)."""
    q, args = "SELECT raw, surface FROM matches WHERE tour=? AND status='Finished'", [tour]
    if start: q += " AND date>=?"; args.append(start)
    if stop: q += " AND date<=?"; args.append(stop)
    acc = defaultdict(lambda: defaultdict(int)); names = {}
    used = skipped = 0
    for raw, surf in db.execute(q, args):
        if surface and surf not in SURFACES[surface]:
            continue
        p = parse_match(raw)
        if not p:
            skipped += 1; continue
        used += 1
        (a, pa), (b, pb) = p.items()
        for me, opp in ((a, b), (b, a)):
            mp, op = p[me], p[opp]; names[me] = mp["name"]; r = acc[me]
            r["n"] += 1
            for k in ("svc", "ret", "hold", "w1", "w2", "bps", "bpc"):
                if k in mp: r[k + "_w"] += mp[k][0]; r[k + "_t"] += mp[k][1]
            r["oh_w"] += op["hold"][0]; r["oh_t"] += op["hold"][1]
    rows = {}
    for pk, r in acc.items():
        pct = lambda w, t: round(100 * r[w] / r[t], 1) if r[t] else None
        rows[pk] = {"name": names[pk], "matches": r["n"], "service_pts": pct("svc_w", "svc_t"), "return_pts": pct("ret_w", "ret_t"),
                    "hold": pct("hold_w", "hold_t"), "opp_hold": pct("oh_w", "oh_t"), "bp_save": pct("bps_w", "bps_t"),
                    "bp_conv": pct("bpc_w", "bpc_t"), "first_serve_in": pct("w1_t", "svc_t") if r["w1_t"] else None,
                    "first_w": pct("w1_w", "w1_t"), "second_w": pct("w2_w", "w2_t")}
    return rows, used, skipped


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", s).split()


def match_name(api_name, full_names):
    """'J. Sinner' -> 'Jannik Sinner' using surname + first initial. Returns the full name or None when ambiguous/absent."""
    t = norm(api_name)
    if len(t) < 2:
        return None
    init, sur = t[0][0], t[-1]
    hits = [f for f in full_names if (n := norm(f)) and n[-1] == sur and n[0].startswith(init)]
    if not hits:  # compound surnames: compare last two tokens of the long name
        hits = [f for f in full_names if (n := norm(f)) and sur in n[1:] and n[0].startswith(init)]
    return hits[0] if len(hits) == 1 else None
