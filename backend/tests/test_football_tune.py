import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
from autobets.football import model


def test_total_shrink_keeps_ratio_and_moves_total():
    st = {"lh": 1.5, "la": 1.2, "gf": {1: [30.0, 0]}, "ga": {1: [0, 0]}, "wt": {}, "n": 1000}
    from collections import defaultdict
    st["gf"], st["ga"], st["wt"] = defaultdict(lambda: [20.0, 18.0]), defaultdict(lambda: [14.0, 12.0]), defaultdict(lambda: [10.0, 10.0])
    st["gf"][1] = [30.0, 30.0]; st["wt"][1] = [10.0, 10.0]
    model.TOT_W = 0.0
    a = model.expected_goals(st, 1, 2)
    model.TOT_W = 0.8
    try:
        b = model.expected_goals(st, 1, 2)
    finally:
        model.TOT_W = 0.0
    assert abs(a[0] / a[1] - b[0] / b[1]) < 1e-9
    assert abs((b[0] + b[1]) - 2.7) < abs((a[0] + a[1]) - 2.7)
