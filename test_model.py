"""Headless smoke tests for the portfolio backend (no UI)."""
import sys
import model

BASE = {
    "tickers": ["SPY", "QQQ", "IWM", "VXUS", "BND", "TLT", "GLD", "VNQ"],
    "mode": "qp", "lambda_": 3.0, "risk_free": 4.0, "long_only": True,
    "max_single": 30.0, "min_lowrisk": 40.0, "max_equity": 80.0,
    "min_dividend": 0.0, "logic": "and",
    "max_holdings": None, "min_position": None,
}


def show(name, res):
    m = res["metrics"]
    ws = dict(sorted(res["weights"].items(), key=lambda kv: -kv[1]))
    line = (f"[{name}] status={res['status']} | E[r]={m.get('expected_return_pct', float('nan')):.2f}% "
            f"| vol={m.get('volatility_pct', float('nan')):.2f}% | Sharpe={m.get('sharpe_ratio', float('nan')):.2f} "
            f"| holdings={m.get('num_holdings','-')} | time={res['model_info'].get('solve_time_s')}s "
            f"| bin={res['model_info'].get('binaries', '-')}")
    print(line)
    print("    weights:", ", ".join(f"{t}={v*100:.1f}%" for t, v in list(ws.items())[:8]))
    if res.get("infeasible_reasons"):
        print("    INFEASIBLE reasons:", res["infeasible_reasons"])
    if res.get("rule_costs"):
        for r in res["rule_costs"][:3]:
            print(f"    cost[{r['rule']}]: dE={r['d_return_pp']:+.3f}pp dVol={r['d_vol_pp']:+.3f}pp dSharpe={r['d_sharpe']:+.4f}")
    if res.get("duals"):
        for nm, d in list(res["duals"].items())[:4]:
            print(f"    dual[{nm}] = {d['pi']:+.4f} ({d['desc'][:50]})")
    if res.get("benchmarks"):
        for k, b in res["benchmarks"].items():
            print(f"    bench[{k}]: E={b['ret_pct']:.2f}% vol={b['vol_pct']:.2f}% "
                  f"Sharpe={b['sharpe']:.2f}")


def main():
    # 1. QP baseline
    show("QP default", model.solve(BASE))

    # 2. LP max return
    p = dict(BASE, mode="lp")
    show("LP max-return", model.solve(p))

    # 3. MIQP: cardinality K=5, min position 5%
    p = dict(BASE, max_holdings=5, min_position=5.0)
    show("MIQP K=5,min5%", model.solve(p))

    # 4. OR logic (either cap or floor)
    p = dict(BASE, logic="or")
    res = model.solve(p)
    show("OR-logic", res)
    assert "or_active" in res, "or_active missing"
    print("    or_active:", res["or_active"])

    # 5. Infeasible: cap 10% x equity 90% floor 70%? -> cap 10% + floor 60%
    p = dict(BASE, max_single=10.0, min_lowrisk=60.0, max_equity=70.0)
    res = model.solve(p)
    show("infeasible-ish", res)
    print("    reasons:", res["infeasible_reasons"])

    # 6. Frontier sanity
    f = model.frontier(BASE, n_points=12)
    print("[frontier] rows:", len(f["df"]), "series:", f["df"]["series"].unique().tolist() if len(f["df"]) else "-")
    print("[frontier] marks:", f["marks"][["vol_pct", "ret_pct", "series"]].to_string(index=False)
          if f["marks"] is not None else "none")

    # 7. LP duals present?
    res = model.solve(dict(BASE, mode="lp"))
    print("[lp duals]", {k: round(v["pi"], 4) for k, v in res["duals"].items()})


if __name__ == "__main__":
    sys.exit(main())
