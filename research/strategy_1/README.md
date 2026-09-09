# Strategy 1 — Opening Range Breakout research dossier

**Main deliverable:** [`STRATEGY_1_ORB_FORENSIC_RESEARCH.pdf`](../../STRATEGY_1_ORB_FORENSIC_RESEARCH.pdf) — 49 pages, 8 original figures, 15 sources, clickable citations and PDF bookmarks. Prepared 8 September 2026.

This is original critical research and an execution specification, **not a verified ES/MES backtest or a Pine Script implementation**. Earlier synthetic pass-rate, walk-forward, certification and optimal-live claims are corrected in the report and in `TRADING_JOURNAL.md`.

## Read first

The PDF distinguishes **REPORTED**, **DERIVED**, **ILLUSTRATIVE**, **PROPOSED** and **UNKNOWN** information. Published results belong to their own instruments, rules, samples and cost assumptions. The educational challenge simulation is deliberately uncalibrated; its percentages are not estimates of actual evaluation success. Verified local drawdown dates and live performance remain unknown.

`report.md` is the original manuscript. `sources.json` contains source URLs, SSRN IDs, versions, access depth, reported figures and transfer limitations. No author papers or licensed market data are redistributed. Some long-PDF retrievals were limited to the first 30 pages; reviewed scopes are disclosed individually.

## Reproduce

Python 3.11 was used. Required package versions are in `requirements.txt` and `build_metadata.json`.

```bash
# Optional, inside your own Python environment:
python3 -m pip install -r research/strategy_1/requirements.txt

python3 research/strategy_1/calculate_examples.py
python3 research/strategy_1/build_pdf.py
python3 -m unittest discover -s research/strategy_1 -p 'test_research.py' -v
```

Run these commands from the repository root. The scripts themselves resolve their files relative to their own location, not the process working directory. The build uses Matplotlib-bundled DejaVu fonts; no font download, network request, broker connection or server is needed.

- `calculate_examples.py`: seeded educational scenario model, exact JSON/CSV results, arithmetic and eight original figures.
- `illustrative_results.json`: assumptions, integer outcome counts, conditional intervals and derived results.
- `illustrative_pass_grid.csv` / `illustrative_stress.csv`: the full scenario output, not just a selected winner.
- `build_pdf.py`: measured, fixed-content-page typesetter with bookmarks and clickable source links; fails on overflow.
- `build_metadata.json`: package versions, layout measurements and hashes of the delivered PDF and research inputs.
- `test_research.py`: arithmetic, accounting identities, reproducibility, untouched audited engine, source links, fonts' layout boundaries, image presence and PDF checks. These are **research-artifact checks, not engine validation**.

`audited_code_hashes.json` identifies the local prototype snapshot discussed in the report. The calculation script refreshes these hashes, so archive the delivered record before rerunning against a changed engine. The dossier's code audit is date-specific; a different implementation needs a fresh audit.

## Quality review

The PDF page count and text extraction were checked with PyMuPDF, alongside internal/external links and page-safe text bounds. Page content is measured before drawing; body type remains at least 9.2 pt. Visual renders were inspected for figure placement and dense-table readability. Scratch renders and caches are ignored rather than included as deliverables.

**Next phase:** review the causal ORB-30R specification, then implement and validate Pine separately. No strategy/engine repairs or Pine implementation were made for this PDF task.
