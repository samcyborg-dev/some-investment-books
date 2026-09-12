#!/usr/bin/env python3
"""Run the Strategy 2 data receipt or the explicitly unaudited research backtest.

This command never downloads prices and never writes raw market data.  It accepts
one private CSV/Yahoo chart JSON file, emits a derived receipt/result, and keeps
the evidence label explicit.  A historical result from a vendor or user upload
is not project-owned evidence.

Examples
--------
Validate a browser/exported CSV without running the strategy::

    python research/strategy_2/run_strategy2.py receipt \
        --asset ES --input data/market/es.csv --output results/es-receipt.json

Run the causal kernel only as an acknowledged research calculation::

    python research/strategy_2/run_strategy2.py backtest --research-only \
        --asset MES --input data/market/mes.csv --target-mode nearer
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


# Allow both ``python -m research.strategy_2.run_strategy2`` and direct
# execution from the repository root without adding a package marker file.
try:  # pragma: no cover - one branch is selected by the invocation style
    from .strategy2_engine import (
        Strategy2Config,
        Strategy2DataError,
        load_csv,
        load_yahoo_json,
        run_backtest,
    )
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from research.strategy_2.strategy2_engine import (  # type: ignore
        Strategy2Config,
        Strategy2DataError,
        load_csv,
        load_yahoo_json,
        run_backtest,
    )


ASSETS = ("ES", "MES")
FORMATS = ("auto", "csv", "yahoo-json")


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--asset", choices=ASSETS, required=True, help="Contract family; ES and MES are never substituted.")
    parser.add_argument("--input", required=True, type=Path, help="Private CSV or native Yahoo chart JSON path.")
    parser.add_argument("--format", choices=FORMATS, default="auto", dest="input_format", help="Input format; auto uses the .csv suffix only.")
    parser.add_argument("--output", type=Path, help="Derived JSON output path. Raw bars are never copied to this file.")
    parser.add_argument("--pretty", action="store_true", help="Indent the JSON receipt/result.")
    parser.add_argument("--require-clean", action="store_true", help="Exit nonzero unless every accepted session passes the clean receipt gate.")


def _backtest_arguments(parser: argparse.ArgumentParser) -> None:
    _common_arguments(parser)
    parser.add_argument("--research-only", action="store_true", help="Required acknowledgement: output is not project-owned evidence.")
    parser.add_argument("--target-mode", choices=("nearer", "mean", "atr"), default="nearer")
    parser.add_argument("--warmup-rth-bars", type=int, default=250)
    parser.add_argument("--risk-pct", type=float, default=0.50)
    parser.add_argument("--max-contracts", type=int, default=1)
    parser.add_argument("--max-daily-fills", type=int, default=4)
    parser.add_argument("--daily-kill-pct", type=float, default=2.5)
    parser.add_argument("--total-loss-pct", type=float, default=8.0)
    parser.add_argument("--commission-round-trip", type=float, default=5.0)
    parser.add_argument("--slippage-ticks-per-side", type=float, default=1.0)
    parser.add_argument("--initial-equity", type=float, default=100_000.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="command", required=True)
    receipt = subparsers.add_parser("receipt", help="Parse and quality-check a private input without running Strategy 2.")
    _common_arguments(receipt)
    backtest = subparsers.add_parser("backtest", help="Run the causal kernel as an explicitly unaudited research calculation.")
    _backtest_arguments(backtest)
    return parser


def _load_dataset(args: argparse.Namespace):
    if not args.input.is_file():
        raise Strategy2DataError(f"Input file does not exist: {args.input}")
    input_format = args.input_format
    if input_format == "auto":
        input_format = "csv" if args.input.suffix.lower() == ".csv" else "yahoo-json"
    if input_format == "csv":
        return load_csv(args.input, args.asset, source=str(args.input))
    return load_yahoo_json(args.input, args.asset, source=str(args.input))


def _config(args: argparse.Namespace) -> Strategy2Config:
    return Strategy2Config(
        asset=args.asset,
        target_mode=args.target_mode,
        warmup_rth_bars=args.warmup_rth_bars,
        risk_pct=args.risk_pct,
        max_contracts=args.max_contracts,
        max_daily_fills=args.max_daily_fills,
        daily_kill_pct=args.daily_kill_pct,
        total_loss_pct=args.total_loss_pct,
        commission_round_trip=args.commission_round_trip,
        slippage_ticks_per_side=args.slippage_ticks_per_side,
        initial_equity=args.initial_equity,
    )


def _payload(args: argparse.Namespace, dataset, result=None) -> dict:
    payload = {
        "schema": "strategy2-research-v1",
        "command": args.command,
        "input": str(args.input),
        "asset": args.asset,
        "receipt": dataset.receipt.to_dict(),
        "dataset": dataset.to_dict(),
        "evidence": "NOT PROJECT-OWNED: structural receipt only" if result is None else result.evidence,
    }
    if result is not None:
        payload["result"] = result.to_dict()
    return payload


def _write_output(path: Path | None, payload: dict, pretty: bool) -> None:
    text = json.dumps(payload, indent=2 if pretty else None, sort_keys=True, allow_nan=False) + "\n"
    if path is None:
        sys.stdout.write(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)
    print(f"Wrote derived receipt/result to {path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "backtest" and not args.research_only:
        parser.error("backtest requires --research-only; unaudited/vendor output must not be presented as project evidence")
    try:
        dataset = _load_dataset(args)
        if args.require_clean and dataset.receipt.status != "PASS_FOR_KERNEL / NOT_PROJECT_OWNED":
            raise Strategy2DataError(f"Receipt is not clean: {dataset.receipt.status}")
        result = run_backtest(dataset, _config(args)) if args.command == "backtest" else None
        _write_output(args.output, _payload(args, dataset, result), args.pretty)
        return 0
    except (OSError, UnicodeError, Strategy2DataError, ValueError, KeyError, TypeError) as exc:
        print(f"Strategy 2 intake failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
