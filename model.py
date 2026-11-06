"""Optimization backend for the Track B portfolio decision-support app.

Three model classes are implemented, all solved fresh with Gurobi on every
call (nothing is precomputed or hard-coded):

  LP   - maximize expected portfolio return          (Lecture 14 style)
  QP   - maximize mean - (lambda/2) * variance         (Markowitz, Lect. 19)
  MIP  - the QP/LP objective plus binary variables for
         cardinality (at most K holdings), minimum position
         sizes, and the Lecture 14 "either guideline A or B"
         big-M logical constraint.

Policy guidelines (Kathleen Allen-style rules) become plain linear
constraints; every rule can be turned on/off by the app user:

  A. cap        w_i <= cap                       (no more than X% in one ETF)
  B. lowrisk    sum_defensive w >= floor         (at least X% defensive)
  C. equitycap  sum_equity     w <= cap_equity   (no more than X% equity)
  D. dividend   sum d_i w_i    >= div_floor      (dividend yield floor)
  OR-logic      either (A) or (B) must hold -> binaries y1,y2, y1+y2 >= 1
                 w_i <= cap + 1*(1-y1) ;  sum_def w >= floor - 1*(1-y2)

Infeasible models are diagnosed with Gurobi's IIS (irreducible infeasible
subsystem) so the app can tell the user WHICH rules conflict. For LP/QP
solves the duals of the guideline constraints are also returned, powering
the "Guideline Cost Analyzer" marginal-value table.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import gurobipy as gp
from gurobipy import GRB

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

STATUS_LABEL = {
    GRB.OPTIMAL: "Optimal",
    GRB.INFEASIBLE: "Infeasible",
    GRB.UNBOUNDED: "Unbounded",
    GRB.INF_OR_UNBD: "Infeasible or unbounded",
    GRB.TIME_LIMIT: "Time limit reached (suboptimal)",
    GRB.INTERRUPTED: "Interrupted",
    GRB.USER_OBJ_LIMIT: "Objective limit reached",
}


# ----------------------------------------------------------------------
# data
# ----------------------------------------------------------------------
class PortfolioData:
    """Loads the bundled ETF dataset once and exposes annualized moments."""

    def __init__(self) -> None:
        prices = pd.read_csv(os.path.join(DATA_DIR, "etf_prices.csv"),
                             index_col=0, parse_dates=True)
        meta = pd.read_csv(os.path.join(DATA_DIR, "etf_meta.csv"))
        rets = prices.pct_change().dropna()
        self.tickers = list(rets.columns)
        self.mu = rets.mean().values * 252.0                    # annualized
        self.cov = rets.cov().values * 252.0                    # annualized
        self.meta = meta.set_index("ticker").loc[self.tickers]

    def subset(self, tickers: list[str]) -> "PortfolioData":
        """Return a view restricted to the selected tickers."""
        new = object.__new__(PortfolioData)
        new.tickers = list(tickers)
        idx = [self.tickers.index(t) for t in tickers]
        new.mu = self.mu[idx]
        new.cov = self.cov[np.ix_(idx, idx)]
        new.meta = self.meta.loc[tickers]
        return new


def load_data() -> PortfolioData:
    return PortfolioData()


# ----------------------------------------------------------------------
# parameter cleaning
# ----------------------------------------------------------------------
def clean_params(p: dict) -> tuple[dict, list[str]]:
    """Validate/normalize user inputs; returns (params, warnings)."""
    p = dict(p)
    warn: list[str] = []
    tickers = [t for t in p.get("tickers", [])]
    if len(tickers) < 2:
        raise ValueError("Select at least 2 ETFs to optimize.")
    n = len(tickers)

    def pct(key: str, default: float | None) -> float | None:
        v = p.get(key, default)
        if v is None:
            return None
        try:
            v = float(v) / 100.0
        except (TypeError, ValueError):
            return None
        if v <= 0 or v >= 1.001:
            return None  # slider set to 0 / off
        return float(np.clip(v, 0.0, 1.0))

    p["max_single"] = pct("max_single", 0.30)
    p["min_lowrisk"] = pct("min_lowrisk", 0.40)
    p["max_equity"] = pct("max_equity", 0.80)
    p["min_dividend"] = pct("min_dividend", 0.0)

    p["long_only"] = bool(p.get("long_only", True))
    p["logic"] = "or" if p.get("logic") == "or" else "and"

    k = p.get("max_holdings")
    p["max_holdings"] = None if not k else max(1, min(int(k), n))
    lp_ = p.get("min_position")
    p["min_position"] = None if not lp_ else max(0.0, min(float(lp_) / 100.0, 1.0))

    if p["max_holdings"] and p["max_holdings"] >= n:
        p["max_holdings"] = None

    if p.get("risk_free") is not None:
        p["risk_free"] = float(np.clip(p["risk_free"] / 100.0, 0.0, 0.20))
    if p.get("lambda_") is not None:
        p["lambda_"] = max(0.0, float(p["lambda_"]))
    return p, warn


# ----------------------------------------------------------------------
# model builder
# ----------------------------------------------------------------------
def _build_model(pd_: PortfolioData, p: dict):
    """Construct the Gurobi model for cleaned params.

    Returns (model, w, z, y, name_map) where name_map translates Gurobi
    constraint names to friendly rule descriptions.
    """
    tickers = pd_.tickers
    n = len(tickers)
    mu = pd_.mu
    cov = pd_.cov
    meta = pd_.meta
    m = gp.Model("portfolio")
    m.setParam("OutputFlag", 0)
    m.setParam("TimeLimit", p.get("time_limit", 20.0))
    m.setParam("MIPGap", 0.001)

    lb = 0.0 if p["long_only"] else -1.0
    w = m.addVars(tickers, lb=lb, ub=1.0, name="w")
    z: dict = {}
    y: dict = {}
    name_map: dict[str, str] = {
        "budget": "All capital is invested (weights sum to 100%)",
    }

    # --- objective -----------------------------------------------------
    linear = gp.quicksum(mu[i] * w[t] for i, t in enumerate(tickers))
    if p["mode"] == "lp":
        obj = linear
    else:
        quad = gp.quicksum(cov[i, j] * w[tickers[i]] * w[tickers[j]]
                           for i in range(n) for j in range(n))
        obj = linear - 0.5 * p["lambda_"] * quad
    m.setObjective(obj, GRB.MAXIMIZE)

    # --- structural constraints ----------------------------------------
    m.addConstr(gp.quicksum(w.values()) == 1.0, name="budget")

    def rule_desc(key: str, pct: float | None) -> None:
        """Register IIS/dual-friendly descriptions for rule constraints."""
        if pct is None:
            return
        base = {
            "cap": f"Rule A: no more than {pct*100:.0f}% in a single ETF",
            "lowrisk": f"Rule B: at least {pct*100:.0f}% in defensive assets "
                       f"(bonds + gold + real estate; category proxy, not a risk guarantee)",
            "equitycap": f"Rule C: no more than {pct*100:.0f}% in equity ETFs",
            "dividend": f"Rule D: dividend yield at least {pct*100:.1f}%",
        }[key]
        name_map[key] = base

    cap = p["max_single"]
    floor = p["min_lowrisk"]
    eqcap = p["max_equity"]
    divfloor = p["min_dividend"]

    if p["logic"] == "or" and cap is not None and floor is not None:
        # Lecture 14 big-M logical constraint: at least one of rules A/B.
        # Cap waiver needs M=1; defensive waiver uses a signed-exposure bound.
        y["a"] = m.addVar(vtype=GRB.BINARY, name="y_a")
        y["b"] = m.addVar(vtype=GRB.BINARY, name="y_b")
        m.addConstr(y["a"] + y["b"] >= 1, name="or_logic")
        m.addConstrs((w[t] <= cap + 1.0 * (1 - y["a"]) for t in tickers), name="or_cap")
        defensive = meta.loc[tickers, "defensive"].to_numpy()
        # Bound defensive net exposure using both individual bounds and budget.
        nd = int(defensive.sum())
        min_defensive = max(nd * lb, 1.0 - (n - nd))
        big_m = max(0.0, floor - min_defensive)
        m.addConstr(defensive @ [w[t] for t in tickers]
                    >= floor - big_m * (1 - y["b"]), name="or_floor")
        name_map["or_logic"] = ("OR-logic: at least one of Rule A (single-ETF cap) "
                                "or Rule B (defensive floor) must hold")
        name_map["or_cap"] = "OR-logic branch: Rule A (single-ETF cap)"
        name_map["or_floor"] = "OR-logic branch: Rule B (defensive floor)"
    else:
        if cap is not None:
            rule_desc("cap", cap)
            m.addConstrs((w[t] <= cap for t in tickers), name="cap")
        if floor is not None:
            rule_desc("lowrisk", floor)
            m.addConstr(meta.loc[tickers, "defensive"].to_numpy() @ [w[t] for t in tickers]
                        >= floor, name="lowrisk")

    if eqcap is not None:
        rule_desc("equitycap", eqcap)
        eq_idx = [t for t in tickers if meta.loc[t, "asset_class"] in
                  {"US Equity", "International"}]
        if eq_idx:
            m.addConstr(gp.quicksum(w[t] for t in eq_idx) <= eqcap, name="equitycap")

    if divfloor is not None:
        rule_desc("dividend", divfloor)
        d = meta.loc[tickers, "div_yield_pct"].to_numpy() / 100.0
        m.addConstr(d @ [w[t] for t in tickers] >= divfloor, name="dividend")

    # --- MIP portfolio rules -------------------------------------------
    uses_bin = bool(y)
    k = p["max_holdings"]
    lp_ = p["min_position"]
    if k is not None or lp_ is not None:
        uses_bin = True
        z = m.addVars(tickers, vtype=GRB.BINARY, name="z")
        m.addConstrs((w[t] <= z[t] for t in tickers), name="card_link")
        m.addConstrs((w[t] >= lb * z[t] for t in tickers), name="holding_lower")
    if k is not None:
        m.addConstr(gp.quicksum(z.values()) <= k, name="cardinality")
        name_map["cardinality"] = f"Advanced: hold at most {k} ETFs"
        name_map["card_link"] = "Advanced: holding flag links to weight"
    if lp_ is not None:
        uses_bin = True
        if p["long_only"]:
            m.addConstrs((w[t] >= lp_ * z[t] for t in tickers), name="minpos_link")
        else:
            positive = m.addVars(tickers, vtype=GRB.BINARY, name="positive")
            negative = m.addVars(tickers, vtype=GRB.BINARY, name="negative")
            m.addConstrs((positive[t] + negative[t] == z[t] for t in tickers))
            m.addConstrs((w[t] >= lp_ * positive[t] - negative[t] for t in tickers))
            m.addConstrs((w[t] <= positive[t] - lp_ * negative[t] for t in tickers))
        name_map["minpos_link"] = f"Advanced: each holding at least {lp_*100:.1f}%"

    m.update()
    return m, w, z, y, name_map, uses_bin


# ----------------------------------------------------------------------
# solving
# ----------------------------------------------------------------------
def _friendly_iis(m: gp.Model, name_map: dict[str, str]) -> list[str]:
    """Return human-readable list of conflicting rule descriptions."""
    names = [c.getAttr("ConstrName") for c in m.getConstrs() if c.getAttr("IISConstr")]
    seen: list[str] = []
    for nm in names:
        desc = name_map.get(nm, nm)
        if nm.startswith("cap") and nm != "cap":
            desc = name_map.get("cap", "single-ETF cap rule")
        if desc not in seen:
            seen.append(desc)
    return seen


def solve(params: dict) -> dict:
    """Solve one portfolio instance; returns a JSON-ish result dict."""
    p, warn = clean_params(params)
    pd_ = load_data().subset(p.get("tickers"))
    m, w, z, y, name_map, uses_bin = _build_model(pd_, p)

    out: dict = {
        "ok": False, "status": "", "status_code": None,
        "weights": {}, "metrics": {}, "risk_contributions": {},
        "duals": {}, "rule_costs": [], "benchmarks": {},
        "model_info": {}, "warnings": warn, "infeasible_reasons": [],
        "mode": p["mode"], "lambda_": p.get("lambda_"),
        "logic": p["logic"],
    }

    # benchmarks (independent of the optimized solution)
    out["benchmarks"] = _benchmarks(pd_, p)

    m.optimize()
    out["status_code"] = m.Status
    out["status"] = STATUS_LABEL.get(m.Status, f"Status {m.Status}")
    out["model_info"] = {
        "vars": m.NumVars, "binaries": int(m.NumBinVars),
        "constraints": m.NumConstrs, "solve_time_s": round(m.Runtime, 3),
        "mip_gap_pct": None if (m.SolCount == 0 or not uses_bin) else
        round(m.MIPGap * 100.0, 3),
    }
    if m.SolCount == 0:
        reasons: list[str] = []
        try:
            m.computeIIS()
            reasons = _friendly_iis(m, name_map)
        except Exception:  # noqa: BLE001 - IIS can fail on some statuses
            reasons = []
        out["infeasible_reasons"] = reasons
        return out

    tickers = pd_.tickers
    mu, cov = pd_.mu, pd_.cov
    wgt = np.array([w[t].X for t in tickers])

    # --- metrics --------------------------------------------------------
    ret = float(wgt @ mu)
    var = float(wgt @ cov @ wgt)
    vol = float(np.sqrt(max(var, 0.0)))
    rf = p.get("risk_free", 0.04)
    sharpe = (ret - rf) / vol if vol > 1e-12 else float("nan")
    holdings = {t: round(wgt[i], 6) for i, t in enumerate(tickers) if abs(wgt[i]) > 1e-5}
    out["weights"] = holdings
    out["metrics"] = {
        "expected_return_pct": ret * 100.0,
        "volatility_pct": vol * 100.0,
        "sharpe_ratio": sharpe,
        "num_holdings": len(holdings),
        "objective": float(m.ObjVal),
        "objective_is_return": p["mode"] == "lp",
        "risk_free_pct": rf * 100.0,
    }

    # risk contributions (sum to ~1)
    rc = (wgt * (cov @ wgt)) / (var if var > 1e-12 else 1.0)
    out["risk_contributions"] = {t: float(rc[i]) for i, t in enumerate(tickers)}

    # duals of guideline constraints (LP/QP only, no binaries, no OR logic)
    if not uses_bin and p["logic"] != "or" and p["mode"] in ("lp", "qp"):
        for c in m.getConstrs():
            nm = c.getAttr("ConstrName")
            if nm in name_map and nm != "budget" and abs(c.Pi) > 1e-9:
                out["duals"][nm] = {
                    "desc": name_map[nm],
                    "pi": float(c.Pi),  # per unit (100pp) of RHS relaxation
                }

    # guideline cost analyzer: re-solve with each enabled rule relaxed
    out["rule_costs"] = _rule_costs(pd_, p, out)

    # the OR-logic winners, when used
    if y:
        out["or_active"] = {
            "rule_a": bool(y["a"].X > 0.5), "rule_b": bool(y["b"].X > 0.5),
        }
        out["duals"] = {}

    out["ok"] = True
    return out


def _rule_costs(pd_: PortfolioData, p: dict, base: dict) -> list[dict]:
    """Re-solve with each active rule relaxed; report deltas vs baseline."""
    rows: list[dict] = []
    rules = [
        ("max_single", "Rule A: single-ETF cap"),
        ("min_lowrisk", "Rule B: defensive floor"),
        ("max_equity", "Rule C: equity cap"),
        ("min_dividend", "Rule D: dividend floor"),
        ("max_holdings", "Advanced: max # holdings"),
        ("min_position", "Advanced: min position size"),
    ]
    if p["logic"] == "or" and p.get("max_single") is not None and p.get("min_lowrisk") is not None:
        # Relax A OR B as one policy. Removing one branch would tighten it.
        rules = [("or_policy", "Rule A OR B: joint policy")] + rules[2:]
    for key, label in rules:
        if key != "or_policy" and p.get(key) is None:
            continue
        relaxed = dict(p)
        if key == "or_policy":
            relaxed["max_single"] = relaxed["min_lowrisk"] = None
        else:
            relaxed[key] = None
        try:
            m2, w2, *_ = _build_model(pd_, relaxed)
            m2.optimize()
            if m2.SolCount == 0 or abs(m2.ObjVal) > 1e12:
                continue
            wgt = np.array([w2[t].X for t in pd_.tickers])
            ret2 = float(wgt @ pd_.mu)
            vol2 = float(np.sqrt(max(wgt @ pd_.cov @ wgt, 0.0)))
            rf = p.get("risk_free", 0.04)
            sh2 = (ret2 - rf) / vol2 if vol2 > 1e-12 else float("nan")
            m1 = base["metrics"]
            rows.append({
                "rule": label,
                "d_return_pp": round((ret2 * 100.0 - m1["expected_return_pct"]), 3),
                "d_vol_pp": round((vol2 * 100.0 - m1["volatility_pct"]), 3),
                "d_sharpe": round(sh2 - m1["sharpe_ratio"], 4),
            })
        except Exception:  # noqa: BLE001
            continue
    return rows


def _benchmarks(pd_: PortfolioData, p: dict) -> dict:
    """Simple comparisons: equal weight, min variance, S&P 500 (if present)."""
    tickers = pd_.tickers
    n = len(tickers)
    rf = p.get("risk_free", 0.04)
    mu, cov = pd_.mu, pd_.cov

    def stats(w: np.ndarray) -> dict:
        r = float(w @ mu)
        v = float(w @ cov @ w)
        s = float(np.sqrt(max(v, 0.0)))
        return {"ret_pct": r * 100.0, "vol_pct": s * 100.0,
                "sharpe": (r - rf) / s if s > 1e-12 else float("nan")}

    out: dict = {"equal_weight": stats(np.ones(n) / n)}

    try:
        m = gp.Model("bench_mvp")
        m.setParam("OutputFlag", 0)
        w = m.addVars(tickers, lb=0.0, ub=1.0)
        m.addConstr(gp.quicksum(w.values()) == 1.0)
        m.setObjective(gp.quicksum(cov[i, j] * w[tickers[i]] * w[tickers[j]]
                                   for i in range(n) for j in range(n)), GRB.MINIMIZE)
        m.optimize()
        if m.SolCount > 0:
            out["min_variance"] = stats(np.array([w[t].X for t in tickers]))
    except Exception:  # noqa: BLE001
        pass

    if "SPY" in tickers:
        i = tickers.index("SPY")
        e = np.zeros(n)
        e[i] = 1.0
        out["sp500"] = stats(e)
    return out


# ----------------------------------------------------------------------
# efficient frontier
# ----------------------------------------------------------------------
def frontier(params: dict, n_points: int = 24) -> dict:
    """Constrained efficient frontier: min variance for a grid of return
    targets, with the user's guideline constraints ON and OFF.

    Returns dict with 'df' (long dataframe for plotting), 'marks' (current
    portfolio, min-variance point, tangency point), and 'infeasible' flags.
    """
    p, warn = clean_params(params)
    pd_ = load_data().subset(p.get("tickers"))
    tickers = pd_.tickers
    n = len(tickers)
    mu, cov = pd_.mu, pd_.cov
    rf = p.get("risk_free", 0.04)
    curves: list[pd.DataFrame] = []
    marks: list[dict] = []

    def sweep(extra_off: tuple[str, ...] = ()) -> pd.DataFrame | None:
        relaxed = dict(p)
        for key in extra_off:
            relaxed[key] = None
        # min-variance portfolio under the (possibly relaxed) rules
        m, w, *_ = _build_model(pd_, relaxed)
        m.setObjective(gp.quicksum(cov[i, j] * w[tickers[i]] * w[tickers[j]]
                                   for i in range(n) for j in range(n)), GRB.MINIMIZE)
        m.optimize()
        if m.SolCount == 0:
            return None
        wgt0 = np.array([w[t].X for t in tickers])
        mu_min = float(wgt0 @ mu)

        # maximum achievable return under the same rules
        m2, w2, *_ = _build_model(pd_, relaxed)
        m2.setObjective(gp.quicksum(mu[i] * w2[t] for i, t in enumerate(tickers)),
                        GRB.MAXIMIZE)
        m2.optimize()
        if m2.SolCount == 0:
            return None
        mu_max = float(m2.ObjVal)

        pts = []
        for tau in np.linspace(mu_min, mu_max, n_points):
            m3, w3, *_ = _build_model(pd_, relaxed)
            m3.addConstr(gp.quicksum(mu[i] * w3[t] for i, t in enumerate(tickers))
                         >= tau, name="ret_target")
            m3.setObjective(gp.quicksum(cov[i, j] * w3[tickers[i]] * w3[tickers[j]]
                                        for i in range(n) for j in range(n)), GRB.MINIMIZE)
            m3.optimize()
            if m3.SolCount > 0:
                v = float(np.sqrt(max(wgt := np.array([w3[t].X for t in tickers]) @ cov
                                      @ np.array([w3[t].X for t in tickers]), 0.0)))
                pts.append({"vol_pct": v * 100.0, "ret_pct": float(np.array([w3[t].X for t in tickers]) @ mu) * 100.0})
        if not pts:
            return None
        return pd.DataFrame(pts)

    base_curve = sweep()
    if base_curve is not None:
        base_curve["series"] = "With your guidelines"
        curves.append(base_curve)

    off_curve = sweep(extra_off=("max_single", "min_lowrisk", "max_equity",
                                 "min_dividend", "max_holdings", "min_position"))
    if off_curve is not None:
        off_curve["series"] = "Guidelines off (long-only)" if p["long_only"] else "Guidelines off (shorting allowed)"
        curves.append(off_curve)

    df = pd.concat(curves, ignore_index=True) if curves else pd.DataFrame(
        columns=["vol_pct", "ret_pct", "series"])

    # marks: current solution, min-variance, tangency (on the ON curve)
    try:
        sol = solve(params)
        if sol["ok"]:
            marks.append({"vol_pct": sol["metrics"]["volatility_pct"],
                          "ret_pct": sol["metrics"]["expected_return_pct"],
                          "series": "Your portfolio"})
    except Exception:  # noqa: BLE001
        pass
    if base_curve is not None and len(base_curve):
        i_mvp = int(base_curve["vol_pct"].idxmin())
        marks.append({"vol_pct": base_curve.loc[i_mvp, "vol_pct"],
                      "ret_pct": base_curve.loc[i_mvp, "ret_pct"],
                      "series": "Min-variance point"})
        sr = (base_curve["ret_pct"] / 100.0 - rf) / (base_curve["vol_pct"] / 100.0)
        i_tan = int(sr.idxmax())
        marks.append({"vol_pct": base_curve.loc[i_tan, "vol_pct"],
                      "ret_pct": base_curve.loc[i_tan, "ret_pct"],
                      "series": "Best Sharpe on sampled frontier"})

    return {
        "df": df,
        "marks": pd.DataFrame(marks) if marks else None,
        "has_curve": bool(curves),
        "warnings": warn,
    }


if __name__ == "__main__":
    import json

    base = {
        "tickers": ["SPY", "QQQ", "IWM", "VXUS", "BND", "TLT", "GLD", "VNQ"],
        "mode": "qp", "lambda_": 3.0, "risk_free": 4.0, "long_only": True,
        "max_single": 30.0, "min_lowrisk": 40.0, "max_equity": 80.0,
        "min_dividend": 0.0, "logic": "and",
        "max_holdings": None, "min_position": None,
    }
    res = solve(base)
    print(json.dumps({k: v for k, v in res.items() if k != "weights"},
                     indent=1, default=str)[:2400])
    print("top weights:", dict(sorted(res["weights"].items(),
                                      key=lambda kv: -kv[1])[:6]))
