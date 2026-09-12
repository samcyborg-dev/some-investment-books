"""Research-only robustness and chronological evaluation helpers.

These helpers orchestrate the causal kernel; they do not create evidence from
synthetic fixtures or choose a winning parameter after seeing an OOS result.
Every caller must retain the input quality receipt and the returned reports are
labelled not project-owned until an independent data/provenance gate approves
them.
"""
from __future__ import annotations

from dataclasses import asdict, fields, replace
from datetime import date
from itertools import product
from typing import Any, Iterable, Mapping, Sequence

from .strategy2_engine import BacktestResult, Strategy2Config, Strategy2DataError, ValidatedDataset, run_backtest


EVIDENCE_LABEL = "NOT PROJECT-OWNED: research orchestration only"


def _config_dict(config: Strategy2Config) -> dict[str, Any]:
    return {key: (value.isoformat() if hasattr(value, "isoformat") else value) for key, value in asdict(config).items()}


def _result_summary(result: BacktestResult) -> dict[str, Any]:
    return {
        "config": _config_dict(result.config),
        "receipt_status": result.receipt.status,
        "project_owned": result.receipt.project_owned,
        "trade_count": result.metrics["trade_count"],
        "metrics": result.metrics,
        "diagnostics": result.diagnostics,
        "evidence": EVIDENCE_LABEL,
    }


def compare_target_modes(dataset: ValidatedDataset, config: Strategy2Config | None = None) -> dict[str, Any]:
    """Run all declared target modes on the same accepted bars.

    This is a comparison surface, not automatic model selection.  The output
    intentionally includes every variant and never promotes one mode to the
    baseline.
    """
    base = config or Strategy2Config(asset=dataset.asset)
    if base.asset != dataset.asset:
        raise Strategy2DataError("Dataset and configuration asset differ.")
    variants = {}
    for mode in ("nearer", "mean", "atr"):
        result = run_backtest(dataset, replace(base, target_mode=mode))
        variants[mode] = _result_summary(result)
    return {
        "schema": "strategy2-target-comparison-v1",
        "asset": dataset.asset,
        "receipt": dataset.receipt.to_dict(),
        "variants": variants,
        "selection": None,
        "evidence": EVIDENCE_LABEL,
    }


def parameter_grid(
    dataset: ValidatedDataset,
    config: Strategy2Config,
    grid: Mapping[str, Sequence[Any]],
    trade_dates: Iterable[date] | None = None,
) -> dict[str, Any]:
    """Evaluate a predeclared grid without ranking or selecting a winner.

    The grid is meant for an in-sample robustness plateau.  Pass an explicit
    ``trade_dates`` set for a fold; the engine still advances indicators over
    all earlier accepted sessions, so a later OOS evaluation remains causal.
    """
    if config.asset != dataset.asset:
        raise Strategy2DataError("Dataset and configuration asset differ.")
    allowed = {field.name for field in fields(Strategy2Config)} - {"asset"}
    unknown = sorted(set(grid) - allowed)
    if unknown:
        raise Strategy2DataError("Unknown Strategy2Config grid fields: " + ", ".join(unknown))
    keys = list(grid)
    values = [tuple(grid[key]) for key in keys]
    if any(not options for options in values):
        raise Strategy2DataError("Parameter grid options cannot be empty.")
    results = []
    for combination in product(*values):
        overrides = dict(zip(keys, combination))
        variant = replace(config, **overrides)
        result = run_backtest(dataset, variant, set(trade_dates) if trade_dates is not None else None)
        results.append({"overrides": overrides, **_result_summary(result)})
    return {
        "schema": "strategy2-parameter-grid-v1",
        "asset": dataset.asset,
        "receipt": dataset.receipt.to_dict(),
        "grid": {key: list(value) for key, value in grid.items()},
        "results": results,
        "selection": None,
        "evidence": EVIDENCE_LABEL,
    }


def walk_forward_folds(
    dataset: ValidatedDataset,
    train_sessions: int = 12,
    test_sessions: int = 4,
    step_sessions: int | None = None,
) -> list[dict[str, Any]]:
    """Return disjoint chronological IS/OOS session folds.

    The helper uses complete, tradeable session dates only.  If the available
    history cannot support a fold it returns an empty list rather than inventing
    a low-power performance denominator.
    """
    if train_sessions < 1 or test_sessions < 1:
        raise Strategy2DataError("Walk-forward train and test lengths must be positive.")
    step = test_sessions if step_sessions is None else step_sessions
    if step < 1:
        raise Strategy2DataError("Walk-forward step must be positive.")
    dates = sorted(dataset.tradeable_dates)
    folds: list[dict[str, Any]] = []
    start = 0
    index = 1
    while start + train_sessions + test_sessions <= len(dates):
        train = tuple(dates[start : start + train_sessions])
        test = tuple(dates[start + train_sessions : start + train_sessions + test_sessions])
        folds.append(
            {
                "fold": index,
                "train_dates": [value.isoformat() for value in train],
                "test_dates": [value.isoformat() for value in test],
                "train_end_before_test_start": train[-1] < test[0],
            }
        )
        start += step
        index += 1
    return folds


def run_walk_forward(
    dataset: ValidatedDataset,
    config: Strategy2Config | None = None,
    train_sessions: int = 12,
    test_sessions: int = 4,
    step_sessions: int | None = None,
) -> dict[str, Any]:
    """Run a frozen-config chronological OOS benchmark.

    No parameter is selected inside this function.  The train dates are
    recorded for audit and only test dates are permitted to generate signals;
    all earlier bars remain available solely to warm causal indicator state.
    """
    base = config or Strategy2Config(asset=dataset.asset)
    folds = walk_forward_folds(dataset, train_sessions, test_sessions, step_sessions)
    reports = []
    dates = sorted(dataset.tradeable_dates)
    for fold in folds:
        test_dates = {date.fromisoformat(value) for value in fold["test_dates"]}
        result = run_backtest(dataset, base, trade_dates=test_dates)
        reports.append({**fold, "result": _result_summary(result)})
    return {
        "schema": "strategy2-walk-forward-v1",
        "asset": dataset.asset,
        "receipt": dataset.receipt.to_dict(),
        "config": _config_dict(base),
        "available_tradeable_sessions": len(dates),
        "fold_count": len(reports),
        "folds": reports,
        "selection": None,
        "evidence": EVIDENCE_LABEL,
    }
