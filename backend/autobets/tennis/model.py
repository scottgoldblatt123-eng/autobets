"""Hold model v1 ('sheet'): a faithful port of the Sheet1 logic of the WTA Model workbook.

  adj_service_pts(A) = service_pts(A) + (avg_return_pts - return_pts(B))            [informational]
  proj_hold(A)       = hold(A) + (opp_hold(B) - avg_opp_hold)
  P(A) %             = 50 * (1 + (proj_hold(A) - proj_hold(B)) / proj_hold(B));  P(B) = 100 - P(A)
  odds               = 100 / P
Tour averages are unweighted means over the players in the table, as in the workbook. Improvements
(shrinkage of small samples, recency, calibration) are separate model versions, compared by backtest."""
from dataclasses import dataclass

VERSION = "v1-sheet"


@dataclass(frozen=True)
class Averages:
    return_pts: float
    opp_hold: float


def tour_averages(rows, min_matches=1):
    """Unweighted means over players (the workbook's AVERAGE of the column)."""
    r = [x for x in rows.values() if x["matches"] >= min_matches and x["return_pts"] is not None and x["opp_hold"] is not None]
    return Averages(sum(x["return_pts"] for x in r) / len(r), sum(x["opp_hold"] for x in r) / len(r))


def projected_hold(a, b, avg):
    return a["hold"] + (b["opp_hold"] - avg.opp_hold)


def adj_service_pts(a, b, avg):
    return a["service_pts"] + (avg.return_pts - b["return_pts"])


def price(a, b, avg):
    """-> dict with projected holds, win probability % and fair odds for A and B."""
    ga, gb = projected_hold(a, b, avg), projected_hold(b, a, avg)
    pa = 50 * (1 + (ga - gb) / gb)
    pb = 100 - pa
    return {"hold_a": ga, "hold_b": gb, "p_a": pa, "p_b": pb, "odds_a": 100 / pa, "odds_b": 100 / pb, "version": VERSION}
