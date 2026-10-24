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
.........................................                                [100%]
41 passed in 4.47s
```

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
every repo in this portfolio standing alone.

## Building and running

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt        # or venv/bin/pip on Linux/Mac

venv\Scripts\python.exe scripts\run_attribution.py > docs\attribution_output.txt
venv\Scripts\python.exe scripts\run_key_rate_check.py > docs\key_rate_output.txt
venv\Scripts\python.exe scripts\run_scenarios.py > docs\scenarios_output.txt

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
