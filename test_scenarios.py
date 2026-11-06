"""Scenario tests through the LIVE app API. Captures the exact numbers the
demo script will quote. Scenarios:

  S1  base case (shipped defaults), frontier ON
  S2  aggressive growth policy (lower aversion, looser rules)
  S3  conflicting rules -> infeasible (IIS diagnostic)
  S3b same conflicting rules but OR-logic (big-M waiver)
  S4  LP mode with duals (marginal values of each rule)
"""
import json
import pandas as pd
from gradio_client import Client

URL = "http://127.0.0.1:7861"
meta = pd.read_csv("data/etf_meta.csv").set_index("ticker")
DEFAULT = ["SPY", "QQQ", "IWM", "VXUS", "BND", "TLT", "HYG", "GLD", "VNQ"]
def choice(t):
    return f"{t} - {meta.loc[t, 'name']} ({meta.loc[t, 'asset_class']})"

QP = "QP - Maximize risk-adjusted return (Markowitz)"
LP = "LP - Maximize expected return"
AND = "AND - all guidelines must hold"
OR = "OR - at least one of (single-ETF cap) or (defensive floor) must hold"

def run(sel, mode, lam, rf, long_only, cap, floor, equity, div, logic,
        use_card, k, use_minpos, minpos, frontier):
    c = Client(URL, verbose=False)
    return c.predict(
        [choice(t) for t in sel], mode, lam, rf, long_only,
        cap, floor, equity, div, logic,
        use_card, k, use_minpos, minpos, frontier,
        api_name="/run_solve")

def clean(v):
    if isinstance(v, dict) and "value" in v and isinstance(v["value"], dict):
        v = v["value"]
    if isinstance(v, dict) and "data" in v and "headers" in v:
        return v["data"]
    return v

def show(tag, out):
    status, metrics, bar, weights, costs, frontier = out
    print(f"\n===== {tag} =====")
    print("STATUS:", str(status).replace("\n", " | ")[:400])
    m = clean(metrics)
    print("METRICS:", json.dumps(m))
    w = clean(weights)
    print("WEIGHTS:", json.dumps(w[:6]))
    co = clean(costs)
    print("COSTS:", json.dumps(co[:6]))
    fb = clean(frontier) if isinstance(frontier, dict) else None
    if fb:
        print("FRONTIER rows:", len(fb))

if __name__ == "__main__":
    # S1 base case
    show("S1 base (frontier ON)",
         run(DEFAULT, QP, 3.0, 4.0, True, 30.0, 40.0, 80.0, 0.0, AND,
             True, 6, True, 3.0, True))
    # S2 aggressive
    show("S2 aggressive (lam=1.5, cap=50, floor=20, equity=100, K=8)",
         run(DEFAULT, QP, 1.5, 4.0, True, 50.0, 20.0, 100.0, 0.0, AND,
             True, 8, True, 3.0, False))
    # S3 conflicting
    show("S3 conflict (cap=10, floor=60, equity=70)",
         run(DEFAULT, QP, 3.0, 4.0, True, 10.0, 60.0, 70.0, 0.0, AND,
             True, 8, True, 3.0, False))
    # S3b OR rescue
    show("S3b same conflict but OR-logic",
         run(DEFAULT, QP, 3.0, 4.0, True, 10.0, 60.0, 70.0, 0.0, OR,
             True, 8, True, 3.0, False))
    # S4 LP duals (advanced rules OFF so duals appear)
    show("S4 LP duals (cap=30, floor=40, equity=80, no K/minpos)",
         run(DEFAULT, LP, 3.0, 4.0, True, 30.0, 40.0, 80.0, 0.0, AND,
             False, 6, False, 3.0, False))
