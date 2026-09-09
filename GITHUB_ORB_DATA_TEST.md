# Reproducible free-data ORB test

> **Runner status:** The workflow file is prepared locally, but pushing it was blocked by the repository connection's missing GitHub Actions `workflows` permission. No credentials are requested. After GitHub is reconnected with workflow permission, push `.github/workflows/orb-market-test.yml` and run the documented command. Until then, use `scripts/github_orb_test.py` on a machine/network that can reach Yahoo.

This repository can run a one-time GitHub Actions job on the current Arena branch:

```bash
gh workflow run orb-market-test.yml --ref arena/01a07bdd-some-investment-books -f assets=ES,MES -f days=59
gh run watch
```

The workflow fetches native Yahoo chart responses for `ES=F` and `MES=F` separately. It requests 59 recent calendar days at five-minute resolution—the maximum window this adapter allows under Yahoo's documented intraday constraint. It does not pretend to have longer five-minute history. If a provider returns more usable coverage than requested, the report records the actual interval; no raw price rows are kept in the artifact.

`web_app/market_data.py` performs:

- fixed-host HTTPS requests with bounded response size and no credentials;
- native symbol, USD, FUTURE/ETF and native `5m` checks;
- explicit timestamp/OHLC/0.25-point tick checks for futures;
- calendar-aware RTH filtering, gap and unfinished-bar rejection;
- duplicate/conflict and volume warnings without interpolation or made-up volume;
- SHA-256 hashes of raw and normalized inputs.

`web_app/orb_backtest.py` then applies the frozen ORB-30R 0.1a research kernel: 09:30–10:00 ET range, 10:00–13:30 ET entry window, prior-completed-bar EMA20/50, Wilder ATR14 and 250-bar warm-up, prospective one-tick orders, integer units, assumed fees/slippage, one fill per cash session, 1.2 ATR stop, 2 ATR target and 15:50 ET flat. It does not place orders or claim live execution.

The derived report contains 21-, 30- and 59-calendar-day summaries for each asset:

- actual modeled trade count and post-cost hit rate;
- profit factor;
- net P&L and return from a clearly labelled reset equity;
- closing-trade maximum drawdown from that reset;
- realized average win R / average loss R reward-to-risk;
- expectancy R, fees, ambiguous-bar count, coverage and all skip/quality counts.

A short window is not independent if it uses warm-up state from the longer request. The report labels the denominator and limitations. PF, DD, R:R and hit rate remain unknown whenever there are no or too few modeled fills. A successful one-run result is not proof of a durable edge, out-of-sample performance, margin adequacy or prop-firm pass probability.

## Raw-data policy

Raw Yahoo bars are held only in the ephemeral GitHub runner and disappear after the job. The artifact is a derived report. The workflow uses `permissions: contents: read`, requests no secrets and has no broker integration. The local dashboard can import a browser-saved source response separately; those imported raw prices remain under the ignored `data/market/` directory.

Yahoo documents that CME data is delayed and supplied as-is for informational use; do not treat this job as a live feed or redistribute its data. The dashboard’s optional TradingView chart is an external viewer and is not ingested by the test.
