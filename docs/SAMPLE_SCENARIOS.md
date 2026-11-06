# Sample scenarios — regenerated November 5, 2026

Computed by the corrected backend against the unchanged bundled snapshot. These are historical in-sample estimates, not forecasts.

## scenario_1_base

Input: `samples/scenario_1_base.json`.

Status: **Optimal**.

Estimated annual return: 13.65%; volatility: 14.60%; Sharpe: 0.660.

| ETF | Signed weight % | Risk contribution % |
|---|---:|---:|
| SPY | 30.00 | 31.96 |
| QQQ | 30.00 | 43.16 |
| HYG | 10.00 | 3.82 |
| GLD | 30.00 | 21.06 |

Relaxation deltas (comparison minus baseline):

| Policy relaxed | Return pp | Volatility pp | Sharpe |
|---|---:|---:|---:|
| Rule A: single-ETF cap | +2.968 | +1.615 | +0.1172 |
| Rule B: defensive floor | +0.543 | +0.825 | -0.0001 |
| Rule C: equity cap | +0.000 | +0.000 | +0.0000 |
| Advanced: max # holdings | +0.000 | +0.000 | +0.0000 |
| Advanced: min position size | +0.000 | +0.000 | +0.0000 |

## scenario_2_aggressive

Input: `samples/scenario_2_aggressive.json`.

Status: **Optimal**.

Estimated annual return: 15.90%; volatility: 16.12%; Sharpe: 0.738.

| ETF | Signed weight % | Risk contribution % |
|---|---:|---:|
| QQQ | 50.00 | 58.21 |
| GLD | 50.00 | 41.79 |

Relaxation deltas (comparison minus baseline):

| Policy relaxed | Return pp | Volatility pp | Sharpe |
|---|---:|---:|---:|
| Rule A: single-ETF cap | +1.098 | +1.234 | +0.0108 |
| Rule B: defensive floor | +0.000 | +0.000 | +0.0000 |
| Rule C: equity cap | +0.000 | +0.000 | +0.0000 |
| Advanced: max # holdings | +0.000 | +0.000 | +0.0000 |
| Advanced: min position size | +0.000 | +0.000 | +0.0000 |

## scenario_3_conflict

Input: `samples/scenario_3_conflict.json`.

Status: **Infeasible**.

IIS explanations (the particular IIS may vary):
- Rule A: no more than 10% in a single ETF
- Rule B: at least 60% in defensive assets (bonds + gold + real estate; category proxy, not a risk guarantee)

## scenario_3_conflict — OR rescue

Input: `samples/scenario_3_conflict.json` with `logic="or"`.

Status: **Optimal**.

Estimated annual return: 16.61%; volatility: 16.22%; Sharpe: 0.778.

| ETF | Signed weight % | Risk contribution % |
|---|---:|---:|
| QQQ | 25.68 | 18.57 |
| GLD | 74.32 | 81.43 |

Relaxation deltas (comparison minus baseline):

| Policy relaxed | Return pp | Volatility pp | Sharpe |
|---|---:|---:|---:|
| Rule A OR B: joint policy | +0.000 | +0.000 | +0.0000 |
| Rule C: equity cap | +0.000 | +0.000 | +0.0000 |
| Advanced: max # holdings | +0.000 | +0.000 | +0.0000 |
| Advanced: min position size | +0.000 | +0.000 | +0.0000 |

## Reproduce

```python
import json, model
with open('samples/scenario_1_base.json') as f:
    result = model.solve(json.load(f))
print(result['status'], result['metrics'])
```

In OR mode the whole A OR B policy is relaxed together. Benchmarks may violate user policies. Defensive includes bonds, gold, and real estate; it is not a guarantee of low risk.
