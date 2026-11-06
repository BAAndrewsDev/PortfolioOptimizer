# AI-Use Statement — Portfolio Optimization Decision-Support App

**MSBC 5680 · Track B · Brandon, Jesse, Drew · December 2026**

*Template: fill in the bracketed tool names with exactly what your team
used. Keep this brief — the guidelines ask for a practical statement, not
a transcript.*

## 1. Tools used

- **AI coding agent(s):** OpenAI Codex (confirmed in this review);
  [team: add other tools actually used] for code generation, scaffolding, UI
  wiring, data preparation, debugging, and drafting of this memo, demo
  script, and statement.
- **Gurobi / gurobipy:** the academic-licensed optimizer that solves every
  model in the app (not an AI tool).
- **yfinance / pandas / numpy / Gradio:** standard libraries for data,
  numerics, and interface (not AI tools).

## 2. What the AI tools helped produce

- Initial drafts of the Python backend (`model.py`), the Gradio interface
  (`app.py`), the data pipeline (`data/fetch_data.py`), the verification
  suite (`verification.py`), and the test scripts.
- Drafting of this memo, the demonstration script, and the README.
- Debugging assistance, including diagnosing the port-in-use launch
  error and two correctness bugs found during verification (details
  below).

## 3. What the AI tools did NOT do (and how outputs were verified)

The team remains responsible for — and verified — the mathematical
formulation, the business translation of the rules, the correctness of the
implementation, and the interpretation of results. Concretely:

1. **Model correctness** was verified against independent mathematics, not
   AI claims: the minimum-variance portfolio was compared with the
   closed-form solution w* = Σ⁻¹1/(1ᵀΣ⁻¹1) computed in numpy (match to
   1e-11); a hand-computable three-asset instance (min-variance weights
   proportional to 1/σ², LP max-return endpoint) was checked by hand.
2. **Business rules** were verified: weights sum to 1, risk contributions
   sum to 1, endpoints behave as theory requires on the production data
   (`verification.py` — all checks pass; also runnable inside the app).
3. **Implementation** was tested end-to-end: the app was exercised through
   its live API across five scenarios (base case, aggressive policy,
   infeasible input, OR-logic rescue, LP duals), and outputs were checked
   against expectations.
4. **AI-generated code that failed verification was fixed by the team**:
   scenario testing caught a dividend-yield unit error (100×) that
   silently disabled a constraint, and a mislabeled dual-value readout;
   both were corrected, and the fixes were re-verified.
5. **Interpretations require team review**: AI assisted with memo wording and
   limitations. The team must review and own the final conclusions.

## 4. Known boundaries

- Every numerical result shown in the demo and memo was produced by
  running the actual app (Gurobi output), not by any AI tool.
- The AI agents produced drafts; the team reviewed, tested, and owns the
  final code and documents. Teammates can defend and explain any line of
  the formulation and any number in the demo.

Team confirmation required: remove template instructions and confirm prior development/testing claims accurately describe work actually performed. This review ran backend verification, smoke checks, and targeted regression tests.
