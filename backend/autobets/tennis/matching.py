"""Match names across sources. Betfair writes 'Jannik Sinner' or 'Sinner J'; api-tennis writes 'J. Sinner'."""
import re, unicodedata


def tokens(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return [t for t in re.sub(r"[^a-z\- ]", " ", s).replace("-", " ").split() if t]


def same_player(api_name, other_name):
    """True if 'J. Sinner' / 'Jannik Sinner' / 'Sinner J' plausibly name the same person (surname words + first initial)."""
    a, o = tokens(api_name), tokens(other_name)
    if len(o) == 1 and len(a) >= 2:             # Betfair tennis events often give the surname only: 'Paul v Halys'
        return o[0] == a[-1] or (len(a[0]) == 1 and o[0] in a[1:])
    if len(a) < 2 or len(o) < 2:
        return False
    init = a[0][0] if len(a[0]) == 1 else a[-1][0] if len(a[-1]) == 1 else a[0][0]
    sur = [t for t in a if len(t) > 1] if len(a[0]) == 1 or len(a[-1]) == 1 else a[1:]
    if not sur:
        return False
    other_sur = [t for t in o if len(t) > 1]
    if not all(t in other_sur for t in sur):
        return False
    return any(t.startswith(init) and t not in sur for t in o) or any(len(t) == 1 and t == init for t in o)


def split_event(event):
    """'Jannik Sinner v Carlos Alcaraz' -> two names; None for doubles or unparseable."""
    for sep in (" v ", " vs ", " - "):
        if sep in event:
            a, b = [x.strip() for x in event.split(sep, 1)]
            if "/" in a or "/" in b:
                return None
            return a, b
    return None
