#!/usr/bin/env python3
"""Ephemeral GitHub Actions runner for the Strategy 2 free Yahoo smoke test.

The runner fetches ES=F and MES=F separately for at most 59 recent calendar
days, holds raw responses only in a temporary directory, and uploads a derived
receipt/result.  It never commits or uploads the raw vendor response.  The
result is explicitly vendor-reported and NOT PROJECT-OWNED evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.strategy_2.strategy2_engine import Strategy2Config, Strategy2DataError, load_yahoo_json
from research.strategy_2.strategy2_validation import compare_target_modes, run_walk_forward


SYMBOLS = {"ES": "ES=F", "MES": "MES=F"}


def yahoo_url(symbol: str, days: int, now: datetime) -> str:
    return (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}"
        f"?period1={int((now - timedelta(days=days)).timestamp())}"
        f"&period2={int(now.timestamp())}&interval=5m&includePrePost=true"
    )


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (RangeLab research CI)", "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        raw = response.read(4_000_001)
    if len(raw) > 4_000_000:
        raise Strategy2DataError("Yahoo response exceeded the 4 MB intake limit.")
    return raw


def run_asset(asset: str, days: int, now: datetime, temporary: Path) -> dict:
    symbol = SYMBOLS[asset]
    url = yahoo_url(symbol, days, now)
    raw = fetch(url)
    source_path = temporary / f"{asset}.json"
    source_path.write_bytes(raw)
    acquired_at = datetime.now(timezone.utc).isoformat()
    dataset = load_yahoo_json(source_path, asset, source=url)
    # Keep the acquisition moment and digest visible in the derived report;
    # the raw file is removed with the temporary runner directory.
    receipt = dataset.receipt.to_dict()
    receipt["acquired_at"] = acquired_at
    receipt["source_sha256"] = hashlib.sha256(raw).hexdigest()
    base = Strategy2Config(asset=asset)
    target_variants = compare_target_modes(dataset, base)
    walk_forward = run_walk_forward(dataset, base, train_sessions=12, test_sessions=4)
    return {
        "asset": asset,
        "source_url": url,
        "source_symbol": symbol,
        "requested_calendar_days": days,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "receipt": receipt,
        "target_variants": target_variants,
        "frozen_default_walk_forward": walk_forward,
        "evidence": "VENDOR-REPORTED HISTORICAL PRICES / ASSUMED FILLS / NOT PROJECT-OWNED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", default="ES,MES", help="Comma-separated ES and MES; each is fetched independently.")
    parser.add_argument("--days", type=int, default=59, choices=range(5, 60))
    parser.add_argument("--output", type=Path, default=Path("results/strategy2-github-results.json"))
    args = parser.parse_args()
    assets = [value.strip().upper() for value in args.assets.split(",") if value.strip()]
    if not assets or any(asset not in SYMBOLS for asset in assets) or len(set(assets)) != len(assets):
        parser.error("--assets must contain ES and/or MES exactly once")
    now = datetime.now(timezone.utc)
    report = {
        "schema": "strategy2-github-v1",
        "acquired_at": now.isoformat(),
        "requested_calendar_days": args.days,
        "assets": {},
        "evidence": "VENDOR-REPORTED HISTORICAL PRICES / ASSUMED FILLS / NOT PROJECT-OWNED",
        "raw_retention": "ephemeral temporary files only; raw vendor responses are not uploaded",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="strategy2-yahoo-") as directory:
            temporary = Path(directory)
            for asset in assets:
                report["assets"][asset] = run_asset(asset, args.days, now, temporary)
    except (HTTPError, URLError, OSError, ValueError, KeyError, TypeError, Strategy2DataError) as exc:
        parser.exit(2, f"Strategy 2 GitHub data test failed without a result: {exc}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote derived Strategy 2 report to {args.output}; raw vendor files were not retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
