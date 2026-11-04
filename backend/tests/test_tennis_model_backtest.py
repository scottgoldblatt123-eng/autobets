import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import tennis_model_backtest as bt
from autobets.tennis.livestore import TennisStore
from test_tennis_ratings import match


def test_walk_forward_scores_without_lookahead():
    st = TennisStore(); i = 0
    for k in range(3, 43):                               # 40 filler players with a long history
        for j in range(8):
            i += 1; st.upsert(match(i, f"2025-0{1 + j}-1{j}", k, k + 100, (60, 40, 9, 5), (60, 40, 9, 5)))
    for j in range(8):                                   # strong player 1 beats weak player 2 monthly
        i += 1; st.upsert(match(i, f"2025-0{1 + j}-20", 1, 2, (68, 46, 11, 8), (55, 34, 4, 1)))
    i += 1; st.upsert(match(i, "2025-09-25", 1, 2, (68, 46, 11, 8), (55, 34, 4, 1)))
    res = bt.run(st, "2025-09-01")
    assert res and all(len(r) == 4 for r in res)
    final = [r for r in res if r[3] == 1][-1]
    assert final[2] > 0.7                                # v2 favours the player who has been dominating
    assert "v2 point model" in bt.report(res)
