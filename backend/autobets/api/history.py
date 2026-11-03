"""Short-lived price and volume history for the ladder: recent matched volume per price, and the price chart.

Held in memory, sampled while a market is open on screen, so it starts when the market is first opened (it is
not backfilled). The price logger's database holds the longer record."""
from __future__ import annotations

from collections import deque

SHORT_S = 60          # "short term" matched volume window
LONG_S = 300          # "long term" matched volume window
SNAP_EVERY = 2.0      # seconds between samples
CHART_KEEP_S = 3 * 3600


class Tracker:
    def __init__(self, short_s: int = SHORT_S, long_s: int = LONG_S) -> None:
        self.short_s, self.long_s = short_s, long_s
        self._snaps: dict[tuple[str, str], deque] = {}      # (t, {price: traded})  for the last long_s + a margin
        self._chart: dict[tuple[str, str], deque] = {}      # (t, ltp, best back, best lay, total traded)

    def record(self, books, now: float) -> None:
        for b in books:
            for sid, s in b.selections.items():
                key = (b.market_id, sid)
                chart = self._chart.setdefault(key, deque())
                if chart and now - chart[-1][0] < SNAP_EVERY:
                    continue
                total = round(sum(s.traded.values()), 2) if s.traded else None
                chart.append((now, s.last_traded, s.backs[0].price if s.backs else None,
                              s.lays[0].price if s.lays else None, total))
                while chart and now - chart[0][0] > CHART_KEEP_S:
                    chart.popleft()
                if s.traded:
                    snaps = self._snaps.setdefault(key, deque())
                    snaps.append((now, dict(s.traded)))
                    while snaps and now - snaps[0][0] > self.long_s + 30:
                        snaps.popleft()

    def _delta(self, key, window: float, now: float, current: dict) -> tuple[list, float]:
        snaps = self._snaps.get(key)
        if not snaps:
            return [], 0.0
        old = snaps[0]
        for s in snaps:                       # newest snapshot that is at least `window` seconds old
            if now - s[0] >= window:
                old = s
            else:
                break
        out = []
        for p, v in current.items():
            d = round(v - old[1].get(p, 0.0), 2)
            if d > 0:
                out.append([p, d])
        return sorted(out), round(now - old[0], 1)

    def recent(self, market_id: str, sid: str, current: dict, now: float) -> dict:
        key = (market_id, sid)
        short, s_span = self._delta(key, self.short_s, now, current)
        long_, l_span = self._delta(key, self.long_s, now, current)
        return {"short": short, "long": long_, "short_s": self.short_s, "long_s": self.long_s,
                "short_span": s_span, "long_span": l_span}

    def chart(self, market_id: str, sid: str, seconds: int = 900, max_points: int = 300) -> dict:
        pts = list(self._chart.get((market_id, sid), ()))
        if pts:
            cutoff = pts[-1][0] - seconds
            pts = [p for p in pts if p[0] >= cutoff]
        step = max(1, -(-len(pts) // max_points))
        pts = pts[::step] if step > 1 else pts
        out, prev = [], None
        for t, ltp, back, lay, total in pts:
            vol = 0.0 if prev is None or total is None else max(0.0, round(total - prev, 2))
            out.append([round(t, 1), ltp, back, lay, vol])
            prev = total if total is not None else prev
        return {"points": out}
