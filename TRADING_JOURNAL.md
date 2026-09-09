# Strategy 1 — Research Status & Journal Correction

**Updated 8 September 2026 | Status: RESEARCH ONLY — NOT LIVE-VALIDATED**

The account balances, historical trades, checked checklists, confidence grades and performance claims in the **legacy demonstration below are illustrative, not verified account records**. No broker statement or live execution connection has been supplied. They must not be used to size trades or assess actual challenge progress. The prior claim that fractional Kelly guarantees minimal recovery time is incorrect; no such guarantee exists. The legacy figures are retained for traceability, not endorsed.

| Verified item | Current state |
| --- | --- |
| Selected strategy | Strategy 1: Opening Range / Intraday Volatility Breakout |
| Actual broker / firm / evaluation terms | Not supplied; limits in legacy demo are assumptions |
| Actual capital, equity, drawdown and trade count | Unknown — awaiting verified records |
| Local performance evidence | Synthetic prototype only; execution and accounting defects identified |
| Prior 100% challenge pass / 72.7% win-rate claims | Withdrawn as live-performance expectations |
| PDF deliverable | Completed: 49-page forensic research report, `STRATEGY_1_ORB_FORENSIC_RESEARCH.pdf` |
| ORB dashboard | Running research workspace: scenario lab, paper results, CSV analytics, rulebook and journal; no live connection |
| Pine Script | Not started; specification and validation gates come first |
| Live deployment approval | Not granted by this research |

## Research activity log

- **2026-09-08:** Read direct ORB papers SSRN 4729284 and 4416622, the accessible main text of related SPY momentum paper 4824172, statistical validation research and contrary evidence. Sources and access limits are recorded in `research/strategy_1/sources.json`.
- **2026-09-08:** Audited the local ORB engine without changing strategy code. Found same-bar future-information entry, target-first intrabar ambiguity, fractional futures, incomplete per-trade fee reconciliation, pre-entry-only kill-switch checks, and invalid walk-forward/Monte Carlo labeling.
- **2026-09-08:** Built clearly labeled educational calculations and stress scenarios; these are not market-calibrated estimates or new ORB backtests.

- **2026-09-08:** Completed the 49-page downloadable ORB forensic PDF, including eight original figures, 15 sources with access limits, worked trades, drawdown analysis, metric dictionaries and a Pine handoff specification only. Checked arithmetic, scenario totals, code-audit hashes, PDF pagination, links and layout; actual ES/MES performance remains unknown.

- **2026-09-08:** Built the ORB-only Range Lab dashboard. Its 20,000-path model reproduces the dossier, separates published and user-supplied results, rejects invalid trade CSVs, and provides pointwise equity/DD charts, sizing, DST conversion and an in-app report reader. The legacy backtest API is retired; trading-engine files remain unchanged. Dashboard notes are stored separately in `research/strategy_1/dashboard_journal.json`.
- **2026-09-08:** Verified 52 dashboard calculation/API tests, 18 dossier checks, desktop/mobile browser flows and automated accessibility checks on all six default views. These are software/research-artifact checks, not market validation. No actual trades were executed or added to this journal.

## Before any future trade — all checks remain unverified

- [ ] Confirm exact instrument, integer lot size, tick value and contract month.
- [ ] Record actual equity and the firm's current equity floors, reset timezone and permitted activities.
- [ ] Verify news, holiday schedule, correct New York session and reliable data.
- [ ] Ensure planned loss plus fees, slippage and reserve fits remaining loss allowance.
- [ ] Confirm broker-held protective orders, emergency flattening and order reconciliation.
- [ ] Confirm real-data validation and paper-execution acceptance tests have passed.

---

## Legacy demonstration — not a live journal

# QuantAlpha Institutional Trading Journal & Execution Log
## Systematic Trade Review, Prop Firm Compliance & Psychological Audit

---

### Daily Account Status & Risk Monitor

| Parameter | Prop Firm Account (Evaluation Phase 1) | Personal Fund Account |
| :--- | :--- | :--- |
| **Account Capital** | **$\$100,000.00$** | **$\$50,000.00$** |
| **High-Water Mark (Peak Equity)** | **$\$104,270.00$** | **$\$92,435.00$** |
| **Current Equity** | **$\$104,270.00$** | **$\$92,435.00$** |
| **Max Allowed Daily Drawdown** | **$4.00\%$ ($\$4,000.00$)** | N/A (12% Target Volatility) |
| **System Proactive Kill-Switch** | **$2.50\%$ ($\$2,500.00$)** *(Halt trading for day)* | 200-SMA Macro Trend Cash Gate |
| **Max Total Drawdown Limit** | **$8.00\%$ ($\$8,000.00$)** | 25% Cyclical Circuit Breaker |
| **Profit Target** | **$+8.00\%$ ($\$8,000.00$)** | Long-Term CAGR Compounding |
| **Current Progress to Target** | **$+4.27\%$ ($\$4,270.00$)** *(53.4% Reached)* | **$+84.87\%$ Net Total Return** |
| **Challenge Status** | <font color="#059669">**ON TRACK (INSTITUTIONAL A+)**</font> | <font color="#059669">**COMPOUNDING ALPHA**</font> |

---

### Pre-Execution Risk Verification Checklist (Daily Pre-Market Protocol)

Before placing any trade in the market, verify the following 6 checkpoints:

```
[X] 1. Economic News Audit: Verify no high-impact FOMC, CPI, NFP, or PPI releases scheduled within 15 minutes.
[X] 2. Account Daily Drawdown Check: Ensure current day loss is $0.00 (Kill-switch is inactive).
[X] 3. Regime Identification: Verify ADX(14) and 50/200 EMA to determine Trending vs. Ranging market state.
[X] 4. Position Sizing Precision: Risk strictly pegged to 0.50% ($500 per trade).
        Formula: Units = ($500) / (Stop Distance in Points * Contract Multiplier).
[X] 5. Hard Stop-Loss & Take-Profit: Both orders queued simultaneously upon entry. No mental stops.
[X] 6. End-of-Day Liquidation: Flat alarm set for 15:50 EST. Zero overnight gap exposure.
```

---

### Realized Trade Execution Log & $R$-Multiple Audit

| Trade # | Date / Time | Symbol | Side | Setup / Strategy | Entry ($) | Exit ($) | Net PnL ($) | $R$-Multiple | Exit Reason | Discipline Score |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **#038** | 2026-06-01 14:15 | `ES_FUT` | **LONG** | ORB Volatility Breakout | 2,842.25 | 2,854.75 | **+$625.00** | **+1.25R** | TAKE_PROFIT | 10 / 10 |
| **#037** | 2026-05-29 11:30 | `ES_FUT` | **SHORT**| Z-Score Stat Reversion | 2,835.50 | 2,831.00 | **+$225.00** | **+0.45R** | MEAN_REVERSION | 10 / 10 |
| **#036** | 2026-05-28 10:45 | `ES_FUT` | **LONG** | ORB Volatility Breakout | 2,820.75 | 2,815.75 | **-$250.00** | **-0.50R** | STOP_LOSS | 10 / 10 |
| **#035** | 2026-05-27 13:00 | `ES_FUT` | **SHORT**| ORB Volatility Breakout | 2,810.00 | 2,797.50 | **+$625.00** | **+1.25R** | TAKE_PROFIT | 10 / 10 |
| **#034** | 2026-05-26 11:15 | `ES_FUT` | **LONG** | Z-Score Stat Reversion | 2,795.25 | 2,798.50 | **+$162.50** | **+0.32R** | MEAN_REVERSION | 10 / 10 |
| **#033** | 2026-05-22 10:35 | `ES_FUT` | **SHORT**| ORB Volatility Breakout | 2,788.00 | 2,773.00 | **+$750.00** | **+1.50R** | TAKE_PROFIT | 10 / 10 |
| **#032** | 2026-05-21 14:40 | `ES_FUT` | **LONG** | ORB Volatility Breakout | 2,775.50 | 2,770.50 | **-$250.00** | **-0.50R** | STOP_LOSS | 10 / 10 |
| **#031** | 2026-05-20 11:05 | `ES_FUT` | **SHORT**| Z-Score Stat Reversion | 2,764.00 | 2,760.00 | **+$200.00** | **+0.40R** | MEAN_REVERSION | 10 / 10 |
| **#030** | 2026-05-19 10:15 | `ES_FUT` | **LONG** | ORB Volatility Breakout | 2,752.00 | 2,767.00 | **+$750.00** | **+1.50R** | TAKE_PROFIT | 10 / 10 |
| **#029** | 2026-05-18 12:20 | `ES_FUT` | **LONG** | Z-Score Stat Reversion | 2,740.00 | 2,735.00 | **-$250.00** | **-0.50R** | STOP_LOSS | 10 / 10 |

---

### Performance Distribution & Expectancy Metrics

```
+---------------------------------------------------------------------------------------------------+
|                                 EXPECTANCY & SYSTEM QUALITY AUDIT                                 |
+---------------------------------------------------------------------------------------------------+
| Total Logged Trades       : 38 trades                                                            |
| Winning Trades            : 24 trades (63.2% Win Rate)                                            |
| Losing Trades             : 14 trades (36.8% Loss Rate)                                           |
| Gross Profit              : +$6,770.00                                                            |
| Gross Loss                : -$2,500.00                                                            |
| Net Realized Profit       : +$4,270.00                                                            |
| Profit Factor (PF)        : 1.42                                                                  |
| Average Win Size          : +$282.08 (+0.56R)                                                     |
| Average Loss Size         : -$178.57 (-0.36R)                                                     |
| Win / Loss Ratio          : 1.58                                                                  |
| Mathematical Expectancy   : +0.48R per trade                                                      |
| System Quality Number     : 3.12 (Institutional Quality / Van Tharp Scale)                        |
| Max Consecutive Losses    : 2 trades (-1.00R cumulative / Well within 2.5% kill-switch)           |
+---------------------------------------------------------------------------------------------------+
```

---

### Monthly 6% Rule & Loss Recovery Protocols (Dr. Alexander Elder)

1. **The 2.5% Daily Soft Halt**:
   - If intraday loss hits $-\$2,500.00$ ($2.5\%$), the automated risk engine locks out order execution for the remainder of the trading day.
   - *Psychological Objective*: Prevents revenge trading and prevents ever approaching the firm's $4.0\%$ hard failure line.
2. **The 6.0% Calendar Month Stop**:
   - If cumulative drawdown in a single month reaches $-\$6,000.00$ ($6.0\%$), live trading is halted for the rest of the calendar month.
   - *Recovery Process*: Switch to paper-trading simulation for 5 consecutive trading days. Analyze trade logs for regime mismatch (e.g., trading mean-reversion in an explosive trend regime).
3. **Kelly Sizing Safety**:
   - Position sizes are capped at **$0.35\text{ Fractional Kelly}$**, mathematically guaranteeing that drawdown recovery time is minimized.

---

### Post-Trade Qualitative Review & Psychological Debrief

- **Trade #038 Review**: Clean Opening Range Breakout above 2,842.25 after a 25-minute volatility compression. Trend was aligned with 20/50 EMA on the 5-minute chart. Stop-loss was trailed automatically at $+1.8\times\text{ATR}$. Executed mechanically with zero emotional hesitation.
- **Discipline Rating**: $100\%$ rule compliance across all parameters. Zero manual intervention.

---
*QuantAlpha System Trading Journal — Active & Synchronized with Engine on port 8000.*
