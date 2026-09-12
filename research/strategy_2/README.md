# Strategy 2 - Statistical Z-Score Mean Reversion

**Status:** preflight and causal-specification review only
**Date:** 12 September 2026 (Africa/Nairobi)
**Performance status:** no accepted ES/MES result

## Purpose

Strategy 2 is the next recommended prop-firm research track after the ORB-30R baseline. It is an intraday mean-reversion candidate using a standardized price deviation, an exhaustion filter, and a low-trend regime gate.

This directory deliberately does **not** contain a performance claim. The existing Python strategy can generate output from synthetic or unaudited data; those outputs are not project-owned evidence. An authorized, independently checked ES and MES five-minute dataset is required before any result is published or used in a walk-forward record.

## Candidate rule set to make explicit

The source material contains conflicting values and incomplete timing details. The following is a candidate specification for review, not a silently frozen result:

- Instrument: ES and MES analyzed independently; do not convert ES into MES.
- Chart/data: five-minute standard candles, with explicit timezone-aware timestamps.
- Session: New York regular trading hours 09:30-16:00 ET.
- Indicator state: update only on RTH bars; no overnight bars and no backward filling.
- Mean: causal EMA20 of RTH close.
- Dispersion: causal 20-bar standard deviation of RTH close.
- Z-score: `(close - EMA20) / StdDev20`.
- RSI: Wilder RSI14, calculated causally on RTH observations.
- Regime: Wilder ADX14 below 25. The existing Python default of 28 is not the candidate value.
- Long signal: Z-score at or below -1.8, RSI below 32, and ADX below 25.
- Short signal: Z-score at or above +1.8, RSI above 68, and ADX below 25.
- Entry timing: signal on a completed five-minute bar and a next-bar order/fill model. The final entry window must be written with bar labels and fill timing, not only clock strings.
- Proposed entry window: 10:15-15:05 ET signal bars so a next-bar fill is not later than 15:10 ET. This replaces the ambiguous 10:15-15:15 implementation until reviewed.
- Exit target: conditional mean touch (Z returning to 0) or a fixed 1.8 ATR target, with the choice and priority documented before testing.
- Structural stop: Z-score at or beyond 3.2 against the position, or a fixed 1.5 ATR protective stop.
- Position limit: one open position; maximum four completed trades per session is a candidate prop rule and requires a separate risk review.
- End of day: submit a close order on the 15:45 ET bar for the intended 15:50 ET open. Shortened sessions need explicit handling.
- Sizing: integer ES/MES contracts, tick rounding, fee reserve, slippage reserve, and a skip when one contract exceeds the risk budget.
- Risk controls: daily realized plus modeled open P&L kill-switch, total-loss circuit breaker, and a clear statement that chart-bar surveillance cannot guarantee a prop-firm floor.

Where a rule remains undecided, the test must be labeled exploratory rather than baseline.

## Audit of the existing Python module

File reviewed: `quant_engine/strategies/prop_mean_reversion.py`.

### Blocking issues

1. **Backward-filled indicators can use future observations.** `ATR`, rolling standard deviation, RSI, directional movement, and ADX use `bfill()` at lines 82, 86, 95, and 103-107. A warm-up must remain undefined until enough past observations exist.
2. **Indicators are not RTH-only.** The module computes from the whole input frame and does not explicitly separate overnight, RTH, holidays, early closes, or the New York timezone.
3. **The fill chronology is not explicit.** Signals use the current close and the portfolio opens at that same bar's price at lines 217-249 and 252-275. A causal implementation must specify whether the order is at the close or the next bar and include latency/slippage once.
4. **OHLC ordering is ambiguous.** Position management checks the target before the stop on a bar that can touch both, at lines 165-215. A five-minute OHLC bar does not reveal which barrier occurred first.
5. **Contracts are fractional.** Lines 233 and 259 use a minimum of `0.2` and round to two decimal places. ES and MES must use integer contracts and skip a trade when one contract is too large for the budget.
6. **The target rule differs from the candidate.** Longs exit when `z >= 0.5` and shorts when `z <= -0.5`, rather than a documented mean-touch rule at Z near 0.0. The ATR target is also a separate choice that must be frozen before testing.
7. **The default ADX gate is 28, not 25.** This is a variant, not the candidate described in the source specification.
8. **The EOD exit uses the current price.** At lines 148-159 it closes at the current bar price after `15:50:00`, rather than modeling the 15:45-generated order and 15:50 open.
9. **Risk controls are not continuous protection.** The risk manager is checked before a new trade. It does not guarantee intrabar liquidation when a daily or total floor is touched, especially during a gap.
10. **Synthetic/unaudited metrics must remain blocked.** The module appends DSR, Harvey, and challenge Monte Carlo outputs at lines 282-302 even though the inputs and sample are not accepted ES/MES evidence. Those outputs must not be reported as validation.

### Accounting and data issues to fix or re-audit

- Commission is charged in the portfolio engine, but the strategy's fee reserve, actual P&L cost, and slippage convention need one reconciled definition.
- A random slippage component in the portfolio engine makes a run non-reproducible unless the random seed and execution convention are controlled.
- `Date` and `HourMin` are derived from the input index without an intake assertion for timezone, ordering, duplicates, contract identity, or session calendar.
- A single `bar_idx` is reset for each day, which makes cross-day holding or global trade chronology unsuitable without an explicit audit.
- Stop, target, and market exits need a deterministic same-bar policy or lower-timeframe/sequence evidence.
- No parameter search may be run until the data artifact and the causal execution kernel pass acceptance.

## Data gate before any performance run

ES and MES each require an independent intake record:

1. Source/license description, acquisition timestamp, archive/file list, and SHA-256.
2. Native timestamp convention and conversion to an explicit timezone-aware index.
3. Contract or continuous-series identity and roll/adjustment treatment.
4. Five-minute alignment, monotonic timestamps, duplicate/conflicting duplicate counts.
5. OHLC validity, 0.25-point tick-grid checks, nonnegative volume, missing bars, and incomplete sessions.
6. New York RTH session counts, overnight separation, holidays, and early closes.
7. A quality receipt stating accepted, rejected, or plumbing-only. Never fill missing bars or relabel ES as MES.

A short public Yahoo intraday snapshot may be used to test parsing and the receipt pipeline, but it is vendor-reported and not equivalent to broker or exchange-direct history. It is not sufficient by itself for a long-window project-owned Strategy 2 result.

## Walk-forward design after acceptance

Keep the frozen candidate as a benchmark. Do not optimize it using the current ORB week or a future OOS block.

- Preferred fold: 12 weeks in-sample, then 4 weeks out-of-sample, rolling by 4 weeks.
- Short-history fallback: 8 weeks in-sample, then 2 weeks out-of-sample, clearly labeled low-power.
- Select a robust parameter plateau from the in-sample data, not a single best point.
- Seal each OOS report before using it for any later choice.
- Combine only sealed OOS trades for the walk-forward record.
- Report ES and MES separately, with undefined metrics left undefined when the sample cannot support them.

## Immediate next work

1. Review and approve the candidate timing and target-priority choices above.
2. Build the data intake/quality receipt for independent ES and MES.
3. Rewrite or isolate a causal execution kernel; do not call the existing synthetic engine a validated backtest.
4. Add unit tests for warm-up, RTH boundaries, next-bar fills, integer sizing, same-bar stop/target ambiguity, EOD flatness, daily kill-switch behavior, and roll/session identity.
5. Only after those gates pass, run the first chronological walk-forward fold.
