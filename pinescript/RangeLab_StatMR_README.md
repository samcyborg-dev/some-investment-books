# RangeLab Statistical Mean Reversion Advanced

File: `pinescript/RangeLab_StatMR_Advanced.pine`

This is the candidate TradingView implementation for Strategy 2, the prop-firm statistical Z-score mean-reversion track. It is for research and paper observation only. It does not place broker orders and has no accepted ES/MES performance result.

## Free TradingView setup

1. Open Pine Editor and create a blank strategy.
2. Delete the existing editor contents completely.
3. Paste `RangeLab_StatMR_Advanced.pine`. The first line must be `//@version=6`.
4. Save and add it to a **5-minute standard candlestick** chart.
5. Use ES and MES in separate tests. `ES1!` is a continuous TradingView symbol; record it as such and do not treat it as a broker fill record.
6. Leave Bar Magnifier disabled. The script is configured with `use_bar_magnifier = false` for the free plan.
7. Verify commission, slippage, initial capital, symbol and date range in Strategy Tester Properties.

## Candidate rules

- RTH clock: 09:30-16:00 America/New_York.
- Indicators update only on RTH bars and do not use backward fills.
- Mean: causal RTH EMA20.
- Z-score: current RTH close minus EMA20 divided by causal RTH 20-bar standard deviation.
- RSI: causal Wilder RSI14.
- Regime: causal Wilder ADX14 with ADX below 25.
- Long signal: Z <= -1.8 and RSI < 32 in the low-ADX regime.
- Short signal: Z >= +1.8 and RSI > 68 in the low-ADX regime.
- Signal window: 10:15-15:05 ET. A completed signal bar submits a market order intended for the next bar open.
- Target: the nearer of a frozen mean target and a 1.8 ATR target.
- Stop: 1.5 ATR protective stop, plus a structural Z-score stop at |Z| >= 3.2.
- Maximum four completed fills per RTH session; one open position at a time.
- Close order: submit during the 15:45 bar for the intended 15:50 ET open.
- Position size: integer ES/MES contracts only, with fee and slippage reserves. An unaffordable one-contract trade is skipped by default.
- Daily soft halt: 2.5% modeled equity drawdown. Total-loss circuit breaker: 8% from initial strategy capital.

The daily and total guards are chart-bar calculations. They are not guaranteed intrabar prop-firm or broker protection. If the stop and target are both touched inside one ordinary five-minute bar, TradingView's broker emulator cannot prove their order without higher-detail data.

## Why this is a candidate, not evidence

The earlier Python module is not used as a validated backtest. Its preflight audit found backward-filled indicators, whole-frame rather than RTH-only calculations, ambiguous target-first same-bar exits, fractional ES/MES quantities, an ADX default of 28, and incomplete causal EOD/risk handling. See `research/strategy_2/README.md` for the full audit and data gates.

No Strategy 2 performance claim should be published until an independent ES and MES five-minute dataset passes provenance, timestamp, session, duplicate, OHLC, tick-grid, volume, and roll/adjustment checks. Public Yahoo intraday history can be used for plumbing but is not equivalent to broker or exchange-direct history.

## What to record

For every week, save the Strategy Tester summary, List of Trades, chart screenshot, script version, inputs, symbol, data source, commission, slippage, date range, and any manual intervention. Preserve no-trade sessions. Never retune the script using a sealed out-of-sample block.
