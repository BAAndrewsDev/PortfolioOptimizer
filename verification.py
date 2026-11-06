"""Self-verification suite for the portfolio optimization backend.

The project guidelines require verification that the coded model implements
the intended formulation and that solutions satisfy the business rules.
This module provides four independent checks, runnable headless or from the
app's "Self-Verification" tab:

  1. analytic_mvp      - min-variance portfolio vs. the closed-form
                         w* = S^-1 1 / (1' S^-1 1)   (shorting allowed)
  2. three_asset       - hand-computable 3-asset instance with a diagonal
                         covariance: long-only min-variance weights are
                         proportional to 1/sigma_i^2; LP max-return goes
                         100% into the highest-return asset.
  3. data_endpoints    - on the real bundled data: LP with only budget +
                         long-only puts 100% in the highest-mean ETF;
                         every solve's weights sum to 1.
  4. risk_contrib      - risk contributions sum to 1; %-weights in [0,100].

Checks that touch the real dataset read the same CSVs the app uses, so they
verify the actual production path, not a copy of it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import gurobipy as gp
from gurobipy import GRB

import model


# ----------------------------------------------------------------------
def _gurobi_minvar(mu: np.ndarray, cov: np.ndarray,
                   long_only: bool) -> np.ndarray:
    """Solve true min-variance (budget only) and return the weight vector.

    When shorting is allowed the weights are unbounded on both sides: an
    unconstrained minimum-variance portfolio routinely contains weights
    outside [-1, 1], so artificial bounds would change the optimum.
    """
    n = len(mu)
    m = gp.Model()
    m.setParam("OutputFlag", 0)
    if long_only:
        w = m.addVars(range(n), lb=0.0, ub=GRB.INFINITY)
    else:
        w = m.addVars(range(n), lb=-GRB.INFINITY, ub=GRB.INFINITY)
    m.addConstr(gp.quicksum(w.values()) == 1.0, name="budget")
    m.setObjective(gp.quicksum(cov[i, j] * w[i] * w[j]
                               for i in range(n) for j in range(n)), GRB.MINIMIZE)
    m.optimize()
    assert m.SolCount > 0, "minvar Gurobi solve failed"
    return np.array([w[i].X for i in range(n)])


def _closed_form_mvp(cov: np.ndarray) -> np.ndarray:
    """Closed-form unconstrained min-variance portfolio (shorts allowed)."""
    inv = np.linalg.inv(cov)
    one = np.ones(len(cov))
    w = inv @ one / (one @ inv @ one)
    return w


# ----------------------------------------------------------------------
def analytic_mvp() -> tuple[bool, str]:
    """Check 1: Gurobi QP == closed-form minimum-variance portfolio."""
    rng = np.random.default_rng(7)
    n = 8
    vols = rng.uniform(0.05, 0.35, n)
    corr = rng.uniform(0.1, 0.7, (n, n))
    corr = (corr + corr.T) / 2
    np.fill_diagonal(corr, 1.0)
    cov = np.outer(vols, vols) * corr
    mu = rng.uniform(0.03, 0.15, n)

    wg = _gurobi_minvar(mu, cov, long_only=False)
    wc = _closed_form_mvp(cov)
    err = float(np.max(np.abs(wg - wc)))
    ok = err < 1e-6
    detail = (f"max |w_gurobi - w_closed_form| = {err:.2e} over n={n} assets "
              f"(shorting allowed, budget only); tolerance 1e-6")
    return ok, detail


# ----------------------------------------------------------------------
def three_asset() -> tuple[bool, str]:
    """Check 2: hand-computable 3-asset instance with diagonal covariance.

    Min-variance, long-only, budget only -> w_i = (1/s_i^2)/sum_j(1/s_j^2).
    Max-return LP, long-only, budget only -> 100% in the top-return asset.
    """
    sigma = np.array([0.05, 0.10, 0.02])
    cov = np.diag(sigma**2)
    mu = np.array([0.10, 0.12, 0.08])

    wg = _gurobi_minvar(mu, cov, long_only=True)
    expected = (1 / sigma**2) / np.sum(1 / sigma**2)

    m = gp.Model()
    m.setParam("OutputFlag", 0)
    w = m.addVars(range(3), lb=0.0, ub=1.0)
    m.addConstr(gp.quicksum(w.values()) == 1.0)
    m.setObjective(gp.quicksum(mu[i] * w[i] for i in range(3)), GRB.MAXIMIZE)
    m.optimize()
    wlp = np.array([w[i].X for i in range(3)])

    err = float(np.max(np.abs(wg - expected)))
    top = int(np.argmax(mu))
    lp_ok = bool(np.argmax(wlp) == top and abs(wlp[top] - 1.0) < 1e-9)
    ok = err < 1e-5 and lp_ok  # 1e-5: interior-point solver noise on a PD QP
    detail = (f"min-var weights vs 1/sigma^2 rule: max err {err:.2e} "
              f"(expected {np.round(expected, 4)}, got {np.round(wg, 4)}); "
              f"LP max-return -> 100% into asset {top} ({mu[top]*100:.1f}%/yr): {lp_ok}")
    return ok, detail


# ----------------------------------------------------------------------
def data_endpoints() -> tuple[bool, str]:
    """Check 3: on the production dataset, endpoints behave as theory says."""
    pd_ = model.load_data()
    tickers = pd_.tickers

    # LP with only budget + long-only: 100% into the highest-mean ETF
    res = model.solve({
        "tickers": tickers, "mode": "lp", "lambda_": 3.0, "risk_free": 4.0,
        "long_only": True, "max_single": None, "min_lowrisk": None,
        "max_equity": None, "min_dividend": None, "logic": "and",
        "max_holdings": None, "min_position": None,
    })
    top_tkr = tickers[int(np.argmax(pd_.mu))]
    ok1 = res["ok"] and len(res["weights"]) == 1 and top_tkr in res["weights"]
    w1 = res["weights"].get(top_tkr)

    # weights sum to 1 in the default scenario
    res2 = model.solve({
        "tickers": tickers, "mode": "qp", "lambda_": 3.0, "risk_free": 4.0,
        "long_only": True, "max_single": 30.0, "min_lowrisk": 40.0,
        "max_equity": 80.0, "min_dividend": 0.0, "logic": "and",
        "max_holdings": None, "min_position": None,
    })
    ok2 = res2["ok"] and abs(sum(res2["weights"].values()) - 1.0) < 1e-6

    detail = (f"highest-mean ETF = {top_tkr} (E[r]={pd_.mu[int(np.argmax(pd_.mu))]*100:.2f}%); "
              f"LP went 100% into it: {ok1} (w={w1}); default QP weights sum to 1: {ok2}")
    return ok1 and ok2, detail


# ----------------------------------------------------------------------
def risk_contrib() -> tuple[bool, str]:
    """Check 4: risk contributions sum to 1 and weights are sane."""
    pd_ = model.load_data().subset(["SPY", "QQQ", "IWM", "VXUS", "BND", "TLT", "GLD"])
    res = model.solve({
        "tickers": pd_.tickers, "mode": "qp", "lambda_": 2.0, "risk_free": 4.0,
        "long_only": True, "max_single": 30.0, "min_lowrisk": 40.0,
        "max_equity": 80.0, "min_dividend": 0.0, "logic": "and",
        "max_holdings": None, "min_position": None,
    })
    if not res["ok"]:
        return False, "solve failed"
    rc_sum = sum(res["risk_contributions"].values())
    w_ok = all(-1e-6 <= v <= 1.0 + 1e-6 for v in res["weights"].values())
    ok = abs(rc_sum - 1.0) < 1e-6 and w_ok
    detail = (f"sum(risk contributions) = {rc_sum:.8f} (expect 1.0); "
              f"all weights in [0,1]: {w_ok}")
    return ok, detail


# ----------------------------------------------------------------------
def run_all() -> tuple[list[dict], bool]:
    """Run every check; returns (rows, all_passed)."""
    rows = []
    for fn, name in [
        (analytic_mvp, "Closed-form min-variance (analytic MVP)"),
        (three_asset, "3-asset hand-computable instance"),
        (data_endpoints, "Production-data endpoint behavior"),
        (risk_contrib, "Risk contributions & weight sanity"),
    ]:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"check raised: {exc!r}"
        rows.append({"check": name, "passed": bool(ok), "detail": detail})
    return rows, all(r["passed"] for r in rows)


def to_markdown(rows: list[dict], all_ok: bool) -> str:
    lines = ["### Self-verification results", ""]
    for r in rows:
        mark = "✅ PASS" if r["passed"] else "❌ FAIL"
        lines.append(f"- **{mark}** — {r['check']}")
        lines.append(f"  - {r['detail']}")
    lines.append("")
    lines.append(f"**Overall: {'ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED'}**")
    lines.append("")
    lines.append("_These checks compare Gurobi's output against independent"
                 " closed-form math (inversion of the covariance matrix), a"
                 " hand-computable 3-asset case, and the model's own business"
                 " rules (budget = 100%, risk contributions sum to 1). They run"
                 " on the same data and code path the app uses._")
    return "\n".join(lines)


if __name__ == "__main__":
    rows, all_ok = run_all()
    for r in rows:
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['check']}\n     {r['detail']}")
    print("\nALL PASSED" if all_ok else "\nSOME FAILED")
    import sys
    sys.exit(0 if all_ok else 1)
