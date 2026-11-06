# Recorded App Demonstration — Script (10–15 minutes)

**MSBC 5680 Track B · Presenters: Brandon, Jesse, Drew**

*Scenario outputs were regenerated through the corrected backend on November 5, 2026; use docs/SAMPLE_SCENARIOS.md as the numeric reference. Rehearse the live UI before recording. If you re-fetch the market data
(`python data/fetch_data.py`) the numbers will drift — if that happens,
re-record the affected segments using the fresh values, or restore the
bundled CSV from the repo.*

---

## Before you press record (5-minute checklist)

- [ ] Launch the app: double-click `run_app.bat` (or the CLI commands in
      the README). Confirm it opens at
      **http://127.0.0.1:7861**.
- [ ] Click **↺ Reset** once so the recording starts from factory defaults.
- [ ] Recording software (OBS / PowerPoint / Zoom) capturing the browser
      window in full screen at 1080p; mic check for all three speakers;
      **mute OS notifications** (Windows Focus Assist).
- [ ] Rehearse once through; total should land 12–14 minutes.
- [ ] Roles are suggestions — swap segments to match who's most
      comfortable on camera. Whoever is NOT speaking should stay muted
      and quiet.
- [ ] Have the README + this script open on a second monitor for cue
      numbers, if available.

---

## Scene 1 — Intro & the decision problem (Drew, ~1:30)

**On screen:** the app right after Reset (all tables empty). Cursor resting,
and Drew narrates.

> "Hi — we're Brandon, Jesse, and Drew, and this is our Track B project:
> a **portfolio-optimization decision-support app**. A DIY investor or an
> advisor has to put money into a menu of real ETFs, and the central
> question is *what weights* maximize the portfolio's expected return for
> an acceptable level of risk — subject to the investor's own policy
> guidelines."
>
> "The key thing about this app: every single solve is a **fresh Gurobi
> optimization**. Nothing here is precomputed or hard-coded — we built
> three model classes from the course: the Lecture-14 style linear program,
> the Markowitz quadratic program from Lecture 19, and a mixed-integer QP
> that adds binary variables for cardinality and logical rules. The data is
> five years of real daily returns for thirteen ETFs, bundled so the app
> runs offline."
>
> "Let's walk through what it can do. Brandon?"

## Scene 2 — Scenario 1: the base case (Brandon, ~3:30)

**On screen:** default settings already in place after Reset (9 ETFs
selected, QP mode, λ = 3, Rule A 30%, Rule B 40%, Rule C 80%, AND logic,
max 6 holdings, min 3%).

> "I'll start with a balanced, 'standard policy' investor and just press
> **Solve portfolio**." *(click Solve)*
>
> "The banner confirms **OPTIMAL** — Gurobi solved it in a few
> milliseconds. Our metrics: **13.65% expected return, 14.6% volatility,
> Sharpe ratio 0.66**, using four holdings."
>
> "Look at the allocation table — this is the model's answer. **SPY 30,
> QQQ 30, GLD 30, HYG 10.** Two things worth pointing out. First, three
> funds sit *exactly* at our 30% cap — the constraint is binding, the
> model would like more of them. Second, the **risk contribution** column:
> QQQ is 30% of the money but **43% of the risk**, because it's volatile
> and correlated with SPY. That's the reason diversification rules exist —
> the table shows you *where* risk actually lives, not just where the
> money is."
>
> *(scrolls down to benchmarks / cost analyzer)*
>
> "Below, the app compares against simple benchmarks: equal weight gets a
> Sharpe of 0.24, the S&P 500 alone 0.50 — our optimized portfolio beats
> them at **0.66**. And this table is our favorite feature: the
> **guideline cost analyzer**. The app re-solves the model with each rule
> removed and reports the difference. Rule A — the 30% single-fund cap —
> costs **2.97 points of expected return per year** if you keep it, and
> buys 1.6 points of lower volatility. Rule B, the defensive floor, costs
> only half a point. So: the floor is cheap insurance, the strict cap is
> the expensive rule. That's an actionable, quantified trade-off an
> advisor can put in front of a client."
>
> *(checks the frontier checkbox, clicks Solve again — or clicks "also
> compute the frontier" first and presses Solve once)*
>
> "Let me turn on the **efficient frontier** and re-solve. Here's the
> constrained frontier with our guidelines — every point is a solved
> minimum-variance portfolio for a target return. The grey curve shows the
> same frontier with all guidelines turned off. You can literally see the
> cost of the rules: the grey frontier reaches higher returns. Our current
> portfolio is marked, along with the min-variance point and the best Sharpe point on the sampled frontier. Jesse, take it from here."

## Scene 3 — Scenario 2: an aggressive policy (Jesse, ~3:00)

**On screen:** left panel. Jesse explains and changes settings deliberately,
*one at a time*, letting each label be read:

> "Same investor universe, but now suppose the client is younger, more
> aggressive, and wants fewer handcuffs. I'll lower risk aversion from 3 to
> **1.5**, raise the single-fund cap from 30% to **50%**, drop the
> defensive floor from 40% to **20%**, and loosen the cardinality limit to
> 8." *(click Solve)*
>
> "Result: **15.9% expected return, 16.1% volatility, Sharpe 0.74** — so
> the more aggressive policy gains 2.25 points of return at 1.5 points of
> extra volatility, and it's still the best Sharpe we've seen." *(gestures
> at allocation)*
>
> "Notice the allocation collapsed to just two funds: **QQQ 50 and GLD
> 50** — both pinned at the new cap. The model concentrates because the
> client's rules now allow it. And the cost analyzer tells the story:
> Rule A still costs about a point of return, but the floor is no longer
> binding at all — removing it changes nothing. The risk decomposition now
> shows QQQ carrying **58% of the risk**; this is a very different risk
> profile, and the client should see that *before* signing off. That's
> exactly the kind of what-if the guidelines asked us to support."
>
> "So what happens if the client's rules simply can't all be true at
> once? Brandon — this is your favorite part."

## Scene 4 — Scenario 3: conflicting rules & the OR-logic rescue (Brandon, ~2:30)

**On screen:** change settings to the conflict: Rule A cap **10%**, Rule B
floor **60%**, Rule C **70%**, logic still **AND**. Click Solve.

> *(click Solve — banner flips to Infeasible)*
>
> "Here's a genuinely hard case: a 10% single-fund cap and a 60% defensive
> floor. Watch what happens — **infeasible**. And notice the app does not
> just say 'no solution'. Gurobi runs an **irreducible infeasible
> subsystem** analysis and the app names the conflict: Rule A and Rule B
> literally cannot both hold — if 60% has to sit in the five selected defensive
> funds (including real estate), one of them must exceed 10%."
>
> *(flips guideline logic to OR — at least one of Rules A or B must hold —
> clicks Solve)*
>
> "Now the payoff for the integer-programming material from Lecture 14.
> I switch the guideline logic to **OR** — 'at least one of the cap or
> the floor must hold' — which adds two binary variables and big-M
> constraints. The model picks the cheaper rule to satisfy and waives the
> other, and the banner tells us exactly what it decided: it kept the
> **defensive floor** and waived the single-fund cap. Result: GLD at 74%,
> QQQ at 26%, **16.6% return, Sharpe 0.78**. Without the binary-variable
> machinery this 'either/or' policy could not even be formulated. Drew,
> wrap it up?"

## Scene 5 — Verification & takeaways (Jesse + Drew, ~2:30)

**On screen:** About tab → "Run self-verification suite" button.

> **Jesse:** "Before we close — the guidelines demand verification, and we
> built it into the app. Pressing **Run self-verification suite** executes
> four independent checks: the minimum-variance portfolio against its
> closed-form matrix solution — matching to four decimal places of
> scientific notation; a hand-computable three-asset case from the course
> material; endpoint checks on the production data; and the business
> rules. All passed in the current verification run, and the same suite runs headless with one
> command. During development, those checks caught two real data bugs —
> a dividend-yield unit error that silently disabled one of our
> constraints. That's the verification loop working."

> **Drew:** "So, the managerial takeaways. One: on this historical estimation window, the optimized portfolio compares favorably to rules
> of thumb — the base case beats equal weight and the S&P 500 on Sharpe
> while holding less risk. Two: **guidelines have prices**, and this app
> puts a number on them — the 30% cap costs roughly three points of return
> a year; the defensive floor costs half a point. Three: some policy sets
> are mathematically impossible, and the app detects the conflict and
> tells you which rules are fighting. The honest limitations, which are in
> the memo: we use historical moments, not forecasts; it's a single-period
> model; and the bond numbers reflect a genuinely unusual five-year window
> for fixed income. The formulation, verification checks, and every number
> in this demo came from actually running the model — nothing is staged.
> Thanks for watching."

*(End recording — fade out.)*

---

## Timing & fallback notes

| Segment | Speaker | Target | Hard max |
|---|---|---|---|
| 1. Intro | Drew | 1:30 | 2:00 |
| 2. Base case | Brandon | 3:30 | 4:30 |
| 3. Aggressive | Jesse | 3:00 | 3:45 |
| 4. Conflict/OR | Brandon | 2:30 | 3:15 |
| 5. Verification + close | Jesse/Drew | 2:30 | 3:30 |
| **Total** | | **13:00** | **~15:00** |

- **Frontier takes too long / lags:** skip the frontier re-solve in Scene 2
  (it's a bonus; the cost analyzer already proves live computation). Keep
  the narrative flow — never wait silently.
- **Numbers differ from this script:** the bundled CSV was replaced
  (someone ran fetch_data.py). Re-record affected lines with fresh values
  rather than reading stale ones.
- **Cut for time:** in Scene 3, cut the risk-decomposition sentence. In
  Scene 4, cut the OR-logic re-solve and end on the IIS diagnosis (but try
  to keep it — it's the differentiator).
- **Speaker balance:** if one presenter ends up with less than ~3:30, hand
  them a supporting line in Scenes 2/3 (e.g., reading the benchmark row).

## Required interpretation corrections for the recording

- State that all return/risk comparisons are in-sample estimates, not evidence of future outperformance.
- Explain that the defensive category includes real estate and high-yield/long-duration bonds; it is not a risk guarantee.
- Scenario 3 is infeasible even from the 10% cap alone: nine selected funds cannot sum to 100%. With max eight holdings the cap permits only 80%. A returned IIS is one conflicting subset, not a unique explanation.
- In OR mode, the cost analyzer relaxes A OR B together. Do not interpret removal of a single branch as a relaxation.
- The frontier enforces holding and logical rules and can be nonsmooth with binaries. Its Sharpe marker is sampled, not an exact tangency solution.
- Benchmarks may violate selected rules. Explain historical differences without calling diversification a guarantee or a policy floor insurance.
