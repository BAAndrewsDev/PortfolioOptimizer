"""End-to-end API test: drives the running Gradio app exactly as the UI does."""
import sys, json
import pandas as pd

from gradio_client import Client, handle_file

URL = "http://127.0.0.1:7861"
meta = pd.read_csv("data/etf_meta.csv").set_index("ticker")
DEFAULT = ["SPY", "QQQ", "IWM", "VXUS", "BND", "TLT", "HYG", "GLD", "VNQ"]
def choice(t):
    return f"{t} - {meta.loc[t, 'name']} ({meta.loc[t, 'asset_class']})"

def as_df(d):
    if isinstance(d, dict):
        return pd.DataFrame(d["data"], columns=d["headers"])
    return d


def main():
    c = Client(URL, verbose=False)

    sel = [choice(t) for t in DEFAULT]
    # order must match the inputs list in app.py
    args = dict(
        sel=sel,
        mode_lbl="QP - Maximize risk-adjusted return (Markowitz)",
        lam=3.0, rf=4.0, long_only=True,
        cap=30.0, floor=40.0, equity=80.0, divfloor=0.0,
        logic_lbl="AND - all guidelines must hold",
        use_card=True, k=6, use_minpos=True, minpos=3.0,
        frontier_on=True,
    )
    out = c.predict(*args.values(), api_name="/run_solve")
    status, metrics_df, weights_bar, weights_df, costs_df, frontier = out
    metrics_df = as_df(metrics_df)
    weights_df = as_df(weights_df)
    costs_df = as_df(costs_df)
    print("\n--- status banner ---\n", status[:400])
    print("\n--- metrics ---\n", metrics_df.to_string(index=False))
    print("\n--- weights table ---\n", weights_df.to_string(index=False))
    print("\n--- costs rows:", len(costs_df), "cols:", list(costs_df.columns)[:5])
    print(costs_df.to_string(index=False)[:600])
    fb = frontier if isinstance(frontier, dict) else {}
    fb = fb.get("value", fb) if isinstance(fb, dict) else fb
    print("\n--- frontier: rows =", len(fb.get("data", [])),
          "series =", sorted({r[2] for r in fb.get("data", [])}))

    # second call: LP mode + OR logic + infeasible combo
    args["mode_lbl"] = "LP - Maximize expected return"
    args["logic_lbl"] = "OR - at least one of (single-ETF cap) or (defensive floor) must hold"
    args["frontier_on"] = False
    out2 = c.predict(*args.values(), api_name="/run_solve")
    print("\n--- LP+OR status ---\n", out2[0][:300])

    args["cap"] = 10.0; args["floor"] = 60.0; args["equity"] = 70.0
    args["logic_lbl"] = "AND - all guidelines must hold"
    out3 = c.predict(*args.values(), api_name="/run_solve")
    print("\n--- infeasible status ---\n", out3[0][:500])

    vout = c.predict(api_name="/run_verification")
    print("\n--- verification output (first 300) ---\n", str(vout)[:300])
    print("\nE2E OK")

if __name__ == "__main__":
    sys.exit(main())
