"""Tunes the football model settings by walk-forward backtest, with an honest hold-out.
Stage 1: decay half-life x small-sample shrinkage (judged on 1X2 log loss). Stage 2: total-goals shrinkage (judged on over 2.5 + BTTS log loss).
Every setting is scored on an earlier 'fit' period and a later 'hold-out' period: choose by the fit column, then check the hold-out column agrees.
Usage: python3 backend/tools/football_model_tune.py [--db ...] [--since 2025-08-01] [--split 2026-01-01] [--every 2]"""
import argparse, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))
import football_model_backtest as bt
from autobets.football import model
from autobets.football.store import FootballStore


def score(rows):
    if not rows:
        return None
    a, b, l, ob, ol, bb, bl = bt.metrics(rows)
    return l, ol, bl


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--db", default="/opt/autobets/data/football.db"); ap.add_argument("--since", default="2025-08-01")
    ap.add_argument("--split", default="2026-01-01"); ap.add_argument("--every", type=int, default=2)
    a = ap.parse_args(); store = FootballStore(a.db)

    def trial(**kw):
        for k, v in kw.items(): setattr(model, k, v)
        rows = bt.run(store, a.since)[::a.every]
        return score([r for r in rows if r["ko"] < a.split]), score([r for r in rows if r["ko"] >= a.split])

    base = dict(HALF_LIFE=270.0, SHRINK=6.0, TOT_W=0.0)
    print("Stage 1: 1X2 log loss  (fit | hold-out)   lower is better")
    best = None
    for hl in (150.0, 270.0, 450.0):
        for sh in (3.0, 6.0, 12.0):
            f, h = trial(HALF_LIFE=hl, SHRINK=sh, TOT_W=0.0)
            print(f"  half-life {hl:5.0f}  shrink {sh:4.0f}   {f[0]:.4f} | {h[0]:.4f}", flush=True)
            if best is None or f[0] < best[0]: best = (f[0], hl, sh)
    _, hl, sh = best
    print(f"\nBest on fit: half-life {hl:.0f}, shrink {sh:.0f}\n\nStage 2: total goals shrinkage  (over 2.5 ll | BTTS ll, fit then hold-out; baseline over ~0.690, BTTS ~0.689)")
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        f, h = trial(HALF_LIFE=hl, SHRINK=sh, TOT_W=w)
        print(f"  total weight {w:4.2f}   fit {f[1]:.4f} | {f[2]:.4f}   hold-out {h[1]:.4f} | {h[2]:.4f}", flush=True)
    for k, v in base.items(): setattr(model, k, v)


if __name__ == "__main__":
    main()
