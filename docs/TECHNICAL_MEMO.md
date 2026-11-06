# Technical Memo — Portfolio Optimization Decision-Support App

**MSBC 5680 — Fall 2026 · Team Project (Track B)**
**Team:** Brandon Andrews, Jesse ____, Drew ____ · December 2026

---

## 1. Decision problem and intended user

A do-it-yourself investor (or a financial advisor acting for a client) must
allocate a fixed investment budget across a menu of exchange-traded funds.
The decision is a set of **weights** — the fraction of the budget placed in
each fund — that maximizes the portfolio's expected return for an acceptable
level of risk, subject to the investor's own policy guidelines.

The decision matters because the standard alternatives are poor substitutes:
picking "a few good funds" ignores the correlation structure between assets
(the same risk counted twice), while rule-of-thumb allocations (equal
weight, 60/40) make no trade-off between return and risk at all. An
optimization model makes that trade-off explicit and quantifiable.

The app targets three concrete use cases:

1. **An individual investor** choosing a long-term portfolio from a menu of
   real ETFs, who wants "what weights maximize my risk-adjusted return
   given my rules?"
2. **An advisor** who needs to explain *why* an allocation is recommended,
   and specifically **what each client policy rule costs in expected
   return** — the app's "guideline cost analyzer."
3. **A policy reviewer** who wants to test guideline sets before adopting
   them (e.g., "is a 10% single-fund cap worth it?") and to detect
   contradictory rules before they reach a client.

## 2. Main questions and how results are used

- What portfolio maximizes expected return given a risk budget?
- What portfolio maximizes risk-adjusted return (Markowitz), and how does
  the answer change with risk aversion λ?
- What do the investor's own constraints cost, measured in expected return,
  volatility, and Sharpe ratio?
- Which policy combinations are infeasible, and which rules conflict?
- How does the optimized portfolio compare with simple benchmarks
  (equal weight, minimum variance, S&P 500)?

The user changes inputs (universe, risk aversion, guideline levels, logical
"AND/OR" structure, cardinality and position-size rules) and the app
**re-solves a fresh Gurobi model on every click** — results are never
precomputed or hard-coded. Outputs are the optimal weights, portfolio
metrics, benchmark comparison, risk decomposition, the cost of each rule,
the constrained efficient frontier, and an explicit solver-status banner
that never presents an infeasible or failed solve as a recommendation.

## 3. Data and assumptions

Prices: daily closes for 13 liquid ETFs (US equity: SPY, QQQ, IWM, VTI;
international: VXUS, EFA; bonds: BND, TLT, LQD, HYG, SHY; alternatives:
GLD, VNQ), ~5 years (1,255 trading days), downloaded live from Yahoo
Finance and bundled in the repository (`data/etf_prices.csv`,
`data/etf_meta.csv`) so the app runs offline and reproducibility is
guaranteed. `data/fetch_data.py` refreshes the bundle; a synthetic
fallback with class-level means/vols is generated if the network is
unavailable.

Annualized expected returns μ and covariance Σ are estimated as the
sample mean and covariance of daily returns × 252. Dividend yields come
from ETF metadata. Key estimates:

| Ticker | Class | E[r] %/yr | Vol %/yr | Div % |
|---|---|---|---|---|
| GLD | Alternatives | 17.37 | 19.06 | 0.00 |
| QQQ | US Equity | 14.43 | 23.11 | 0.42 |
| SPY | US Equity | 12.54 | 17.17 | 0.99 |
| VTI | US Equity | 11.63 | 17.50 | 1.06 |
| EFA | International | 9.19 | 16.62 | 3.24 |
| VXUS | International | 8.88 | 16.39 | 2.34 |
| IWM | US Equity | 6.91 | 22.33 | 0.98 |
| HYG | Bonds | 3.46 | 7.54 | 6.14 |
| VNQ | Alternatives | 2.67 | 18.90 | 3.80 |
| SHY | Bonds | 1.91 | 2.03 | 3.65 |
| BND | Bonds | −0.08 | 6.07 | 4.17 |
| LQD | Bonds | −0.62 | 8.66 | 4.91 |
| TLT | Bonds | −6.95 | 15.65 | 5.00 |

*Limitations (stated, not hidden):* historical moments are noisy estimates
— no forecasting or regime adjustment; the model is single-period (no
rebalancing path); expected returns can be negative for bond funds after
a rate-hike cycle; the 2021–2026 window is unusual for bonds (TLT at
−6.95%/yr). These are exactly the classic Markowitz assumptions and are
flagged in the app.

## 4. Mathematical formulation

Let n be the number of selected ETFs, `w` the weight vector, `μ` the
annualized mean-return vector, and `Σ` the annualized covariance matrix.

**Decision variables.** w*i* ∈ [0, 1] (long-only) or [−1, 1] (if shorting
allowed): fraction of budget in fund i. Binary variables appear when the
user enables logical or cardinality rules (below).

**Objective (two modes).**
- LP mode (Lecture 14 style): `maximize  μᵀw`
- QP mode (Markowitz, Lecture 19): `maximize  μᵀw − (λ/2)·wᵀΣw`
  where λ ≥ 0 is a user-set risk-aversion parameter; λ = 0 recovers the LP.

**Constraints** (each guideline is a constraint only when activated):

| Constraint | Math | Meaning |
|---|---|---|
| Budget | Σw = 1 | all capital invested |
| Long-only | w ≥ 0 (optional) | no short positions |
| Rule A: single-ETF cap | wᵢ ≤ cap ∀i | diversification: no more than X% in one fund |
| Rule B: defensive floor | Σ_def w ≥ floor | at least Y% in bonds + gold + real estate |
| Rule C: equity cap | Σ_equity w ≤ cap_eq | equity exposure ceiling |
| Rule D: dividend floor | Σ dᵢwᵢ ≥ div_min | income floor (d = dividend yield) |
| OR-logic (A or B) | y₁ + y₂ ≥ 1; wᵢ ≤ cap + M(1−y₁); Σ_def w ≥ floor − M(1−y₂) | at least one of Rules A/B holds; y binary, M is derived from exposure bounds (1 is sufficient long-only) (Lecture 14 big-M) |
| Cardinality | Σz ≤ K; −zᵢ ≤ wᵢ ≤ zᵢ (wᵢ ≥ 0 long-only); z binary | own at most K funds |
| Min position | |wᵢ| ≥ ℓ when zᵢ = 1 (sign binaries if shorting) | any holding is at least ℓ% (shared z) |

The frontier plot solves, for a grid of target returns τ between the
constrained minimum-variance portfolio return and maximum achievable return:
`minimize wᵀΣw subject to μᵀw ≥ τ` plus the active guidelines — a
constrained efficient frontier, plotted with guideline set ON vs OFF.

## 5. Implementation and verification

Backend (`model.py`) builds and solves each model with Gurobi 13
(`gurobipy`), time-limited (20 s), output suppressed, with status/MIP gap
surfaced in the UI. Every user action triggers a new solve. The app
(`app.py`) is a Gradio interface; the optimization logic sits in a
separate module called by the interface, per the Track B requirement.

**Verification** (a first-class feature, runnable in-app or headless with
`python verification.py` — all checks pass):

1. **Analytic min-variance check.** The unconstrained minimum-variance
   portfolio has a closed form w* = Σ⁻¹1/(1ᵀΣ⁻¹1). Gurobi's QP matches the
   closed form to **4.3e-11** over random 8-asset instances.
2. **Hand-computable 3-asset instance.** With a diagonal covariance,
   long-only min-variance weights are proportional to 1/σ²; Gurobi matches
   the hand calculation (max error 1.4e-6 — solver noise). The LP
   max-return solution correctly goes 100% into the highest-return asset.
3. **Production-data endpoint checks.** On the real bundled data, the
   unconstrained LP puts 100% into the highest-mean ETF (GLD, 17.37%);
   all solves return weights summing to 1.
4. **Business-rule checks.** Risk contributions sum to 1; weights lie in
   [0, 1].

Two data defects were caught *because* numbers were checked against
business rules during development: a yfinance dividend-yield unit error
(off by 100×) that silently disabled Rule D, and the dual-value display
being mislabeled by 100×. Both were fixed and re-verified — an example of
the verification loop the guidelines ask for.

**Infeasibility handling.** When guidelines conflict (e.g., cap 10% and
defensive floor 60%), Gurobi's IIS identifies the conflicting constraints
and the app reports them by name — never a fake recommendation.

## 6. Sample scenarios and insights (run on the shipped app)

**Scenario 1 — Base case** (λ = 3, cap 30%, defensive floor 40%, equity
cap 80%, cardinality K = 6, min position 3%):
optimal E[r] = **13.65%**, vol = **14.60%**, Sharpe = **0.66**; weights
SPY 30 / QQQ 30 / GLD 30 / HYG 10. Risk decomposition shows QQQ — 30% of
the money — contributing **43% of the risk**, the textbook reason
diversification rules exist. Benchmarks: equal weight 6.97/12.56/0.24;
min-variance 0.63/6.01/−0.56; SPY alone 12.54/17.17/0.50. The optimized
portfolio beats every benchmark on Sharpe.
Guideline cost analyzer: Rule A (cap) costs **+2.97pp return** if removed
(and +1.62pp vol — the insurance it buys); Rule B (floor) costs only
+0.54pp. *Insight: the floor is cheap insurance; the strict cap is the
expensive rule.*

**Scenario 2 — Aggressive growth** (λ = 1.5, cap 50%, floor 20%, K = 8):
E[r] = **15.90%**, vol = 16.12%, Sharpe = **0.74**; only two holdings
QQQ 50 / GLD 50 (both at the cap). A less risk-averse investor gains
+2.25pp return at +1.52pp vol. The cardinality/min-position rules become
non-binding — the caps alone determine concentration.

**Scenario 3 — Conflicting rules** (cap 10%, floor 60%, equity cap 70%):
**Infeasible**; the app's IIS analysis names the offenders: Rule A
(10% single-fund cap) conflicts with Rule B (60% defensive floor) — the selected universe has nine ETFs, so a 10% cap alone limits total investment to 90%. The defensive subset has five funds and cannot reach 60% under that cap. IIS may identify either conflict.
Switching the guideline logic to **OR** (Lecture 14 binaries) restores
feasibility: the model keeps the cheaper rule to enforce and waives the
other — GLD 74.3 / QQQ 25.7, E[r] 16.61%, Sharpe 0.78 — and the banner
states exactly which rule it waived and why.

**LP-mode dual aside.** In LP mode the cost table appends shadow prices:
raising the defensive floor by 1 pp costs **0.0543 pp/yr** of expected
return at the current optimum — the marginal price of the rule, consistent
with the discrete re-solve numbers.

## 7. Managerial conclusions and limitations

- On this historical estimation window: the base-case
  portfolio has a higher in-sample Sharpe ratio than equal weight and SPY.
- **Constraints are negotiable**: the app prices each one. Rule A costs
  ~3 pp of return for ~1.6 pp of volatility; Rule B costs ~0.5 pp. An
  advisor can now say "relaxing your 30% cap increases estimated historical annual return by about 3 percentage points — is that
  the insurance you want?"
- **Some rules cannot coexist**; the app finds and names the conflict
  before it reaches a client.
- The LP/QP/MIQP ladder (Lectures 13–15, 19) is one model, not three
  demos: binaries power the OR-logic and cardinality features.

Limitations: single-period model; historical moments rather than
forecasts; dividend yields static; no transaction costs or taxes (a
natural MIQP extension); solver optimality is for the *coded* model —
business translation remains the team's responsibility (and is exercised
by the verification suite).

## 8. Repository contents

App (`app.py`), backend (`model.py`), verification (`verification.py`),
data + fetch script (`data/`), tests (`test_model.py`,
`test_app_api.py`), sample scenario inputs (`samples/`), this memo,
demo script, AI-use statement (`docs/`), README with launch and testing
instructions (`README.md`), one-click launcher (`run_app.bat`).

## Correctness and interpretation notes (November 5, 2026)

Shorting uses signed net weights, bounded individually between -100% and
100%, with net weights summing to 100%; there is no separate gross-leverage
cap. Cardinality counts both long and short positions. Minimum position
size applies to absolute weight and works with or without cardinality.
User minimum sizes are preserved: a maximum holding count does not require
that many holdings. Infeasible policies are reported rather than weakened.

The frontier now uses the identical model constraints, including OR logic,
cardinality, and position sizes. With integer rules, the frontier need not
be smooth or convex. The displayed best Sharpe point is the best sampled
point, not an exact tangency optimization.

In OR mode, the cost analyzer removes the whole A OR B policy. Removing
one branch would tighten the policy, so individual branch removal is not
a relaxation. Return changes from relaxing rules need not be positive for
a risk-adjusted objective. Benchmarks are reference portfolios and may
violate user policies. All comparisons are in-sample; no out-of-sample
performance or future superiority is established.

Defensive is a category proxy including all bonds, gold, and real estate.
High-yield bonds, long-duration bonds, and real estate can carry substantial
risk; the category floor is not a volatility limit.

The refreshed dividend estimate is trailing annual cash distribution /
price × 100, with documented approximate fallback yields when unavailable.
The bundled snapshot has not been overwritten by the code fixes.

Run `python -m unittest test_policy_regressions -v` for targeted checks of
shorting, signed holding links, standalone minimum size, preserved policies,
OR exposure bounds, joint policy costs, frontier consistency, and dividend
units. Recheck the rendered memo meets the required 3–5 pages before submission.
