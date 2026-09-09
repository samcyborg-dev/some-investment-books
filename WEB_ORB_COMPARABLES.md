# Public ORB-30R comparison scan

**Scan date:** 2026-09-09 (Africa/Nairobi)

## Decision

No publicly documented trader, researcher, commercial system, or reproducible backtest found in the indexed web search matched the complete frozen ORB-30R rule set. The public results below are therefore **contextual near matches only**. None is an ES/MES ORB-30R result, and none has been ingested into the project dashboard or used as project evidence.

The search was broad indexed-web research, not a literal guarantee that every private, paywalled, login-only, unindexed, deleted, or non-English page was found. Search snippets were treated as leads; claims were retained only when the linked page supplied enough detail to compare the rule set.

## Frozen rule set used for the exact-match test

A source could be called an exact match only if it documented all material items below, not merely a 30-minute ORB:

- ES and/or MES futures; U.S. cash-session RTH 09:30–16:00 ET.
- The first 30 minutes define the OR high and low.
- Five-minute causal processing; a **prior completed close** must be above EMA20 above EMA50 for a long, or below both in the inverse for a short.
- ATR(14) is frozen when the prospective stop order is armed; the OR width must be no more than 5× ATR.
- One-tick stop entry beyond the OR boundary; only the first trade per session; entry window 10:00 through before 13:30 ET.
- Stop = 1.2× ATR rounded outward; target = 2× ATR rounded inward; target requires one-tick trade-through.
- No VWAP, volume, news, trailing-stop, or discretionary filter; flatten at 15:50 ET.
- Integer contract sizing at 0.5% of equity risk, configured fees, and one-tick slippage.

**Exact-match result: zero.** Every candidate found differed on at least one material rule, and most differed on several.

## Closest public candidates and full rule comparison

`Not documented` means the source did not specify the item in the publicly accessible material reviewed. It does not mean that the author necessarily did not use that rule privately.

### 1. TradingStats — ES/NQ ORB continuation research

**Source:** [Opening Range Breakout Strategy: 6,142 Days of ES & NQ](https://tradingstats.net/orb-breakout-strategy-guide/) and [context-filter research](https://tradingstats.net/orb-strategy-research/)

| Rule | ORB-30R | TradingStats source |
|---|---|---|
| Instrument/sample | ES/MES | ES and NQ futures; Jan 2, 2014–Jan 26, 2026; about 3,030 ES 30-minute sessions |
| RTH | 09:30–16:00 ET | RTH 09:30–16:00 ET |
| Opening range | 30 minutes | 09:30–10:00 ET, plus 5m and 15m configurations |
| Breakout trigger | One-tick stop beyond boundary | Three separate observational definitions: wick breach, 1-minute close, or 5-minute close |
| EMA filter | Prior close EMA20 > EMA50 / inverse | Not documented |
| ATR | Intraday ATR(14), frozen at arming | Daily RTH ATR(14), used to classify OR width into narrow/normal/wide tiers |
| Range gate | OR width ≤ 5× intraday ATR | No matching gate; tier cutoffs are `<0.3×`, `0.3–0.6×`, and `>0.6×` daily ATR |
| Trade window | 10:00–before 13:30 ET | Breaks and extensions measured through noon and close; no matching entry cutoff |
| One trade/session | First trade only | Day-level breakout classification, not a trade order model |
| Stop/target | 1.2× ATR / 2× ATR | No project stop/target; extension probabilities are measured at 0.25×–3× the OR width |
| Sizing | Integer contracts at 0.5% equity risk | Not applicable/documented; no contract sizing model |
| Fees/slippage | Configured fee + one tick | Not included in the reported continuation/extension statistics |
| Flattening | 15:50 ET | Observation horizon includes 16:00 ET; no modeled 15:50 liquidation |
| Metrics/provenance | Project P&L/PF/hit rate | ES 30m wick: 64.6% continuation, 35.4% false-break rate, 47.9% double-break rate; 5m-close continuation 70.7%. These are first-break/closing-direction and excursion statistics, **not** trade win rate, profit factor, expectancy, or P&L. |

**Why it matters:** This is the closest market and range-window benchmark, but it deliberately studies breakout behavior rather than the project’s EMA/ATR order-and-exit system. It must not be presented as the same strategy.

### 2. NinjaTrader Team — generic 30-minute futures ORB guide

**Source:** [30-Minute Opening Range Breakout Strategy](https://ninjatrader.com/futures/blogs/opening-range-breakout-strategy/)

| Rule | ORB-30R | NinjaTrader Team source |
|---|---|---|
| Instrument/sample | ES/MES futures | Generic U.S. equity-index futures example; no backtest sample |
| RTH | 09:30–16:00 ET | Example 09:30–10:00 ET range; full session implied, exact test session not specified |
| Opening range | First 30 minutes | First 30 minutes |
| Breakout trigger | One-tick stop | Full-bar close outside the range |
| EMA filter | EMA20/EMA50 causal alignment | Not documented |
| ATR | ATR14 frozen at arming | Not documented |
| Range gate | ≤5× ATR | Not documented |
| Trade window | 10:00–before 13:30 ET | No cutoff documented |
| One trade/session | First trade only | Describes one clean setup per session/no new signal until the next session |
| Stop/target | 1.2× ATR / 2× ATR | Stop at the opposite range edge; target handled generically through ATM, with no matching fixed 2× ATR rule |
| Sizing | 0.5% equity, integer contracts | General advice to size around stop; no numeric rule |
| Fees/slippage | Configured fees + one tick | Not documented |
| Flattening | 15:50 ET | Not documented; simulator/ATM discussion only |
| Metrics/provenance | No project metric | Educational article; no audited performance result |

### 3. George Pruitt — 30-minute breakout / EasyLanguage research

**Source:** [Day Trading the 30-Minute Breakout, Again](https://georgepruitt.com/day-trading-the-30-minute-breakout-again/)

| Rule | ORB-30R | Pruitt source |
|---|---|---|
| Instrument/sample | ES/MES | `@NQ.D`; July 2018–July 2023 optimization, then a walk-forward/incubation discussion |
| RTH | 09:30–16:00 ET | Uses the U.S. cash open and six 5-minute bars; exact session template/flatten time not fully specified |
| Opening range | First 30 minutes | Six 5-minute bars; orders discussed at 09:55 ET |
| Breakout trigger | One-tick stop | Buy/sell stop one or two ticks beyond the range |
| EMA filter | Prior close EMA20/EMA50 | Not documented |
| ATR | Intraday ATR14 frozen at arming | Uses a volatility comparison `TR < 1.5 × ATR` in the final filter; no matching ATR14 stop model |
| Range gate | ≤5× ATR | No matching 5× OR gate; disaster-stop/risk-budget logic instead |
| Trade window | 10:00–before 13:30 ET | No matching cutoff documented |
| One trade/session | First trade only | One side triggers; the opposite entry is cancelled/converted to a liquidation stop |
| Stop/target | 1.2× ATR / 2× ATR | Dollar stop/objective optimization; final pictured system uses $2,000 risk, $9,000 reward, and $1,500 break-even trigger |
| Sizing | 0.5% equity, integer contracts | Fixed dollar risk in an NQ test; no project sizing rule |
| Fees/slippage | Configured fees + one tick | Explicitly tested without commission and slippage |
| Flattening | 15:50 ET | Zero-overnight-risk intent, but no matching 15:50 rule documented |
| Metrics/provenance | Project PF/hit rate | Walk-forward page reports expected annual return 318% vs actual 434%, expected gain $39,732 vs actual $54,197, and actual worst drawdown $35,005 vs historical $20,355; it labels the incubation result degraded/high risk. These are Pruitt’s NQ model statistics, not ORB-30R statistics. |

### 4. automated-trading.ch — commercial MES Quantower ORB

**Source:** [Opening Range Breakout Strategy](https://automated-trading.ch/quantower/strategies/opening-range-breakout)

| Rule | ORB-30R | Commercial system/source |
|---|---|---|
| Instrument/sample | ES/MES | Example and published backtest use MES, 1-minute execution; 13 Mar 2024–5 Sep 2025 |
| RTH | 09:30–16:00 ET | MES example uses 09:30–09:45 ET; exact full-session template not stated in the result summary |
| Opening range | First 30 minutes | Example is a configurable 15-minute range, not 30 minutes |
| Breakout trigger | One-tick stop | Market-order mode; depending on settings, bar close, FVG, first break/retest/re-break, or other configurable trigger |
| EMA filter | EMA20/EMA50 | Not documented; SuperTrend is offered instead |
| ATR | ATR14 frozen at arming | ATR indicator is a dependency, but the public page does not document the project’s period/freeze/multiplier |
| Range gate | ≤5× ATR | Not documented |
| Trade window | 10:00–before 13:30 ET | Configurable; example says an 11:00 ET cutoff may be used |
| One trade/session | First trade only | Daily stop controls exist; one-trade rule is not the fixed published rule |
| Stop/target | 1.2× ATR / 2× ATR | Configurable stop methods, SuperTrend/trailing options, and ratio targets; example describes 2:1, not the project’s rounded ATR levels |
| Sizing | 0.5% equity, integer contracts | Fixed quantity or dynamic maximum-risk sizing; no 0.5% equity requirement |
| Fees/slippage | Configured fees + one tick | Claims tick-level backtesting, market-order execution, and included commissions; gives an MES fee example of $0.61, but no project one-tick slippage convention |
| Flattening | 15:50 ET | Position-management/stop settings are configurable; no matching flatten rule documented |
| Metrics/provenance | Project PF/hit rate | Vendor-published MES result: $39,559 total profit and -$3,544 max drawdown. The page does not expose a comparable PF/hit rate in text; the result is for a configurable commercial system and was not independently reproduced. |

### 5. Edgeful — ES 5-minute ORB

**Source:** [5-minute opening range breakout on ES](https://www.edgeful.com/blog/posts/5-minute-opening-range-breakout-es-strategy)

| Rule | ORB-30R | Edgeful source |
|---|---|---|
| Instrument/sample | ES/MES | ES, one contract, about six months; 115 trades |
| RTH | 09:30–16:00 ET | 09:30–09:35 ET opening window; complete RTH/flatten schedule not documented |
| Opening range | First 30 minutes | First 5 minutes |
| Breakout trigger | One-tick stop | 5-minute candle close beyond the range |
| EMA filter | EMA20/EMA50 | Not documented |
| ATR | Intraday ATR14 | Not used for the documented stop/target; max-loss cap instead |
| Range gate | ≤5× ATR | 0.55% maximum ORB-size filter |
| Trade window | 10:00–before 13:30 ET | Exact cutoff not stated in the article |
| One trade/session | First trade only | One trade/day in the described algorithm |
| Stop/target | 1.2× ATR / 2× ATR | Stop at opposite edge (100% of range); target at 50% of range |
| Sizing | 0.5% equity, integer contracts | One ES contract; $700 maximum dollar loss; no equity-scaled 0.5% rule |
| Fees/slippage | Configured fees + one tick | Explicitly says results do not include commissions or slippage |
| Flattening | 15:50 ET | Not documented |
| Metrics/provenance | Project PF/hit rate | Author/platform report: 72.17% win rate, 115 trades, $10,825 net profit, 108% return on $10,000, PF 1.623. It also removes Tuesday breakouts and is explicitly described as optimized/near-default. Not independently audited here. |

### 6. TradeThatSwing / Cory Mitchell — NQ 5-minute ORB

**Source:** [Opening Range Breakout Strategy up 400% This Year](https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/)

| Rule | ORB-30R | TradeThatSwing source |
|---|---|---|
| Instrument/sample | ES/MES | NQ, one contract, roughly one year; 114 trades in the author’s test |
| RTH | 09:30–16:00 ET | U.S. futures opening setup; exact full RTH and flatten time not documented in the article |
| Opening range | First 30 minutes | First 15 minutes |
| Breakout trigger | One-tick stop | 5-minute candle close outside the range |
| EMA filter | EMA20/EMA50 | Not documented |
| ATR | Intraday ATR14 | Not documented; dollar loss cap used |
| Range gate | ≤5× ATR | 0.5% in the earlier test, later expanded to 0.8% |
| Trade window | 10:00–before 13:30 ET | Not documented |
| One trade/session | First trade only | One trade/day; long-only version ignores a downside break before an upside break |
| Stop/target | 1.2× ATR / 2× ATR | Stop at opposite OR edge; target at 50% of range; maximum loss cap |
| Sizing | 0.5% equity, integer contracts | One NQ contract; $1,000 maximum loss in the cited test; no fees/slippage |
| Fees/slippage | Configured fees + one tick | Explicitly says commissions and slippage are not included |
| Flattening | 15:50 ET | Not documented |
| Metrics/provenance | Project PF/hit rate | Author reports 74.56% profitable trades, PF 2.512, $2,725 max drawdown, 114 trades; position size was not scaled as account grew. These are NQ, long-only/parameterized variant results. |

### 7. Option Alpha — SPX 0DTE options ORB

**Source:** [Opening Range Breakout: 0DTE Options Trading Strategy Explained](https://optionalpha.com/blog/opening-range-breakout-0dte-options-trading-strategy-explained)

| Rule | ORB-30R | Option Alpha source |
|---|---|---|
| Instrument/sample | ES/MES futures | SPX/0DTE option credit spreads; backtest comparisons for 15/30/60-minute ORBs |
| RTH | 09:30–16:00 ET | U.S. cash open; exact data/session details not fully documented |
| Opening range | First 30 minutes | 30-minute variant exists, but the bot highlighted by the source uses 60 minutes |
| Breakout trigger | One-tick stop | Underlying breaks range high/low; options spread opened at the opposite range boundary |
| EMA filter | EMA20/EMA50 | Not documented |
| ATR | Intraday ATR14 | Not documented |
| Range gate | ≤5× ATR | Minimum OR width 0.2% of underlying open |
| Trade window | 10:00–before 13:30 ET | No entry after 12:00 ET |
| One trade/session | First trade only | Combined strategy opens one position per day |
| Stop/target | 1.2× ATR / 2× ATR | Credit-spread wing widths ($5/$10/$15 tested); hold to end of day, no matching ATR exits |
| Sizing | 0.5% equity, integer contracts | Options position sizing not stated in the article |
| Fees/slippage | Configured fees + one tick | Not documented |
| Flattening | 15:50 ET | Hold until end of day |
| Metrics/provenance | Project PF/hit rate | 30-minute combined result: $19,555 total P/L, -$8,306 max drawdown, 82.6% win rate, $31 average/trade, PF 1.19. The mechanics and payoff are options-specific, so this cannot be an ES/MES comparison. |

### 8. QuantConnect — stocks-in-play ORB research

**Source:** [Opening Range Breakout for Stocks in Play](https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/)

| Rule | ORB-30R | QuantConnect source |
|---|---|---|
| Instrument/sample | ES/MES futures | Liquid U.S. equities; 2016 backtest; 20 stocks selected from a 1,000-stock universe by abnormal first-5-minute volume |
| RTH | 09:30–16:00 ET | U.S. equity intraday data; close exit, exact session template not the project’s futures RTH rule |
| Opening range | First 30 minutes | First 5 minutes; scan at 09:35 |
| Breakout trigger | One-tick stop | Stop-market at the opening bar high/low after the opening bar direction |
| EMA filter | EMA20/EMA50 | Not documented |
| ATR | Intraday ATR14 | 14-day ATR; used to determine stop distance and stock-universe threshold; project multiplier not documented |
| Range gate | ≤5× ATR | No matching OR-width gate |
| Trade window | 10:00–before 13:30 ET | Entry at 09:35; exits at close or stop |
| One trade/session | First trade only | Multiple stocks/positions allowed, subject to max positions/equal-weight limits |
| Stop/target | 1.2× ATR / 2× ATR | ATR stop; winning positions exit at close, no project fixed 2× ATR target |
| Sizing | 0.5% equity, integer contracts | 1% of allocated portfolio value at stop, capped by equal-weight position size |
| Fees/slippage | Configured fees + one tick | Not documented in the research page |
| Flattening | 15:50 ET | Close exit |
| Metrics/provenance | Project PF/hit rate | 2016 Sharpe 2.396 versus SPY 0.836 and beta -0.042; stock-universe research, not ES/MES ORB-30R. |

### 9. FMZQuant / Medium — EMA20/50 + ATR ORB architecture

**Source:** [Opening Range Breakout Strategy with Volume Confirmation and Exponential Moving Averages](https://medium.com/@FMZQuant/opening-range-breakout-strategy-with-volume-confirmation-and-exponential-moving-averages-9352aa581357)

| Rule | ORB-30R | FMZQuant source |
|---|---|---|
| Instrument/sample | ES/MES futures | Binance DOGE/USDT futures example; source code block covers 5–11 May 2025 on 3-minute bars |
| RTH | 09:30–16:00 ET | Uses a New York 09:30 opening anchor, but crypto trades 24/7 and no RTH flatten is documented |
| Opening range | First 30 minutes | Default 15 minutes, adjustable |
| Breakout trigger | One-tick stop | Price condition/strategy entry after a breakout; source code does not document the project’s one-tick stop-order semantics |
| EMA filter | Prior completed close EMA20 > EMA50 / inverse | EMA20 and EMA50 directional filter, but code evaluates current close and does not document the project’s causal arming rule |
| ATR | Frozen intraday ATR14 | ATR length 5; ATR multiplier 1.5 for both stop and target; not project settings |
| Range gate | ≤5× ATR | No matching gate |
| Trade window | 10:00–before 13:30 ET | No matching cutoff |
| One trade/session | First trade only | No fixed one-trade rule documented in the source code |
| Stop/target | 1.2× ATR / 2× ATR | Equal 1.5× ATR stop and target; source recommends asymmetric variants as future work |
| Sizing | 0.5% equity, integer contracts | Pine strategy uses 10% of equity; not ES/MES contract sizing |
| Fees/slippage | Configured fees + one tick | Not documented |
| Flattening | 15:50 ET | Not documented |
| Metrics/provenance | Project PF/hit rate | No meaningful performance result published for the rule set; the code block is a one-week Binance example. This is a useful component-level near match, not evidence for ES/MES. |

## Other public material checked but not promoted to comparables

- **Toby Crabel’s original ORB framework** is the historical ancestor of many ORB systems, but it is based on stretch/offset and contraction patterns such as NR4/NR7, not this exact EMA20/50 + ATR14 + 1.2/2.0 ATR ES/MES rule set. Public summaries do not provide the frozen project execution model.
- Generic guides and indicators from CrossTrade, Sahi, ForexTester, TradeAlgo, Build Alpha, TradingView, and similar vendors expose configurable combinations of OR windows, EMA/VWAP/volume filters, ATR stops, targets, and one-trade/session controls. They do not document the full ORB-30R values together with an independently auditable result, so their claims were not promoted to exact or comparable evidence.
- A search result for a NinjaTrader Community paid MES ORB/ATR listing could not be verified: the linked forum page now returns “Page Not Found”/private. It is excluded rather than treated as a documented system.
- Reddit, forum, and indicator pages were used only as discovery leads unless they supplied reproducible rules and provenance. Anecdotal success claims such as “100% last week” are not treated as strategy metrics.

## Metric handling

The sources use incompatible definitions:

- **Continuation rate** is not trade hit rate. TradingStats defines it as whether the first breakout direction agrees with the session’s closing direction; it does not model the project stop, target, sizing, costs, or intrabar order sequence.
- **Win rate/profitable trades** may be author-reported and may be optimized, long-only, one-contract, or cost-free. They are not transferable to ES/MES ORB-30R.
- **Profit factor, P&L, return, and drawdown** are retained with the source’s instrument, sample, sizing, and cost assumptions. Missing fees, slippage, contract rolls, data provenance, or independent reproduction are not silently filled in.
- A source that omits a field is recorded as **Not documented**, not assumed to match the project.

## Bottom line before project-owned data

There is no defensible public “same-style trader metric” to use as a direct prior for ORB-30R. The strongest contextual benchmark is the ES 30-minute TradingStats continuation study, and the closest mechanical MES example is the commercial Quantower page, but both materially differ from the frozen rule set. The project’s ES and MES results must therefore come from an independent, provenance-first long-window data run, kept separate by contract and not mixed with these public variants.
