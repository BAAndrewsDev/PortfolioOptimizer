# Portfolio Optimizer — MSBC 5680 Team Project (Track B)

An interactive **optimization decision-support app**: a DIY investor or
advisor picks a set of real ETFs and their own policy guidelines; the app
**re-solves a fresh Gurobi optimization** on every click and shows the
optimal allocation, what each guideline *costs*, benchmarks, and the
constrained efficient frontier.

> Every solve is a real optimization run — nothing is precomputed or
> hard-coded. The model is the deliverable; the dashboard is its interface.

---

## Quick start

The verified setup is **Windows with Python 3.14.4** and a working Gurobi
academic license. `requirements.txt` pins the five direct dependencies used
for verification; pip resolves their additional dependencies. It is not a
complete environment lockfile, and other platforms have not been tested.

After cloning the repository or extracting the ZIP, open a terminal in the
project folder. On Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:7861 in your browser. After the one-time setup,
double-click `run_app.bat`: it automatically uses `.venv\Scripts\python.exe`
when present, otherwise `python` from PATH. Activation is not required.
Each teammate must configure their own Gurobi license; do not share license
files or copy another person's virtual environment.

For macOS/Linux (not yet validated), the equivalent commands are:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Headless checks (no UI needed; use your virtual environment interpreter):

```bash
.venv/Scripts/python.exe verification.py    # must print ALL PASSED
.venv/Scripts/python.exe test_model.py      # backend smoke tests
```

## What the app does

| Panel | What you can change | What you get back |
|---|---|---|
| Universe & objective | ETF selection (13 funds), QP vs LP objective, risk aversion λ, risk-free rate, shorting | Solver status (Gurobi, incl. solve time & # binaries) |
| Policy guidelines | Rule A single-ETF cap · Rule B defensive floor · Rule C equity cap · Rule D dividend floor · **AND/OR logic** | Optimal weights, expected return, volatility, Sharpe |
| Advanced (MIQP) | Max # holdings (cardinality), minimum position size | Risk contributions per ETF, objective value |
| Frontier | Checkbox | Constrained efficient frontier (guidelines ON vs OFF) + your portfolio, min-variance, tangency marks |
| Cost analyzer | *(automatic)* | What each rule costs in return / volatility / Sharpe, plus LP marginal values (duals) |
| About | — | Model formulation, verification suite run in-app |

**Unusual-but-graded features** (per the project guidelines):
- **Infeasible inputs are diagnosed, not glossed over**: Gurobi IIS analysis
  names the conflicting guidelines (e.g. "Rule A conflicts with Rule B").
- **Verification is a first-class feature**: closed-form min-variance check
  vs. matrix inversion, a hand-computable 3-asset instance, endpoint checks
  on production data (`verification.py`; also runnable from the About tab).

## Model summary

Let `wᵢ` = fraction invested in ETF `i`, `μ`/`Σ` = annualized historical
moments (5y daily returns, Yahoo Finance, bundled in `data/`).

- **LP** (Lecture 14): maximize `μᵀw`
- **QP** (Markowitz, Lecture 19): maximize `μᵀw − (λ/2)·wᵀΣw`
- Constraints: `Σw = 1`, optional long-only, plus any toggled guidelines
  (caps, floors, dividend floor).
- **OR-logic** (Lecture 14, big-M based on weight and budget bounds): binaries `y₁,y₂`,
  `y₁+y₂ ≥ 1`, waiving one of two guidelines.
- **MIQP**: binaries `zᵢ` for cardinality (`Σzᵢ ≤ K`) and minimum absolute position
  sizes (linked to holding indicators; sign binaries when shorting).

Full write-up lives in the app's "About" tab.

## Project layout

```
app.py            Gradio UI (inputs -> Gurobi -> outputs)
model.py          optimization backend (LP/QP/MIQP, IIS, rule costs, frontier)
verification.py   independent self-checks (closed-form vs solver)
data/fetch_data.py  refreshes the bundled market data (yfinance)
data/etf_prices.csv  daily closes, 13 ETFs x ~5 years (bundled)
data/etf_meta.csv    names, asset classes, dividend yields
data/SOURCE.txt      where the bundle came from
test_model.py / test_app_api.py   headless + end-to-end API tests
```

## Requirements & notes

- Python 3.11+ with **Gurobi (gurobipy) and a license** — free academic
  license via https://www.gurobi.com/academics (this course uses Gurobi).
- The app runs fully offline thanks to the bundled CSVs; re-fetch or extend
  the universe with `python data/fetch_data.py`.
- The bundled data were fetched **live from Yahoo Finance** (see
  `data/SOURCE.txt`); expected returns/volatility are simple historical
  moments — the classic Markowitz assumption, listed as a limitation in the
  app's About tab.
- Gurobi logs are suppressed by design; solver status, time, and MIP gap
  are surfaced in the UI instead.

## Deliverables mapping (Track B)

1. ✅ Working application — this repo
2. ✅ Technical memo (3–5 pp) — `docs/TECHNICAL_MEMO.md`
3. ✅ Source code, data, README — reproducible locally; sample inputs in
   `samples/` with expected outputs in `docs/SAMPLE_SCENARIOS.md`
4. ✅ Recorded 10–15 min demo — script in `docs/DEMO_SCRIPT.md` (roles for
   Brandon/Jesse/Drew, 3 tested scenarios with exact on-screen numbers)
5. ✅ AI-use statement — `docs/AI_USE_STATEMENT.md` (fill in the tool-name
   brackets with what the team actually used)
6. ✅ Launch instructions PDF — sent to the course folder

## Portability and model checks

Extract the complete project, install requirements into your chosen Python
environment, and run `python app.py`. On Windows, `run_app.bat` uses its own
folder and prefers its `.venv` interpreter, falling back to `python` on PATH. A working
Gurobi license is required. Direct dependency versions are pinned to the tested environment;
a fresh installation on another device has not been validated.

Run `python -m unittest test_policy_regressions -v` in addition to
`python verification.py` and `python test_model.py`.

The bundled adjusted prices span 2021-11-03 through 2026-11-03. Results and
benchmark comparisons are in-sample estimates, not performance forecasts.
The defensive category includes bonds, gold, and real estate, including
high-yield and long-duration bond funds. It is not a low-risk guarantee.
Short positions are bounded at -100% individually; long positions at 100%;
net exposure is 100% without an additional gross-exposure limit.

In OR mode the cost analyzer relaxes the joint A OR B policy. Frontier
calculations apply all selected rules; their best Sharpe marker is sampled.
Refreshing data overwrites the snapshot and can fall back to synthetic data;
always inspect `data/SOURCE.txt` afterward.

Before submission, complete the team names and factual AI-use statement,
format the technical memo to 3–5 pages, and record the 10–15 minute demo.

## Team collaboration

Clone the repository using GitHub Desktop or Git. Before editing, fetch and
pull the latest main branch, create a branch for your change, and open a
pull request after checking your work. Keep the bundled data in the
repository so everyone can reproduce the same scenarios. Refresh it only
as an intentional, reviewed change.

The `.gitignore` excludes local environments, caches, credential files, and
Gurobi licenses. It does not remove files already tracked by Git. The source,
requirements, bundled CSVs, samples, tests, and documentation should be
committed. Do not commit your `.venv` folder.

When upgrading a direct dependency, update its exact version in
`requirements.txt`, run the verification and regression checks, and include
the version change in your pull request. On Windows, run:

```powershell
.\.venv\Scripts\python.exe verification.py
.\.venv\Scripts\python.exe test_model.py
.\.venv\Scripts\python.exe -m unittest test_policy_regressions -v
```
