"""MSBC 5680 Team Project (Track B) - Portfolio Optimization App.

A Gradio decision-support app around a Gurobi optimization backend
(model.py). Every solve is a fresh Gurobi call: nothing is precomputed.

Run:  python app.py   (then open the printed local URL)
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import gradio as gr

import model
import verification

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

DEFAULT_TICKERS = ["SPY", "QQQ", "IWM", "VXUS", "BND", "TLT", "HYG", "GLD", "VNQ"]
MODE_CHOICES = [
    "QP - Maximize risk-adjusted return (Markowitz)",
    "LP - Maximize expected return",
]
LOGIC_CHOICES = [
    "AND - all guidelines must hold",
    "OR - at least one of (single-ETF cap) or (defensive floor) must hold",
]


def load_meta() -> pd.DataFrame:
    return pd.read_csv(os.path.join(DATA_DIR, "etf_meta.csv")).set_index("ticker")


def universe_choices() -> list[str]:
    meta = load_meta()
    return [
        f"{t} - {meta.loc[t, 'name']} ({meta.loc[t, 'asset_class']})"
        for t in meta.index
    ]


def _ticker_of(choice: str) -> str:
    return choice.split(" - ")[0].strip()


# ----------------------------------------------------------------------
# solve handler
# ----------------------------------------------------------------------
def run_solve(sel, mode_lbl, lam, rf, long_only, cap, floor, equity, divfloor,
              logic_lbl, use_card, k, use_minpos, minpos, frontier_on):
    sel = [_ticker_of(c) for c in sel] if sel else []
    params = dict(
        tickers=sel,
        mode="qp" if mode_lbl.startswith("QP") else "lp",
        lambda_=lam, risk_free=rf, long_only=bool(long_only),
        max_single=cap, min_lowrisk=floor, max_equity=equity,
        min_dividend=divfloor,
        logic="or" if logic_lbl.startswith("OR") else "and",
        max_holdings=int(k) if use_card else None,
        min_position=minpos if use_minpos else None,
    )
    try:
        res = model.solve(params)
    except ValueError as exc:
        return (f"**⚠️ {exc}**", gr.update(value=None), gr.update(value=None),
                gr.update(value=None), gr.update(value=None), gr.update(value=None))

    # ---- status banner -------------------------------------------------
    if res["status_code"] == 2:  # Optimal
        st = [f"**Solver status: OPTIMAL** (Gurobi, "
              f"{res['model_info']['solve_time_s']}s, "
              f"{res['model_info']['vars']} vars, "
              f"{res['model_info']['binaries']} binaries)  "
              f"· mode: **{res['mode'].upper()}**"]
    elif res["ok"]:
        st = [f"**Solver status: {res['status']}** — feasible incumbent; optimality is not certified."]
    else:
        st = [f"**Solver status: {res['status']}** — no valid solution available."]
    for w_ in res.get("warnings", []):
        st.append(f"⚠️ {w_}")
    if res.get("infeasible_reasons"):
        st.append("❌ **Your rules conflict.** Gurobi's infeasibility analysis "
                  "(IIS) points at these rules:")
        for r_ in res["infeasible_reasons"]:
            st.append(f"   • {r_}")
        st.append("Try relaxing one of them (e.g. raise a cap or lower a floor).")
    if res.get("or_active") is not None:
        a_ = res["or_active"]
        active = [name for key, name in (("rule_a", "single-ETF cap"),
                                        ("rule_b", "defensive floor")) if a_[key]]
        st.append("OR policy: enforced " + " and ".join(active) +
                  ". Other branches may also hold incidentally.")
    status_md = "\n\n".join(st)

    if not res["ok"]:
        return (status_md, gr.update(value=None), gr.update(value=None),
                gr.update(value=None), gr.update(value=None),
                gr.update(value=None))

    status_md += ("\n\nReturns and risk are historical in-sample estimates, not forecasts. "
                  "Benchmarks may not satisfy your policies. Defensive is a category proxy "
                  "including bonds, gold, and real estate; it does not guarantee low risk. "
                  "In OR mode, the cost table relaxes A OR B together.")
    m = res["metrics"]
    mode_name = ("maximize expected return" if m["objective_is_return"]
                 else f"maximize E[r] − λ/2·Var, λ = {res['lambda_']}")
    metrics_df = pd.DataFrame({
        "Metric": ["Expected annual return", "Annual volatility (std dev)",
                   "Sharpe ratio (rf = %.2f%%)" % m["risk_free_pct"],
                   "Number of holdings", "Objective value",
                   "Objective meaning"],
        "Value": [
            f"{m['expected_return_pct']:.2f}%",
            f"{m['volatility_pct']:.2f}%",
            f"{m['sharpe_ratio']:.3f}",
            f"{m['num_holdings']}",
            f"{m['objective']:.6f}",
            mode_name,
        ],
    })

    # ---- weights bar + table --------------------------------------------
    meta = load_meta()
    wdf_rows = []
    for t, w_ in sorted(res["weights"].items(), key=lambda kv: -kv[1]):
        rc = res["risk_contributions"].get(t, 0.0)
        i = list(res["weights"]).index(t)
        wdf_rows.append({
            "Ticker": t, "Fund": meta.loc[t, "name"],
            "Weight %": round(w_ * 100.0, 2),
            "Risk contribution %": round(rc * 100.0, 2),
            "Asset class": meta.loc[t, "asset_class"],
        })
    weights_df = pd.DataFrame(wdf_rows)
    bar_df = weights_df.rename(columns={"Weight %": "w_pct"})[["Ticker", "w_pct"]]

    # ---- guideline cost analyzer ----------------------------------------
    cost_rows = []
    for r_ in res.get("rule_costs", []):
        cost_rows.append({
            "Rule": r_["rule"],
            "Δ Expected return (pp)": r_["d_return_pp"],
            "Δ Volatility (pp)": r_["d_vol_pp"],
            "Δ Sharpe": r_["d_sharpe"],
            "Reading": ("Removing the rule would *gain* return" if r_["d_return_pp"] > 0
                        else ("Removing the rule would *lose* return" if r_["d_return_pp"] < 0 else "No material return change")),
        })
    costs_df = pd.DataFrame(cost_rows)
    if res.get("duals") and costs_df is not None:
        dual_rows = [{"Rule": v["desc"], "Δ Expected return (pp)": np.nan,
                      "Δ Volatility (pp)": np.nan, "Δ Sharpe": np.nan,
                      "Reading": f"LP shadow price: raising this rule's level by "
                                 f"1pp changes expected return by "
                                 f"{v['pi']:+.4f} pp/yr (marginal, local to the "
                                 f"current optimum)"} for v in res["duals"].values()]
        costs_df = pd.concat([costs_df, pd.DataFrame(dual_rows)], ignore_index=True)

    # ---- frontier ---------------------------------------------------------
    if frontier_on:
        f = model.frontier(params, n_points=24)
        xy = f.get("df", pd.DataFrame())
        if len(xy):
            xy = xy.copy()
            xy = xy.rename(columns={"vol_pct": "Volatility %", "ret_pct": "Return %"})
        marks = f.get("marks")
        if marks is not None and len(marks):
            marks = marks.rename(columns={"vol_pct": "Volatility %",
                                          "ret_pct": "Return %"})
            xy = pd.concat([xy, marks], ignore_index=True)
        frontier_plot = gr.update(value=xy)
    else:
        frontier_plot = gr.update(value=None)

    return status_md, metrics_df, bar_df, weights_df, costs_df, frontier_plot


def reset_app():
    """Restore every input to its default and clear all result outputs."""
    return (
        gr.update(value=[c for c in universe_choices()
                         if _ticker_of(c) in DEFAULT_TICKERS]),
        gr.update(value=MODE_CHOICES[0]),
        gr.update(value=3.0),
        gr.update(value=4.0),
        gr.update(value=True),
        gr.update(value=30.0),
        gr.update(value=40.0),
        gr.update(value=80.0),
        gr.update(value=0.0),
        gr.update(value=LOGIC_CHOICES[0]),
        gr.update(value=True),
        gr.update(value=6),
        gr.update(value=True),
        gr.update(value=3.0),
        gr.update(value=False),
        "*Inputs restored to defaults. Press **Solve portfolio** to re-run "
        "the optimizer.",
        gr.update(value=None),   # metrics
        gr.update(value=None),   # weights bar
        gr.update(value=None),   # weights table
        gr.update(value=None),   # guideline costs
        gr.update(value=None),   # frontier
    )


def run_verification() -> str:
    rows, all_ok = verification.run_all()
    return verification.to_markdown(rows, all_ok)


# ----------------------------------------------------------------------
# layout
# ----------------------------------------------------------------------
def build_app() -> gr.Blocks:
    choices = universe_choices()

    with gr.Blocks(title="Portfolio Optimizer — MSBC 5680 Track B") as demo:
        gr.Markdown(
            "# 🧮 Portfolio Optimizer — Optimization Decision-Support App\n"
            "**MSBC 5680 Team Project (Track B)** · every solve is a fresh "
            "**Gurobi** optimization — LP, Markowitz QP, or mixed-integer QP — "
            "built on ~5 years of real ETF daily returns (bundled data).\n\n"
            "**How to use:** pick your ETF universe and risk preferences on the "
            "left, toggle the policy **guidelines** (Kathleen Allen–style rules) "
            "you want enforced, and click **Solve**. The app shows the optimal "
            "allocation, the cost of each rule, benchmarks, and — optionally — "
            "the efficient frontier."
        )

        with gr.Row():
            with gr.Column(scale=5):
                gr.Markdown("### 1 · Universe & objective")
                cg_tickers = gr.CheckboxGroup(
                    choices=choices,
                    value=[c for c in choices if _ticker_of(c) in DEFAULT_TICKERS],
                    label="ETFs available to the portfolio (5 years of daily data)",
                )
                rb_mode = gr.Radio(
                    MODE_CHOICES, value=MODE_CHOICES[0],
                    label="Optimization objective",
                    info="QP: risk-adjusted return (λ slider below). "
                         "LP: Lecture-14 style max expected return.",
                )
                sl_lambda = gr.Slider(
                    0.5, 10.0, value=3.0, step=0.1,
                    label="Risk aversion λ (QP only)",
                    info="Higher λ = more penalty on variance = more conservative.",
                )
                sl_rf = gr.Slider(
                    0.0, 8.0, value=4.0, step=0.1,
                    label="Risk-free rate (%/yr, used for Sharpe ratio)",
                )
                cb_longonly = gr.Checkbox(value=True, label="Long-only (uncheck for signed weights, each bounded -100% to 100%)")

                gr.Markdown("### 2 · Policy guidelines (rules become constraints)")
                sl_cap = gr.Slider(
                    0, 60, value=30, step=5,
                    label="Rule A — max % in any single ETF (0 = off)",
                    info="Lecture 14 diversification guideline.",
                )
                sl_floor = gr.Slider(
                    0, 90, value=40, step=5,
                    label="Rule B — min % in defensive assets, bonds + gold + real estate "
                         "(0 = off)",
                )
                sl_equity = gr.Slider(
                    50, 100, value=80, step=5,
                    label="Rule C — max % in equity ETFs (US + international) "
                         "(100 = 100% net equity limit)",
                )
                sl_div = gr.Slider(
                    0, 6, value=0, step=0.25,
                    label="Rule D — min portfolio dividend yield % (0 = off)",
                )
                rb_logic = gr.Radio(
                    LOGIC_CHOICES, value=LOGIC_CHOICES[0],
                    label="Guideline logic",
                    info="OR uses binary variables + big-M, exactly as in "
                         "Lecture 14 (either Rule A or Rule B must hold).",
                )

                with gr.Accordion("Advanced portfolio rules (binary variables / MIQP)",
                                  open=False):
                    cb_card = gr.Checkbox(
                        value=True,
                        label="Limit the number of holdings (cardinality)")
                    sl_k = gr.Slider(2, 13, value=6, step=1,
                                     label="Max number of ETFs held")
                    cb_minpos = gr.Checkbox(
                        value=True,
                        label="Enforce a minimum position size")
                    sl_minpos = gr.Slider(0.5, 20, value=3.0, step=0.5,
                                          label="Min absolute weight (%) of any holding")

                cb_frontier = gr.Checkbox(
                    value=False,
                    label="Also compute the efficient frontier "
                         "(takes a few seconds)")
                with gr.Row():
                    btn_solve = gr.Button("▶ Solve portfolio", variant="primary")
                    btn_reset = gr.Button("↺ Reset", variant="secondary")

            with gr.Column(scale=7):
                status_md = gr.Markdown("*Press Solve to run the optimizer.*")
                metrics_df = gr.Dataframe(
                    headers=["Metric", "Value"], row_count=6, label="Portfolio metrics")
                weights_df = gr.Dataframe(
                    label="Optimal allocation (sorted by weight)",
                    wrap=True)
                weights_bar = gr.BarPlot(
                    x="Ticker", y="w_pct",
                    title="Optimal weights (%)",
                    y_title="Weight (%)",
                    height=280, color="#0a7ea4")
                costs_df = gr.Dataframe(
                    label="Guideline cost analyzer — what is each rule costing you?",
                    wrap=True)
                frontier_plot = gr.ScatterPlot(
                    x="Volatility %", y="Return %", color="series",
                    title="Constrained efficient frontier",
                    x_title="Annual volatility (%)", y_title="Expected return (%)",
                    height=380)

        with gr.Tab("About · formulation · verification"):
            gr.Markdown(
                """
### Decision problem
A DIY investor (or an advisor) must allocate a budget across a menu of real
ETFs. The decision: **what weight in each fund**, trading off expected return
against risk, subject to the investor's own policy guidelines.

### Mathematical model (core)
Let `wᵢ` be the fraction invested in ETF `i`, `μ` the vector of annualized
expected returns and `Σ` the annualized covariance matrix (both estimated
from ~5 years of daily returns).

**QP (Markowitz):**  maximize `μᵀw − (λ/2)·wᵀΣw`
**LP (Lecture 14):**  maximize `μᵀw`

subject to (activated rules become constraints):
- `Σwᵢ = 1` — all capital invested
- `wᵢ ≥ 0` — long-only (optional toggle)
- Rule A: `wᵢ ≤ cap` for all i — diversification cap
- Rule B: `Σ_defensive wᵢ ≥ floor` — bonds + gold + real estate floor
- Rule C: `Σ_equity wᵢ ≤ cap_equity`
- Rule D: `Σ dᵢwᵢ ≥ div_floor` — dividend yield floor
- **OR-logic** (Lecture 14, big-M derived from weight and budget bounds):
  binaries `y₁, y₂`, `y₁+y₂ ≥ 1`, `wᵢ ≤ cap + 1·(1−y₁)`,
  `Σ_def wᵢ ≥ floor − M·(1−y₂)` (M accounts for signed exposures)
- **Advanced (MIQP):** binaries `zᵢ` with `wᵢ ≤ zᵢ` (holding flag),
  `Σzᵢ ≤ K` (cardinality). Active holdings have absolute weight at least ℓ;
  signed holdings use separate sign indicators, and z = 0 forces w = 0.

### Verification
The backend ships a self-test suite (`verification.py`): closed-form
minimum-variance portfolio vs Gurobi (analytic check), a hand-computable
3-asset instance, and production-data endpoint checks. Run it below or
headless with `python verification.py`.

### Data & assumptions
- Prices: real daily closes from Yahoo Finance (`data/fetch_data.py`),
  bundled as `data/etf_prices.csv` + `data/etf_meta.csv` so the app runs
  offline and reproducibly. Source path recorded in `data/SOURCE.txt`.
- Return/risk estimates are simple historical moments — that is the classic
  Markowitz assumption, and a stated limitation of the model (no forecasts,
  no regime adjustment). Synthetic fallback data are generated with
  plausible class-level means/vols if the live download is unavailable.

### Responsible AI use (placeholder for the team memo)
- AI used for code scaffolding, UI wiring and debugging; the model
  formulation, verification checks, and interpretation are team-owned.
- Verification is *independent of the AI's claims*: Gurobi output is
  compared against closed-form math and hand-computed cases.
"""
            )
            btn_verify = gr.Button("Run self-verification suite")
            verify_md = gr.Markdown("*Not run yet.*")

        # wire events at the end of the Blocks context: all components exist
        # by now, so cross-tab references cannot raise NameError
        btn_solve.click(
            run_solve,
            inputs=[cg_tickers, rb_mode, sl_lambda, sl_rf, cb_longonly,
                    sl_cap, sl_floor, sl_equity, sl_div, rb_logic,
                    cb_card, sl_k, cb_minpos, sl_minpos, cb_frontier],
            outputs=[status_md, metrics_df, weights_bar, weights_df,
                     costs_df, frontier_plot],
        )
        btn_reset.click(
            reset_app,
            outputs=[cg_tickers, rb_mode, sl_lambda, sl_rf, cb_longonly,
                     sl_cap, sl_floor, sl_equity, sl_div, rb_logic,
                     cb_card, sl_k, cb_minpos, sl_minpos, cb_frontier,
                     status_md, metrics_df, weights_bar, weights_df,
                     costs_df, frontier_plot],
        )
        btn_verify.click(run_verification, outputs=verify_md)
    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch(server_name="127.0.0.1", server_port=7861,
               show_error=True, prevent_thread_lock=True,
               theme=gr.themes.Soft())
    import time
    while True:
        time.sleep(3600)
