# RangeLab ORB-30R Advanced
## User, testing, and walk-forward manual

**Document date:** 12 September 2026
**Script:** `pinescript/RangeLab_ORB30R_Advanced.pine`
**Use:** research, backtesting, paper testing, and alert observation only

> **Important boundary:** This is not a broker execution system, does not place live orders, and does not prove profitability. A TradingView strategy fill is a modeled fill. Keep ES and MES results separate and treat one week of results as an observation, not as evidence of a durable edge.

---

## 1. What this script is

RangeLab ORB-30R Advanced is a TradingView Pine Script strategy implementing the frozen ORB-30R research specification. It tests a 30-minute opening-range breakout during the US cash session, with a trend filter, a range-width gate, stop-entry protection, ATR-based exits, integer contract sizing, modeled costs, and diagnostics.

The script is deliberately configured for the free TradingView plan. **Bar Magnifier is disabled** because TradingView charges for higher-detail historical intrabar calculation on plans that support it. The baseline therefore uses the chart's ordinary five-minute bars.

The strategy is intended to answer a narrow research question:

> When the exact rules are applied consistently to an ES or MES five-minute series, what are the modeled entries, exits, costs, drawdowns, and out-of-sample results?

It is not intended to answer whether a broker will fill the order at the displayed price or whether future profits are guaranteed.

---

## 2. Frozen baseline rules

Use these rules for the baseline. Do not change them after seeing a result and still call that result an untouched out-of-sample result.

| Rule | Baseline implementation |
|---|---|
| Chart | Five-minute, standard candlesticks |
| Clock | `America/New_York` |
| Cash session | 09:30-16:00 ET, Monday-Friday |
| Opening range | 09:30-10:00 ET; six completed five-minute bars |
| Entry window | 10:00-13:30 ET |
| Exit | Submit close order during the 15:45 bar; intended fill at the 15:50 bar open |
| Trade count | Maximum one fill per session |
| Trend filter | Prior completed RTH close versus causal RTH EMA20 and EMA50 |
| Volatility | Causal RTH Wilder ATR14 |
| Warm-up | 250 completed RTH bars |
| Range gate | Opening-range width must be no more than 5 ATR |
| Entry | One research tick beyond the opening-range high or low |
| Crossed-entry protection | Do not pretend to fill a stop order if the bar has already crossed it before the order is eligible |
| Initial stop | 1.2 ATR from entry, rounded directionally to the tick grid |
| Target | 2.0 ATR from entry, rounded directionally to the tick grid |
| Trailing | Disabled for the frozen baseline |
| Sizing | Integer contracts, equity-risk allowance, fee reserve, and slippage reserve |
| Bar Magnifier | Off for free-plan compatibility |

The chart in the supplied screenshot was `ES1!`. That is a continuous futures symbol, not necessarily the exact contract that a broker would fill. Record the symbol and data source with every test. If possible, compare the continuous chart with the actual front-month contract used for paper or live observation.

---

## 3. Correct TradingView installation

1. Open TradingView in Chrome.
2. Open **Pine Editor**.
3. Create a new blank strategy.
4. Press **Ctrl+A**, then **Delete**. This avoids leaving the MT5 exporter in the editor.
5. Paste the complete contents of `RangeLab_ORB30R_Advanced.pine`.
6. The first line must be exactly:

   `//@version=6`

7. The source must contain `strategy(` and `use_bar_magnifier = false`.
8. Click **Save**, then **Add to chart**.
9. Select a **5m** chart and standard candles. Do not use Heikin Ashi, Renko, Range, Kagi, or another synthetic chart type.
10. Open **Strategy Tester -> Settings -> Properties** and verify initial capital, commission, slippage, and symbol settings.

Do not paste `mt5/RangeLab_HistoryExporter.mq5`. That is an MQL5 exporter for MetaTrader and will produce a translation error in Pine Editor. It contains lines such as `#property strict` and `input ENUM_TIMEFRAMES`; those lines do not belong in a Pine script.

### What a healthy chart should show

- The strategy name appears in the chart legend.
- The status table appears at the upper right if `Show status table` is enabled.
- The table says `5m OK`, not `Use 5m`.
- The opening-range high and low are plotted during RTH if enabled.
- Strategy Tester loads without a runtime error.
- There is no request to upgrade for Bar Magnifier.

If there are no trades, that does not automatically mean the script is broken. The 250-RTH-bar warm-up, range gate, trend gate, one-trade limit, and crossed-stop protection can legitimately reject a session.

---

## 4. Inputs and cost settings

### Session and clock

Leave the timezone as `America/New_York` and use the default cash-session windows for the baseline. The chart's display timezone does not change the script's session calculations; the script uses the selected session timezone.

### Risk and sizing

The default instrument is ES:

- ES point value: approximately $50 per index point.
- MES point value: approximately $5 per index point.
- Research tick size: 0.25 points.
- Default equity-risk allowance: 0.50 percent.
- Default maximum contracts: 1.

For an MES test, set:

- `Sizing instrument = MES`;
- `Research tick size = 0.25`;
- `Round-trip fee reserve / contract` to the fee assumption used in your test;
- `Maximum integer contracts` to the intended cap.

The fee reserve is used by the script when deciding whether an integer contract is affordable. TradingView's Strategy Properties commission is what affects modeled strategy P&L. Keep the fee-reserve input and the Properties-panel assumption consistent, and write both into your research log.

The slippage reserve is used for sizing. The strategy declaration also models one tick of slippage. These are separate safeguards, so document exactly what each one means in your report.

### Baseline versus trailing experiment

Leave `Enable separate trailing experiment` off for the frozen baseline. If it is turned on, label that run as a different variant. Never mix its trades with the frozen baseline in one performance claim.

---

## 5. What to save from each test

A result is not reproducible unless its conditions are saved. For each ES or MES run, archive:

1. Strategy Tester **Overview** or **Performance Summary**.
2. Strategy Tester **List of Trades** export, if available.
3. A chart screenshot showing the symbol, timeframe, date range, and strategy name.
4. The complete input values.
5. Strategy Properties: initial capital, commission, slippage, and order settings.
6. Symbol details: ES or MES, continuous or dated contract, exchange/data source, and session setting.
7. The script version or a copy of the source file.
8. Any data gaps, TradingView warnings, runtime errors, or manual interventions.

Never overwrite an earlier report after changing an input. Give every run an ID, for example:

`ES_5m_ORB30R_baseline_2026-09-12_v1`

---

## 6. How to interpret this week's results

One week normally provides roughly five cash-session observations, and often fewer actual fills because the filters can skip sessions. That is far too small to estimate a stable win rate, expectancy, profit factor, or maximum drawdown.

Classify this week's result as:

> **Forward observation - sample too small for a performance conclusion.**

A positive week is not a reason to increase size. A negative week is not a reason to change the rules. Both outcomes are useful if the execution and data were recorded correctly.

Before doing anything else, freeze and archive:

- the exact script source;
- the exact chart symbol and timeframe;
- the date range;
- all inputs;
- commission and slippage settings;
- the list of trades;
- the summary metrics;
- your notes about whether each order was actually observable or only modeled.

If the settings were fixed before the week began, the week can be labelled a genuine forward observation. If settings were changed after seeing earlier bars or trades, label it a post-hoc or exploratory result instead. Do not relabel it as clean out-of-sample evidence.

---

## 7. Walk-forward testing: the correct idea

Walk-forward testing separates **information used to choose a rule** from **future information used to evaluate it**.

- **In-sample (IS):** the historical window available when parameters are chosen or frozen.
- **Out-of-sample (OOS):** the next period, kept untouched until the choice is locked.
- **Walk-forward:** move the window forward, lock each choice, and evaluate the following unseen period.

A valid cycle is:

1. Choose a training window.
2. Use only that window to select or confirm parameters.
3. Lock the selected version and settings.
4. Run the next future window without changing anything.
5. Seal and archive the OOS result.
6. Move forward and repeat.
7. Combine only the sealed OOS results for the walk-forward record.

If you look at this week's P&L and then change the stop, target, range gate, or session before recording it, you have used the OOS result to train the next version. That is allowed as a research iteration, but it is no longer an untouched evaluation of the previous version.

---

## 8. Recommended plan from today

Because you already have this week's results, use the following sequence.

### Stage 0 - Freeze this week now

Call the current script and settings **Baseline v1**. Do not optimize from this week's outcome. Archive the report and list of trades. Record whether this week was positive, negative, or flat only as a descriptive fact.

### Stage 1 - Build a clean forward block

Run Baseline v1 unchanged for the next three to seven weeks. This gives a first forward block of approximately four to eight weeks including the week already observed. Record every session, including no-trade days.

At this stage the goal is operational validity:

- Did the script load without runtime errors?
- Was the chart really five-minute standard data?
- Were the sessions and exits at the intended New York times?
- Were there duplicate fills or missing fills?
- Were commission and slippage settings present?
- Was any manual intervention made?

Do not change parameters to improve the weekly total.

### Stage 2 - First formal walk-forward cycle

Once enough history is available, use a pre-declared rolling design such as:

- **12 weeks IS, then 4 weeks OOS, roll forward by 4 weeks**, or
- **8 weeks IS, then 2 weeks OOS** when the available history is shorter.

The longer design is preferable for a one-trade-per-session system because it gives more trades in the training window. Neither design makes a small sample statistically certain; the purpose is to expose instability and look-ahead bias.

For each fold:

1. Freeze the current code version.
2. Use only the IS period for any permitted parameter selection.
3. Select a robust region, not the single best historical setting.
4. Lock the chosen settings before the OOS start date.
5. Run OOS with no edits.
6. Archive the OOS report separately.
7. Roll forward and repeat.

The frozen ORB-30R baseline should remain as a permanent benchmark in every fold. If you test variants, compare each variant against that benchmark rather than replacing it.

### Stage 3 - Promotion decision

Do not promote from paper observation to larger size because of one good week. Require:

- valid and reproducible data;
- no unresolved script or timing errors;
- enough completed sessions and trades for the chosen metrics to be defined;
- results after modeled commission and slippage;
- drawdown within a pre-declared risk budget;
- performance that is not dependent on one unusually large trade;
- similar behavior across more than one OOS fold;
- ES and MES reviewed independently;
- no evidence that the parameter choice used future OOS information.

If a metric is undefined because there are too few trades, report it as undefined. Do not replace it with a zero or a favorable estimate.

---

## 9. What may and may not be changed

### Changes that create a new version

Any change to these creates a new version and requires a new research log entry:

- session times or timezone;
- opening-range length;
- entry window;
- EMA or ATR lengths;
- warm-up length;
- range-gate multiple;
- entry tick distance;
- stop or target multiple;
- trailing logic;
- sizing formula or maximum contracts;
- commission, slippage, or fee assumptions;
- chart type, timeframe, or symbol;
- code logic.

### Safe operational corrections

Fixing a copy/paste error, removing the old MQL5 script from Pine Editor, or setting Bar Magnifier to false to make the free-plan script run is an operational correction. Still document it and restart the affected test if the error could have changed trades.

### Do not optimize all inputs at once

If a formal research variant is allowed, pre-declare a small search space and an objective measured after costs. Prefer a stable plateau of nearby settings to a single best point. Keep the frozen baseline unchanged so the result can be compared with the original specification.

---

## 10. Daily and weekly journal template

Record one row per session, including sessions with no trade.

| Field | What to record |
|---|---|
| Date | New York cash-session date |
| Instrument | ES or MES, kept separate |
| Symbol | For example ES1! or the dated contract |
| Data source | TradingView exchange/vendor feed |
| OR high / low | Frozen 09:30-10:00 range |
| OR width | Price points and width divided by prior ATR |
| Prior ATR | Causal RTH ATR used by the gate |
| Trend | Long, short, or rejected |
| Trigger | Rounded stop-entry price |
| Quantity | Integer contracts or zero |
| Order result | Armed, filled, cancelled, or rejected |
| Entry | Modeled fill price and time |
| Stop / target | Frozen bracket values |
| Exit | Price, time, and exit reason |
| Costs | Commission and slippage assumption |
| Result | Dollars and R multiple |
| Notes | Gaps, warnings, manual action, or data issue |

At the end of each week, save the raw journal and a read-only summary. Do not edit the historical row after a later result is known; append a correction note instead.

---

## 11. Metrics to review after each sealed block

Use the same definitions every time:

- number of eligible sessions;
- number of fills;
- win rate;
- average win and average loss;
- expectancy per trade in dollars and R;
- profit factor, when there are both gains and losses;
- net P&L after modeled costs;
- maximum peak-to-trough drawdown;
- worst day and worst week;
- average holding time;
- percentage of sessions with no trade;
- long and short results separately;
- ES and MES results separately;
- IS versus OOS comparison;
- results by walk-forward fold.

The most important first check is not the headline profit. It is whether the OOS trades were generated by the same rules, symbol conditions, session settings, and cost assumptions as the frozen baseline.

---

## 12. Decision matrix for the current week

| Observation | Action |
|---|---|
| Positive or negative week, but fewer than about 20-30 valid fills | Mark insufficient sample; continue unchanged |
| Runtime error, wrong timeframe, wrong source file, or wrong session | Correct the setup; restart the affected measurement block |
| Good result but settings were changed after observing the week | Label exploratory; do not count as clean OOS |
| Negative result with valid unchanged settings | Keep it in the OOS record; do not optimize reactively |
| Results vary sharply between ES and MES | Keep them separate; investigate contract, costs, and liquidity differences |
| Results depend on one unusually large trade | Continue testing; do not promote on that week alone |
| Repeated OOS deterioration across several folds | Pause promotion and diagnose; do not simply widen the search until something looks good |

These are research controls, not a promise that any outcome will be profitable.

---

## 13. What to send for the next review

To review this week's result without contaminating the next test, provide:

1. The Strategy Tester summary screenshot or export.
2. The List of Trades export or a table of the trades.
3. The symbol, timeframe, date range, and data source.
4. All script input values.
5. Commission and slippage Properties settings.
6. Whether the script was unchanged before and during the week.
7. Any no-trade sessions or runtime warnings.

The result can then be classified as valid forward data, exploratory data, or invalid setup data. It should not be merged with another instrument or another script version.

---

## Immediate next actions

1. Save this week's report and list of trades as **Baseline v1 - Week 1**.
2. Do not change the ORB-30R inputs because of this week's P&L.
3. Run the same ES or MES setup unchanged next week on the five-minute chart.
4. Add one journal row per cash session, including no-trade sessions.
5. After the first four-week block, perform a data and execution audit only.
6. After enough history is collected, begin the pre-declared 12-week IS / 4-week OOS rolling walk-forward.
7. Keep the frozen baseline and every variant in separate folders and separate reports.

**Bottom line:** This week's result is valuable as the first forward observation, but it is not yet a reason to change the model or increase risk. Preserve it, continue unchanged, and let future sealed blocks determine whether the behavior is repeatable.
