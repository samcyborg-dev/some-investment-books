# First observed-price research checkpoint — 8 September 2026

## What is available

The original Range Lab dashboard is preserved. **Market data & replay** adds a separate observed-price workspace, source QA, an independent causal OHLC kernel, actual-price candle charts, a gate audit, cost/risk controls, a raw Yahoo JSON / OHLCV CSV import path, and an optional cross-origin TradingView viewer.

**This is not a live execution connection.** The server's direct Yahoo HTTPS requests currently fail during TLS establishment. A research-browser retrieval route did work. Do not describe either a dated snapshot or a widget as data ingested continuously into the strategy.

## Actual acquisition, not a random-price demonstration

Five full Yahoo `ES=F` cash sessions were retrieved with the research browser tool:

- 2026-08-31, 2026-09-01, 2026-09-02, 2026-09-03, 2026-09-04.
- Each source response contained 79 timestamp slots: 78 five-minute RTH bars plus a null 16:00 boundary row.
- The exact selected OHLCV arrays were manually transferred from the complete tool responses. Their explicitly observed, uninterrupted timestamp sequences were losslessly delta-encoded. This transfer method is disclosed; it is not described as a direct HTTP download, an exchange authentication, or an independent replication.
- The vendor supplied the name **E-Mini S&P 500 Sep 26**. Historical contract mapping beyond this snapshot is not established.
- Unused current-quote metadata was deliberately not mixed into the historical candles.

Private inputs live in `data/market/`, excluded from Git to avoid redistributing vendor prices. The source URLs, acquisition method and hashes are inside the private capture and normalized snapshot. No broker account records were obtained.

### Quality result

| Check | Result |
| --- | ---: |
| Source timestamp slots | 395 |
| Accepted RTH OHLC price bars | 390 |
| Complete cash sessions | 5 |
| Outside-session boundary slots | 5 |
| Missing RTH bars | 0 |
| Invalid OHLC / futures off-tick bars | 0 / 0 |
| Conflicting duplicates | 0 |
| Zero-volume bars | 5 |

**The zero volumes are warnings, not silently repaired observations.** All are the first returned RTH bar of each narrow source request and may reflect vendor request-boundary behavior. No volume filter is used in this baseline. Structural QA does not prove price accuracy. Manual transfer remains a provenance limitation until replaced/cross-checked by a reproducible direct download.

Normalized price SHA-256 at this checkpoint:
`30c05af462677e63d772411e2951973007aaa45da67abff026c55a2e517a2be0`

## Frozen research kernel

`web_app/orb_backtest.py`, version **ORB-30R-price-research-0.1a**, is separate from the unrepaired legacy `quant_engine`.

- New York cash-session clock, explicit XNYS holiday/short-session calendar. This is not the futures overnight calendar.
- Native, completed five-minute bars only. No interpolation, backfill or made-up missing sessions.
- Incomplete/conflicting sessions excluded. Indicator history restarts after an incomplete session. This full-session QA selection is ex post and can bias sample inclusion; it is not a deployable live trading filter.
- 09:30–10:00 range; entries from 10:00 to before 13:30; one fill per session.
- Past-only EMA20/50 and Wilder ATR14, with at least 250 completed RTH bars before a signal. A session can become eligible only partway through warm-up completion.
- One-tick stop entry, armed for the coming bar using prior completed information. Already-crossed prices are skipped. Opening gaps are explicitly modeled.
- Frozen armed ATR; initial stop 1.2 ATR rounded out, target 2 ATR rounded in; target must trade through by a tick.
- No trailing stop or news filter. These are distinct later experiments, not secretly added optimizations.
- Integer unit sizing includes fees and a conservative two-way slippage allowance; no forced minimum lot.
- Initial assumed equity $100,000; baseline risk allowance 0.50%; ES round-trip fee $5 per contract and one tick of market-order slippage per side; one-contract cap. These are test assumptions, not a broker tariff or actual account.
- Price P&L uses modeled fills; both fee halves reconcile to the complete trade ledger. Slippage is included through prices, not deducted twice as an extra P&L fee.
- Conservative stop-first sequencing when OHLC cannot order the events. Entry-bar stop ambiguity is disclosed.
- Liquidation at the 15:50 bar **open**, with a conservative resting-target check; never the future close of the 15:50 bar.
- ETFs are initially **long-only, 1× cash buying power** with integer shares. Their results would not be directly comparable to leveraged long/short futures without adjusting the experimental design.
- No futures margin model, firm daily-reset rules, tick-level order queues, licensed real-time feed, live orders, or intrabar compliance claim.

### First executed price-based outcomes

The 250-bar warm-up leaves only **two entry-eligible sessions** (one partly eligible) in the five-session sample.

| Risk allowance | Modeled ES fills | Modeled net P&L | Interpretation |
| --- | ---: | ---: | --- |
| 0.25% | 0 | $0 | No executable integer position under these assumptions |
| **0.50% baseline** | **0** | **$0** | One triggered order required $517.50, above the $500 allowance |
| 0.75% diagnostic | 1 | +$795 | One modeled winner; emphatically not evidence of a reliable edge |

The risk fractions were already used as educational sensitivity levels in the dossier. This is a sizing sensitivity check, **not an optimization** and not a recommendation to increase risk until a trade appears. Default risk remains 0.50%. A no-trade test has no estimated trade win rate, R expectancy or profit factor. One winner cannot estimate a durable win rate. Sharpe is withheld for this short sample. A zero closing drawdown does not prove zero intrabar loss.

## Continue to a larger sample without rebuilding the dashboard

1. Try **Fetch Yahoo · 59 days**. The connector uses one fixed public HTTPS provider endpoint, verified TLS and bounded response size. It does not circumvent logins, paywalls, rate limits or access controls.
2. If the workspace's TLS connection still fails, click **Open source JSON**. This opens Yahoo in the user's browser, which is a different network environment from the server. Save the complete response and import it on the matching asset tab.
3. Alternatively run the standard-library-only collector on a computer with working Yahoo access:

   ```bash
   python3 scripts/fetch_free_bars.py --asset ES --days 59
   python3 scripts/fetch_free_bars.py --asset MES --days 59
   ```

   Import the generated JSON. No credentials or data API key are requested. Provider availability remains conditional.
4. The same QA and kernel then operate on the larger history. Keep the original source and receipt; do not modify prices to pass validation.
5. Compare true MES data separately, then test SPY/QQQ as separately specified research candidates. Do not relabel ES bars as a MES feed.
6. Freeze rules before chronological validation. Obtain longer, contract-aware licensed data before making robust expectancy, drawdown, margin, or evaluation-pass claims.

## Provider notes and canonical sources

- Yahoo exchange coverage and delays: https://help.yahoo.com/kb/finance-for-web/exchanges-data-providers-yahoo-finance-sln2310.html — CME is listed as 10-minute delayed; data is “as is,” informational, and must not be redistributed.
- Public chart format: https://query1.finance.yahoo.com/v8/finance/chart/ES%3DF?range=5d&interval=5m — browser retrieval succeeded; server requests failed TLS in this environment.
- Intraday retention documented by the yfinance project: https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html — five-minute research should remain within the recent 60-day limit. The connector asks for 59 calendar days and reports actual coverage.
- TradingView widgets: https://www.tradingview.com/widget-docs/widgets/charts/advanced-chart/ — optional external viewer, not an API feeding the test. Provider scripts execute on the provider's own origin, not in the main dashboard document.
- FirstRate ES / MES sample pages: https://firstratedata.com/i/futures/ES and https://firstratedata.com/i/futures/MES — free sample links exist; the full history is paid. The advertised sample ZIP also failed direct TLS here and was **not** used as price evidence.

## Tests versus evidence

`web_app/tests/test_market.py` uses expressly constructed fixtures for software checks: missing/invalid bars, calendars, duplicates, volume warnings, asset mismatch, forward-only information, ATR seeding, gap fills, ambiguous bars, fees, integer positions, failed imports and retained snapshots during network failure. Those fixtures are never a historical performance dataset.

A browser-capture shape check is conditional on the private input's presence. Full market-data and out-of-sample validation are still unfinished.
