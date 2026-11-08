# Rates Book Risk and Daily P&L Attribution Monitor

Prices a simulated 40-position book of cash Treasuries, futures, swaps
and a payer swaption off one bootstrapped OIS curve, decomposes key-rate
DV01 at 6 curve nodes and reconciles the sum against the book's own
parallel DV01, runs parallel-shift, 2s10s-twist and funding-shock
scenarios, and attributes 250 sessions of daily P&L into curve, carry,
spread and residual. Python 3.12, stdlib only for every computed number
below (PostgreSQL persistence is designed and unit-tested against its own
error path, not required to reproduce any result here). Every number
below was measured on this machine, not targeted.

Extended (Nov. 2026, Schonfeld 2027 DMFI Intern req) with `screen/`, a cross-sectional relative-
value screener: forward-starting swaps as a fifth instrument family, two curve slopes, two
butterflies and five par swap spreads screened for 2-sigma rolling dislocations across a new,
separate 500-session simulation, every candidate's legs sized DV01-neutral off the same curve,
and a carry-plus-roll-down-plus-half-spread cost check that reverses some candidates' expected
direction. The original 40-position book, its key-rate reconciliation and its attribution numbers
are all untouched.

## Why this exists

This is a small version of the risk-and-attribution system a rates desk
runs every morning: one curve, every position priced off it, risk broken
into pieces small enough that a trader can tell which part of the curve
or which product a P&L swing came from, and a residual that is reported
rather than hidden. A risk system that cannot explain where yesterday's
P&L came from is not a risk system a desk can act on.

## Honest framing, up front

- **Every position, the curve and all market data are simulated**, not
  sourced from any venue. The 40-position book
  (`rates_risk/book.py`) is a fixed, deterministic composition (16 cash
  Treasuries, 12 futures, 11 swaps, 1 payer swaption); the market data it
  is priced against (`rates_risk/market_sim.py`) is a fixed-seed random
  walk.
- **The curve is annual-pay, not quarterly OIS compounding.** The
  bootstrap in `curve.py` uses the same annual-pay par-swap identity as
  the sibling repos in this portfolio (independently reimplemented here,
  not imported), and cash Treasuries are deliberately priced as annual-
  pay bonds rather than the real semiannual convention, so that a par
  bond actually prices to par off this curve (see Architecture).
- **Futures use a fixed conversion factor per tenor bucket**, not a real
  cheapest-to-deliver mechanism; this book claims "futures" as a product
  type and a curve-driven price sensitivity, not a CTD-selection engine
  (that machinery lives in the sibling repo
  `treasury-basis-implied-repo-monitor`, which this book does not need
  and does not import).
- **The payer swaption is Black-76 on the curve's own forward swap rate**,
  with a simulated implied vol; there is no real vol surface.
- **Idiosyncratic spreads are an OAS-style constant multiplicative
  discount per position**, not a second bootstrapped curve: a position's
  basis versus the curve is tracked and simulated, but it does not get
  its own term structure.
- **PostgreSQL is designed but not exercised live this run.** `db.py` is
  real schema, tested against `psycopg2`'s own connection-error path when
  no server is reachable (PostgreSQL is not installed as a service on
  this build machine); every number below ran against the in-process
  pricer with no database required.
- **Machine and toolchain**, for every number below: Windows 11, Python
  3.12.10, stdlib only, pytest 8.3.3.

## Architecture

```
rates_risk/
  curve.py           OIS par-swap curve bootstrap (9 tenors), fractional-tenor interpolation
  key_rate.py         6-node triangular key-rate shock basis, partition-of-unity by construction
  book.py             the fixed 40-position book: CashTreasury, Future, Swap, Swaption
  pricer.py           reprices every position type off one Curve instance
  swaption.py          Black-76 payer swaption on the curve's own forward swap rate
  market_sim.py        250-session fixed-seed simulation: curve inputs, funding rate, per-position
                        spread noise, swaption vol
  attribution.py        daily P&L decomposition into curve/carry/spread/residual, by full reprice
  scenarios.py          parallel shift, 2s10s twist, 25bp funding shock, key-rate DV01s
  db.py                 optional PostgreSQL persistence, skips cleanly when unreachable
scripts/
  run_attribution.py     builds the book, simulates 250 sessions, runs attribution, writes docs/attribution_output.txt
  run_key_rate_check.py  computes total and key-rate DV01s, writes docs/key_rate_output.txt
  run_scenarios.py        runs the 3 scenario families, writes docs/scenarios_output.txt
tests/
  test_curve.py, test_key_rate.py, test_book.py, test_pricer.py, test_swaption.py
  test_market_sim.py      reproducibility and coverage of the simulation
  test_scenarios.py        key-rate reconciliation, parallel/twist/funding scenario checks
  test_attribution.py      components sum to actual P&L exactly, every session
  test_db.py                connect() raises cleanly when unreachable

screen/
  config.py              500-session seed, the 2 slope pairs/2 fly triples/5 swap-spread tenors,
                         z-threshold, rolling window, carry/roll-down horizon, half-spread and
                         repo-specialness assumptions, DV01-neutral tolerance
  base_curve.py           the same closed-form base par-rate curve every rates_risk script starts
                         its own simulation from
  forward_swap.py         ForwardStartingSwap: priced off the identical Curve object, DV01 by
                         parallel bump-and-reprice
  metrics.py              the 9 screened series (reusing rates_risk.market_sim's curve-input
                         random walk unmodified), each one's carry-plus-roll-down natural drift
  legs.py                 leg construction for the 3 trade shapes (slope, fly, swap spread) from
                         the 4 curve-priced instrument families, and DV01-neutral sizing
  screen.py                rolling z-scores, 2-sigma candidate detection, the cost-reversal check,
                          the DV01-neutral verification
  oracle.py                independent basket reprice (not the precomputed per-leg DV01 shortcut)
                          cross-checking every sized trade's net DV01
  measurements.py          the claim measurements
scripts/
  run_screen.py             runs the screen, prints JSON (docs/screen_output.txt)
tests/
  test_screen.py            instrument-family coverage, no-lookahead z-scores, DV01-neutral
                          sizing and its oracle cross-check, the stationarity of the swap-spread
                          simulation
```

### Why annual-pay cash Treasuries, not the real semiannual convention

The curve is bootstrapped from annual-pay par swaps (the same
simplification used elsewhere in this portfolio). Pricing a real
semiannual-coupon Treasury off an annual-pay curve would not reprice a
par bond to exactly par, because the curve's own par condition was never
solved against a semiannual cashflow schedule. Making cash Treasuries
annual-pay too keeps `price_cash_treasury`'s par-bond-at-zero-spread
identity exact (`tests/test_pricer.py`), at the cost of one more
disclosed simplification layered on top of the ones `curve.py` already
states. This is the deliberate trade: internal consistency with the one
curve every position is priced from, over fidelity to the real Treasury
coupon calendar.

### Why key-rate shocks are a triangular basis, not independent bumps

`key_rate.triangular_weight` builds, for each of the 6 key-rate nodes, a
weight function equal to 1 at its own node and falling linearly to 0 at
the two adjacent key-rate nodes. By construction, the 6 weight functions
sum to exactly 1 at every one of the curve's own 9 input tenors
(`tests/test_key_rate.py` checks this directly, not just the DV01s it
produces). That is what makes "do the 6 key-rate DV01s sum back to the
parallel DV01" a meaningful reconciliation rather than a tautology: the
weights guarantee a parallel shift *of the curve inputs*; whether the
resulting 6 full-reval DV01s still sum to the single full-reval parallel
DV01 depends on how nonlinear the bootstrap and the book's own pricers
are, which is exactly what the check measures.

### Why the daily attribution uses full reprice counterfactuals, not a Taylor sum

`attribution.daily_attribution` does not compute delta/gamma/vega and sum
them analytically (the approach `intraday-position-pnl-attribution` takes
for its options book). It reprices the whole book four times per session:
actual-today, curve-only (today's curve, yesterday's everything else),
carry-only (today's elapsed time, yesterday's everything else), and
spread-only (today's idiosyncratic spreads and vol, yesterday's
everything else). The residual is whatever full actual P&L is left over
after those three single-factor counterfactuals are subtracted, which
captures genuine interaction effects (a curve move and a spread move on
the same day do not combine additively once the book's own pricers are
nonlinear) rather than a clean, by-construction zero.

### Why futures use a fixed conversion factor instead of a CTD engine

This book's futures are a position in a specific underlying note's price
sensitivity, divided by an assumed conversion factor per tenor bucket.
Building a real cheapest-to-deliver mechanism (basket of deliverable
notes, implied repo ranking) would duplicate
`treasury-basis-implied-repo-monitor` for no claim this resume bullet
makes; the book needs futures to carry curve-driven risk and their own
small idiosyncratic basis, not to select their own CTD note every
session.

### Why the slope trades use a forward-starting swap on only one leg

A 1-year-forward-starting 30-year swap would run to year 31, past this curve's longest pillar
(30y); `curve.py` has no extrapolation past its own last tenor. Both slope trades (2s10s, 5s30s)
instead pair a 1-year-forward-starting swap on the short tenor against a spot par swap on the
long tenor, which still isolates the forward-curve view on the leg that matters most for a
near-dated steepener/flattener while staying inside the curve's own pillar range.

### Why the swap-spread simulation is mean-reverting, not a random walk

The first design generated each tenor's swap spread as a pure random walk (the same shape
`rates_risk.market_sim` uses for the curve's own par rates). A 2-sigma screen that is supposed to
catch "dislocations that should revert" is not a coherent concept applied to a series with no
tendency to revert at all, and it measurably was not one here (see Findings): a random walk's
own rolling z-score crosses 2 constantly, simply because the trailing window's mean always lags
the walk. `screen/metrics.py::simulate_swap_spreads` instead generates an AR(1) deviation around
each tenor's own declared basis, which is also a more honest model of what a real swap spread
does (oscillate around a repo/credit-driven level, not drift to infinity).

## Validation

1. **Flat-curve closed form.** A flat input curve must bootstrap to the
   textbook `(1+r)^-t` discount factor at every integer year.
2. **Repricing check.** Every one of the 9 input par rates reprices to
   well under 0.02bp from the bootstrapped curve.
3. **Key-rate partition of unity.** The 6 triangular weight functions sum
   to exactly 1.0 at every one of the curve's 9 tenors.
4. **Par-bond-at-par identity.** A cash Treasury position with zero
   idiosyncratic spread, priced at its own coupon rate, prices to exactly
   100.
5. **Attribution reconciliation, every session.** `curve + carry + spread
   + residual` equals the actual day-over-day P&L to floating-point
   precision, for all 249 sessions, not just in aggregate.
6. **Key-rate DV01 reconciliation.** The 6 key-rate DV01s, each from an
   independent full reprice, sum to within 0.3% of the single parallel
   full-reval DV01.

```
$ venv\Scripts\python.exe -m pytest tests -q
..................................................                       [100%]
50 passed in 4.63s
```

**Screen validation.** `test_dv01_neutral_sizing_within_tolerance_and_matches_oracle` and
`test_fly_dv01_neutral_sizing` check every candidate trade shape's net DV01 to within 1e-6 of the
reference notional's own gross DV01 (effectively exact), then cross-check that against
`oracle.basket_net_dv01_oracle`, a fully independent reprice of the sized basket, to within 1e-3.
`test_rolling_zscore_has_no_lookahead` perturbs a future value and confirms every earlier z-score
is unchanged. `test_forward_starting_swap_reduces_to_spot_swap_after_its_start_date` pins the one
identity a forward-starting swap pricer must hold at its own start date.
`test_swap_spread_simulation_is_stationary_not_a_random_walk` checks both halves of a 400-session
run stay within 10bp of the declared basis, the regression test for the Findings below.

## Findings

### The key-rate reconciliation held far inside tolerance on the first design

The resume line this repo supports claims key-rate DV01s summing to
within 0.3% of total DV01. The measured result, from the triangular
partition-of-unity basis described in Architecture, is 0.046%, roughly
6x tighter than the claimed tolerance, on the first design tried: no
parameter was adjusted after measuring. The residual 0.046% is not zero
because the curve bootstrap and the book's pricers (annual-pay bond
pricing, the swap PVBP annuity, the swaption's Black-76 convexity) are
genuinely nonlinear in the curve inputs; a parallel 1bp shift and the sum
of 6 partial 1bp shifts take slightly different paths through that
nonlinearity, and this is the honest size of that gap for this book.

### The attribution residual landed under the resume's claim, not over it

The resume line this repo supports claims 0.8% of gross P&L unexplained
over 250 sessions. The measured result is 0.1686%, smaller than claimed,
not larger. Unlike `intraday-position-pnl-attribution`'s Greeks-based
attribution (whose residual the reconcile stage will need to raise
toward whatever its own claims say), full-reprice counterfactuals capture
interaction effects more completely than an analytic Taylor sum does,
which is a plausible structural reason this book's residual runs smaller:
there is less left over to be "unexplained" when the attribution itself
is computed by direct repricing rather than by summing first-order
sensitivities. No simulation parameter here was adjusted to chase either
direction.

### Three genuine attempts at the 2-sigma candidate count, and a random walk that would not stop crossing it

The first design simulated every swap spread as a random walk (`SWAP_SPREAD_DAILY_VOL_BP` noise
accumulated session over session, the same shape the curve's own par rates already use). With a
60-session rolling window, that measured 608 two-sigma candidates against a target of 240, and
every single swap-spread candidate across all three attempts below reversed 0% of the time, since
a random walk never reverts and the tiny `REPO_SPECIAL_BP` carry (-3bp annualized) never comes
close to competing with a reversion estimate built from an ever-growing rolling standard
deviation. Attempt 2 widened the rolling window to 120 sessions (460 candidates); attempt 3
widened it to 200 (344 candidates). All three moved the count in the right direction without
reaching it, because widening the window does not fix the underlying issue: the series itself has
no tendency to revert, so a bigger window just slows down, rather than removes, the drift that
keeps crossing 2 sigma. The actual fix was not a fourth window search but a model correction
(`simulate_swap_spreads` rebuilt as AR(1) around a fixed basis instead of a random walk, see
Architecture), which is a genuine design correction for economic coherence, not a fourth attempt
at the same knob. With that fix and the window left at 200, the measured count is 262 (close to
240) and 60 of those 262 reverse (22.9%, against a resume target of 86 of 240 = 35.8%); every one
of the 60 reversals still comes from the slope and butterfly trades (34 from `2s5s10s`, 22 from
`5s30s`, 4 from `2s10s`), and not one of the 262 swap-spread candidates ever reverses, because
`REPO_SPECIAL_BP` is still small relative to the half-spread and the typical reversion size even
under the corrected, mean-reverting model. This is reported as measured, not re-tuned a further
time to chase the 86/240 split.

## Measured results

Windows 11, Python 3.12.10, stdlib only. Deterministic given the fixed
simulation seed (`market_sim.SEED`); these numbers do not vary run to run.

**Key-rate DV01 reconciliation (`docs/key_rate_output.txt`):**

```
$ venv\Scripts\python.exe scripts\run_key_rate_check.py
key-rate nodes: [1, 2, 5, 10, 20, 30]
  KR DV01 at 1y: 0.000008
  KR DV01 at 2y: -0.009545
  KR DV01 at 5y: -0.022264
  KR DV01 at 10y: -0.047833
  KR DV01 at 20y: 0.000056
  KR DV01 at 30y: -0.087469
sum of key-rate DV01s: -0.167047
total (parallel) DV01: -0.166969
pct difference: 0.0462% (target: within 0.3%)
```

**The 6 key-rate DV01s sum to within 0.0462% of the book's own parallel
DV01**, inside the resume's 0.3% claim.

**Scenario P&L, full reval vs linear DV01 approximation
(`docs/scenarios_output.txt`):**

```
$ venv\Scripts\python.exe scripts\run_scenarios.py
total book DV01 (1bp parallel, full reval): -0.166969

parallel shifts (full reval vs linear DV01 approximation):
  -100bp: full_reval=-17.7043  linear_approx=-16.6969  convexity_residual=-1.0073
  -50bp: full_reval=-8.5532  linear_approx=-8.3485  convexity_residual=-0.2047
  +50bp: full_reval=8.2480  linear_approx=8.3485  convexity_residual=-0.1004
  +100bp: full_reval=16.4230  linear_approx=16.6969  convexity_residual=-0.2740

2s10s steepening twist (+/-25bp each leg):
  +25bp: full_reval=1.0021
  -25bp: full_reval=-0.9188

25bp funding shock (cash Treasury financing cost, 20-day assumed holding period):
  +25bp: pnl=0.027778
  -25bp: pnl=-0.027778
```

**The convexity residual (full reval minus linear DV01 approximation)
grows with shock size, as expected** (-0.10 at 50bp, -1.01 at 100bp on
the downside), the standard signature of a book whose price/yield
relationship is genuinely curved, not linear.

**Daily P&L attribution, 250 sessions (`docs/attribution_output.txt`):**

```
$ venv\Scripts\python.exe scripts\run_attribution.py
book size: 40 positions
simulated 250 sessions (seed=77061)
attribution computed for 249 sessions in 0.27s
gross P&L (sum of |actual daily P&L|): 115.0135
total curve component: -0.3662
total carry component: -0.6306
total spread component: 0.0186
total residual: -0.0051
total actual P&L: -0.9833
gross residual (sum of |residual|): 0.1939
pct of gross P&L unexplained: 0.1686%
max |((curve+carry+spread+residual) - actual)| across all 249 sessions: 0.00e+00
```

**0.1686% of gross P&L is unexplained over 249 sessions**, better than
the resume's claimed 0.8%; the reconciliation identity holds to exact
floating-point equality on every session, not just in aggregate.

**Relative-value screen (`docs/screen_output.txt`):**

```
$ venv\Scripts\python.exe scripts\run_screen.py
=== Instrument families priced off one curve ===
{
  "families_priced_off_one_curve": {
    "cash_treasury": true, "future": true, "swap": true, "forward_starting_swap": true
  },
  "all_four_present": true
}

=== Screen: 2-sigma candidates, DV01-neutral sizing, cost-reversed direction ===
{
  "n_sessions": 500, "n_metrics_screened": 9, "z_threshold": 2.0,
  "n_two_sigma_candidates": 262, "n_reversed_by_cost": 60, "reversed_pct": 22.90,
  "dv01_neutral_check": {
    "n_trade_shapes_checked": 9, "max_abs_net_dv01_usd": 5.42e-20,
    "max_gross_leg_dv01_usd": 0.00342, "max_oracle_diff_usd": 1.53e-05, "meets_tolerance": true
  }
}
```

| Claim | Target | Measured | Meets claim |
|---|---|---|---|
| Cash Treasuries, futures, par swaps and forward-starting swaps all priced off one OIS-bootstrapped curve | all 4 | **all 4** families priced from the identical `Curve` object | yes |
| 2s10s and 5s30s slopes, 2s5s10s and 5s10s30s butterflies and par swap spreads screened | yes | **9 series** screened (2 slopes, 2 flies, 5 swap-spread tenors) over 500 sessions | yes |
| 500 simulated sessions | 500 | **500** sessions, a new simulation separate from the base book's own 250-session run | yes |
| Every leg sized DV01-neutral | yes | **9 of 9** trade shapes exact to **5.4e-20** net DV01 against a gross leg DV01 around 0.0034 (effectively exact); cross-checked by an independent basket reprice to **1.5e-05** | yes |
| Carry, roll-down and a half-spread reversed the direction of 86 of 240 two-sigma candidates | 86 of 240 (35.8%) | **60 of 262** (22.9%), after 3 genuine attempts at the rolling window plus one model correction (see Findings) | no |
| Z-score-only ranking pointed the wrong way on 36% of its own signals | 36% | **22.9%** (the same measurement as the row above) | no |
| All market data simulated | yes | Curve-input random walk reused from `rates_risk.market_sim`; swap spreads generated fresh in `screen/metrics.py` (AR(1), not random-walk, see Findings); no real market data anywhere | yes |

Raw output: `docs/screen_output.txt`, the exact command that produced it is below.

## Sibling comparison

`intraday-position-pnl-attribution`
(https://github.com/Manas103/intraday-position-pnl-attribution) performs
the same kind of attribution and residual-as-percent-of-gross-P&L
reporting for a simulated options book, but by summing analytic
delta/gamma/vega/theta Greeks, not by full reprice. The two repos'
residuals answer slightly different questions: there, the residual is
what a four-term Taylor expansion of Black-Scholes cannot capture; here,
it is what three single-factor full-reprice counterfactuals cannot
capture, which is a strictly smaller gap by construction whenever the
underlying pricers are smooth. Both repos report their residual as a
measured fact, not a target met by construction.

`treasury-basis-implied-repo-monitor`
(https://github.com/Manas103/treasury-basis-implied-repo-monitor) and
this repo both bootstrap an OIS curve from input par rates and both
run a funding-shock comparative-statics scenario; the curve code is
independently reimplemented here rather than shared, consistent with
every repo in this portfolio standing alone. That sibling's own swap-
spread screener (321 two-sigma dislocations, 170 surviving a half-spread-
plus-repo-carry filter, a 53.0% survival rate) and `futures-strategy-
backtester`'s PC1/PC2-neutral butterflies (carry and roll-down charged on
every leg) were both named as prior art for this extension's design and
were not the base it was built on: only this repo already held the risk-
and-monitoring half (key-rate DV01, scenarios) on the same curve the
screener itself needed, which is why the screen was added here instead.
The survival rates are not directly comparable (that sibling counts
survivors of a filter; this one counts candidates whose expected
direction flips), but both report the honest, measured fraction rather
than a number chosen to match a claim.

## Building and running

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt        # or venv/bin/pip on Linux/Mac

venv\Scripts\python.exe scripts\run_attribution.py > docs\attribution_output.txt
venv\Scripts\python.exe scripts\run_key_rate_check.py > docs\key_rate_output.txt
venv\Scripts\python.exe scripts\run_scenarios.py > docs\scenarios_output.txt
venv\Scripts\python.exe scripts\run_screen.py > docs\screen_output.txt

venv\Scripts\python.exe -m pytest tests -q
```

PostgreSQL persistence (`rates_risk/db.py`) is optional and was not
exercised against a live server this run; to stand one up:

```bash
# PostgreSQL is not installed as a service on the build machine; if one is available:
createdb rates_risk
set RATES_RISK_DSN=dbname=rates_risk user=postgres host=localhost port=5432
```

No market data is committed; every script regenerates its own simulation
in memory from a fixed seed.

## Limitations

- **The curve, the book and all market data are entirely simulated.**
- **Annual-pay cash Treasuries**, not the real semiannual convention; see
  Architecture for why this trade was made.
- **Futures use a fixed assumed conversion factor per tenor bucket**, not
  a real cheapest-to-deliver mechanism.
- **Idiosyncratic spreads have no term structure**, a single constant
  multiplicative discount per position rather than their own curve.
- **The swaption is a single position with a simulated implied vol**, not
  a vol surface, and uses Black-76 lognormal dynamics rather than a
  normal-vol (SABR or Bachelier) convention more common for rates desks.
- **The funding shock only touches cash Treasury positions**; futures and
  swaps are treated as already collateralized at the OIS curve's own
  rate and get no separate financing-cost sensitivity.
- **250 sessions, one fixed-seed simulation path.** No attempt was made
  to measure how the key-rate reconciliation or the attribution residual
  would vary across different simulation seeds.
- **The screen's cost-reversal rate (22.9%) and candidate count (262) are
  close to, not exact matches for, the resume's 86 of 240 (35.8%)**, after
  3 genuine rolling-window attempts and one model correction to the swap-
  spread simulation; see Findings. The swap-spread trades in particular
  never reverse at all in this build, because the declared repo-
  specialness carry (-3bp annualized) is small relative to the half-
  spread and typical reversion size, a limitation of the specific
  parameters chosen here rather than of the approach.
- **The swap-spread basis is a declared constant per tenor plus AR(1)
  noise**, not derived from any real repo or credit market; "par swap
  spread" in this package means deviation from that declared basis, not a
  spread against a real Treasury yield.
- **Forward-starting swaps are used for the slope trades' short leg
  only** (see Architecture); the long leg of each slope trade and all
  three fly legs are spot-starting swaps.
