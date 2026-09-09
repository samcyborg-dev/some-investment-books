# Range Lab — ORB research dashboard

An ORB-only, evidence-aware dashboard. FastAPI serves the UI, local font/icons, APIs, research reader and downloads from **one origin**. No frontend build, external chart CDN, live feed, broker credentials or market-data connection is required.

## Start

From the repository root, in your Python environment:

```bash
python3 -m pip install -r web_app/requirements.txt
python3 -m uvicorn web_app.app:app --host 0.0.0.0 --port 8000
```

Open the port 8000 preview. The app accepts the preview host and permits iframe embedding. Browser requests use relative `/api/orb/*` URLs, never localhost URLs to another service. The exact working branch is unchanged.

## Workspace

- **Overview:** model expectancy, target/breach/unresolved counts, percentile equity and drawdown bands, assumptions, validation status and selected published results.
- **Scenario lab:** actual seeded recalculation of 20,000 hypothetical accounts; editable assumed win probability, risk, costs, activity, stop/target geometry, horizon and floor. Saved 12-cell sensitivity grid and seven stress presets reproduce the dossier. Edited inputs are explicitly marked until applied; old results are not silently relabeled.
- **Research & evidence:** seven reported implementations, correct author return labels, timeframe comparisons, all 15 sources with access scope/limitations, and the unresolved local execution audit.
- **Trade analytics:** CSV import, integer/tick/fee/timestamp validation, net P&L, win rate, profit factor, R expectancy, closing-trade equity and right-censored drawdown episodes. Includes an explicitly fictional sample, filtering and CSV export.
- **Rulebook:** frozen ORB-30R proposal, New York/Nairobi date-aware session conversion and integer ES/MES position-sizing calculator.
- **Journal:** saved research notes, search, delete and JSON export. Checklist preferences are stored in the browser. Notes are not verified broker records.
- **Resources:** searchable metric glossary and complete 49-section in-app dossier reader. PDF, manuscript, source registry and research CSV downloads are same-origin. Result summaries also support copying if downloads are unavailable in a client.

## Evidence boundaries

The default results are an **uncalibrated educational model**, not historical ES/MES performance. Published results retain their own instrument, dates, entry/exit rules, exposure and author labels. Imported records are **USER-SUPPLIED**, not independently verified. No Sharpe, intrabar drawdown or firm pass probability is manufactured from a sparse trade file. Actual local strategy performance remains unknown.

The simulation models one or zero closed-trade outcomes per session. It stops at a target/floor and holds terminated paths flat for plotting. Bands are **pointwise** quantiles, not a simultaneous confidence band or a representative actual account trajectory. Costs and rare losses are included in expected payoff arithmetic. It does not generate ORB signals, real contract fills, daily floating-loss checks or a funded-account lifetime.

The existing trading engine and Pine specification were not changed. `legacy_app.py` and `templates/index.html` preserve the superseded multi-strategy demo for traceability; the new application neither imports nor calls that engine. The old `/api/backtest` route returns HTTP 410 with an explanation rather than resurfacing invalid synthetic performance claims.

## Trade CSV format

Required columns:

```csv
entry_time,exit_time,symbol,side,quantity,entry_price,exit_price,fees,initial_risk_usd
```

- ISO-8601 timestamps **with UTC offsets**, exit after entry.
- ES/MES (optionally a contract month suffix), LONG/SHORT, integer quantity.
- Actual fill prices on the 0.25-point grid. Off-tick weighted-average fills are not supported by this version; do not round them to force an import.
- `fees` contains all round-trip fees for that trade; fill-price slippage is not charged again.
- `initial_risk_usd` is the fixed total initial price-risk denominator, not the moved trailing risk.
- Up to 1 MB / 5,000 records. Overlapping positions, duplicates and invalid rows reject the import rather than silently changing the sample.
- Supply starting equity explicitly. Reconstruction assumes no external cash flows and samples only at trade closes.

Trade imports are held in memory and **not saved**. Research notes persist separately in `research/strategy_1/dashboard_journal.json` using atomic writes. Do not enter credentials or sensitive account identifiers. Corrupt journal records are rejected without overwriting existing notes. The dashboard is a single-workspace research tool, not an authenticated multi-tenant production service.

## Checks

```bash
python3 -m pip install -r web_app/requirements-dev.txt
python3 -m pytest web_app/tests/test_orb.py -q

# With the server running:
python3 -m playwright install chromium
python3 web_app/tests/browser_smoke.py
```

`ORB_BASE_URL` overrides the smoke-test URL; `ORB_BROWSER_PATH` selects an already-installed Chromium. The test covers all routes, real control recalculation, drafts versus completed results, downloads, source/metric dialogs, report images, ledger validation, sizing, DST, journal persistence/escaped user text, and mobile overflow. Scratch screenshots and downloaded test exports live in `.cache/orb-dashboard/` and are ignored.

Automated axe WCAG 2 A/AA and 2.1 AA checks were run on the six default routes. These are automated checks, not a complete accessibility certification.

To rebuild the dossier and its original figures, use the existing `research/strategy_1/requirements.txt`, `calculate_examples.py` and `build_pdf.py`. The original 18 research checks are separate from dashboard tests. Archive the code-audit hashes before rebuilding against a changed trading engine.

## Dependencies and assets

The Inter variable font is bundled locally with its SIL Open Font License in `static/fonts/OFL.txt`. UI icons and charts are local SVG. The only outbound navigation consists of source links deliberately opened by the reader. No tracking, analytics or trading services are connected.
