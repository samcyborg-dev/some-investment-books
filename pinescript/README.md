# RangeLab ORB-30R Advanced Pine Script

File: `pinescript/RangeLab_ORB30R_Advanced.pine`

This is an advanced TradingView **strategy script for research, backtesting, paper testing and alerts**. It is not a broker EA and does not place live orders.

## What is implemented

- Pine Script v6 strategy declaration.
- New York timezone-aware 09:30–16:00 cash-session clock.
- 09:30–10:00 six-bar opening range.
- 10:00–13:30 prospective entry window.
- 15:45 close-generated exit order intended to fill at the 15:50 bar open.
- One fill per session.
- RTH-only causal EMA20/EMA50 state.
- RTH-only Wilder ATR14 state.
- 250 completed RTH-bar warm-up gate.
- Range-width gate of 5 ATR.
- One-tick stop entries, with already-crossed trigger protection.
- Frozen ATR at order arming.
- Initial 1.2 ATR stop and 2.0 ATR target with directional tick rounding.
- Integer ES/MES position sizing with an equity-risk allowance, fee reserve and slippage reserve.
- Optional trailing-stop experiment, disabled by default and visibly marked when enabled.
- Strategy commission and one-tick slippage properties.
- Free-plan-compatible strategy declaration with Bar Magnifier disabled.
- Opening-range, indicator, stop, target, order, fill and status-table diagnostics.
- Alert conditions that describe modeled events and explicitly warn that they are not broker fills.

## Add it to TradingView

1. Open TradingView in Chrome.
2. Open **Pine Editor**.
3. Create a new blank strategy.
4. Copy all text from `RangeLab_ORB30R_Advanced.pine` into the editor.
5. Click **Save**, then **Add to chart**.
6. Use a **5-minute standard candlestick chart**. The status table will show `Use 5m` if the chart is on another timeframe.
7. Open **Strategy Tester → Settings → Properties** and verify:
   - initial capital;
   - commission per contract;
   - slippage in ticks;
   - the broker symbol's tick size.

## ES versus MES costs

The script declaration uses a compile-time default of `$5` commission per contract and one tick of slippage. TradingView also allows the commission and slippage properties to be changed in the strategy's Properties panel.

For a common MES research assumption, change the strategy Properties commission to `$2` per contract and leave one tick of slippage if that is the frozen test assumption. Also set the script inputs to:

- `Sizing instrument = MES`
- `Research tick size = 0.25`
- `Maximum integer contracts` to the intended cap
- `Round-trip fee reserve / contract` to the same fee used in Properties

The fee-reserve input is used for integer sizing. The actual TradingView strategy P&L uses the Properties-panel commission setting. Keep those values synchronized.

## Important TradingView limitations

- A TradingView bar is not a broker fill. Alerts are notifications only unless separately connected and authorized.
- The 15:50 open liquidation is modeled by submitting a close order on the 15:45 bar. Use a five-minute chart; other timeframes cannot represent the frozen timing exactly.
- Bar Magnifier is intentionally disabled so the script runs on TradingView's free plan. A paid plan may allow a separate Bar Magnifier experiment, but that does not provide a tick-level queue, exchange order book, broker margin model or guaranteed fill.
- The script cannot prove that ORB-30R is the best-performing ORB. The repository still lacks an accepted long-window independent ES/MES dataset.
- The optional trailing stop is a separate experiment, not part of the frozen baseline. Leave it off for baseline tests.
- Use standard candles, not Heikin Ashi, Renko, Range, Kagi or other synthetic chart types.
- Export or record the Strategy Tester report together with symbol, contract specification, timeframe, date range, commission, slippage, timezone, script version and input settings.

## Evidence boundary

The script is an implementation of the frozen research specification so that forward and paper results can be returned consistently. It does not turn the proposal into a validated edge, exchange-certified history or live performance record. Keep ES and MES results separate and report undefined metrics honestly when the sample is too small.
