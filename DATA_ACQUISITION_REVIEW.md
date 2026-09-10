# ES/MES intraday data acquisition review

**Status:** acquisition remains blocked; no new market data or performance result was created.

**Review date:** 10 September 2026 (Africa/Nairobi)

## Decision

Do **not** start the Strategy 2 performance run yet. The repository's prop-firm mean-reversion module also expects intraday ES data, and its current test harness can generate synthetic bars. Running it before an authorized, validated ES/MES artifact exists would produce an unaudited result rather than project evidence.

The next executable research step is therefore a provenance-first data intake, beginning with a public vendor sample and then the smallest authorized long-window package that passes the checks below.

## What was checked

### FirstRateData: current leading candidate

The provider's ES and MES pages advertise:

- native 1-, 5-, 30- and 60-minute bars plus daily data;
- individual contracts and continuous series;
- unadjusted, absolute-adjusted and ratio-adjusted continuous variants;
- comma-separated, zipped files;
- a public sample download;
- ES coverage advertised from 2 January 2008 and MES coverage from 5 May 2019.

The pages list the full datasets as paid products. These claims are provider claims and are not treated as exchange-authenticated project evidence until the actual package is received and checked.

The public sample URLs were attempted from the research workspace:

- ES: <https://frd001.s3.us-east-2.amazonaws.com/frd_sample_futures_ES.zip>
- MES: <https://frd001.s3.us-east-2.amazonaws.com/frd_sample_futures_MES.zip>

Both direct HTTPS downloads failed during TLS establishment with `SSL_ERROR_SYSCALL`. No ZIP bytes were used, retained, published or imported. The browser/page retrieval route could not decode the binary ZIP either. This is a workspace transport limitation, not evidence that the vendor files are unavailable elsewhere.

Source pages:

- <https://firstratedata.com/i/futures/ES>
- <https://firstratedata.com/i/futures/MES>

### Other routes

| Route | Finding | Decision |
| --- | --- | --- |
| Databento / CME GLBX.MDP3 | Documents CME definitions, continuous-contract symbology and authenticated historical retrieval. | Viable authorized alternative; no API key was requested or used. |
| Sierra Chart / broker-linked CME feed | A practical paid or broker-linked path, but not a free long-window artifact available in this workspace. | Keep as an authorized export alternative. |
| Yahoo Finance | Useful only for a short recent vendor snapshot; direct workspace TLS also remains unavailable. | Not a long-window ES/MES source. |
| Alpha Vantage | Its documented intraday route is an authenticated equity endpoint, not a suitable ES/MES futures history. | Reject for this task. |
| Stooq and free daily sources | Do not establish a reproducible long-window native five-minute ES/MES path. | Reject for this task. |

## Intake gates for any candidate package

The ES and MES artifacts must be handled as independent datasets. An ES file is never relabelled as MES, and an adjusted continuous series is not silently mixed with an unadjusted series or individual contracts.

1. **Receipt and provenance**
   - Record the source URL or export description, acquisition time, archive size, file list and SHA-256.
   - Keep the raw package in ignored/private storage only; do not commit or redistribute vendor rows.
   - Record the vendor's timestamp convention, contract/continuous label, adjustment method and license/use boundary.

2. **Schema and parsing**
   - Enumerate all files and headers before importing.
   - Preserve the source contract symbol and continuous-series label.
   - Require native timestamp, open, high, low, close and volume fields; do not reconstruct five-minute bars from daily/hourly data or generate replacement prices.
   - Reject malformed, ambiguous or mixed-instrument files rather than silently dropping their identity.

3. **Time and session treatment**
   - Convert the documented source timezone to an explicit timezone-aware representation and then to America/New_York for the frozen RTH rule.
   - For a complete XNYS cash session, expect 78 five-minute bars from 09:30 through 15:55 ET. A provider's 16:00 boundary row is not an additional price bar.
   - Separate holidays, early closes, missing sessions, overnight bars and incomplete sessions. Never fill a gap.
   - Keep the project's current frozen ORB clock (09:30–10:00 ET range, 10:00–13:30 ET entry window, 15:50 ET liquidation) distinct from the broader CME futures session.

4. **Bar integrity**
   - Check timestamp monotonicity, five-minute alignment, duplicates and conflicting duplicates.
   - Check finite positive OHLC values, `high >= max(open, close)`, `low <= min(open, close)`, nonnegative volume and the ES/MES 0.25-point tick grid.
   - Report zero/missing volume as a warning; do not invent volume.
   - Report per-session observed, expected, missing and invalid bars, with rejected sessions excluded from any later test.

5. **Roll and adjustment audit**
   - For individual contracts, retain the contract code and make roll dates explicit.
   - For continuous data, test each adjustment variant separately and report the vendor's adjustment definition. Do not compare an adjusted continuous series with unadjusted individual-contract results as if they were the same instrument.
   - Inspect roll boundaries for artificial jumps, duplicated intervals and price-grid violations.

6. **Acceptance for project-owned research**
   - ES and MES each need their own accepted artifact and quality report.
   - The quality report must state coverage, complete sessions, rejected sessions, missing bars, duplicates, off-tick values, volume warnings, contract/roll treatment and raw/normalized hashes.
   - Only after acceptance may the frozen strategy kernel be run. Trade count, P&L, hit rate, profit factor, expectancy, reward-to-risk and drawdown remain undefined when the accepted sample does not support them.

## What is intentionally not claimed

- No FirstRateData sample was successfully downloaded in this workspace.
- No long-window ES or MES dataset is present in the repository.
- No Strategy 2 metric, synthetic metric, vendor/variant comparison or live result is project-owned evidence.
- A provider's statement that files are complete and consistent is not a substitute for the repository's independent checks.

## Next handoff

The preferred handoff is one of:

1. a locally downloaded public sample ZIP for **both** ES and MES, used only for schema and structural validation; or
2. an authorized ES/MES five-minute export/package with its source metadata and license boundary.

The raw files should remain in private ignored storage. Once available, the next run will create a derived intake/quality manifest first, preserve ES/MES independence, and only then decide whether the package is sufficient for the frozen ORB and the intraday Strategy 2 workflow.
