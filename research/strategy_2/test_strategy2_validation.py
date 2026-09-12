"""Tests for the no-selection robustness and chronological fold helpers.

All bars are synthetic plumbing fixtures.  The tests prove orchestration
invariants only; they are not Strategy 2 performance evidence.
"""
from datetime import date, datetime, time, timedelta

import pytest

from research.strategy_2.strategy2_engine import Bar, NY, Strategy2Config, Strategy2DataError, validate_bars
from research.strategy_2.strategy2_validation import compare_target_modes, parameter_grid, run_walk_forward, walk_forward_folds


def make_sessions(count: int):
    bars = []
    first = date(2026, 1, 5)
    for day_offset in range(count):
        day = first + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        start = datetime.combine(day, time(9, 30), NY)
        previous = 100.0
        for index in range(78):
            close = 100.0
            opening = previous if index else close
            bars.append(Bar(start + timedelta(minutes=5 * index), opening, max(opening, close) + 0.25, min(opening, close) - 0.25, close, 1))
            previous = close
    return bars


def test_walk_forward_never_overlaps_is_and_oos_and_returns_no_unsupported_fold():
    dataset = validate_bars(make_sessions(20), "ES", "synthetic-fixture")
    folds = walk_forward_folds(dataset, train_sessions=3, test_sessions=2, step_sessions=2)
    assert folds
    for fold in folds:
        assert fold["train_end_before_test_start"] is True
        assert set(fold["train_dates"]).isdisjoint(fold["test_dates"])
    assert walk_forward_folds(dataset, train_sessions=30, test_sessions=2) == []


def test_walk_forward_and_target_comparison_do_not_select_a_variant():
    dataset = validate_bars(make_sessions(20), "MES", "synthetic-fixture")
    config = Strategy2Config(asset="MES", warmup_rth_bars=20)
    comparison = compare_target_modes(dataset, config)
    assert set(comparison["variants"]) == {"nearer", "mean", "atr"}
    assert comparison["selection"] is None
    assert comparison["evidence"].startswith("NOT PROJECT-OWNED")

    report = run_walk_forward(dataset, config, train_sessions=3, test_sessions=2)
    assert report["fold_count"] > 0
    assert report["selection"] is None
    assert all(fold["result"]["evidence"].startswith("NOT PROJECT-OWNED") for fold in report["folds"])


def test_parameter_grid_rejects_unknown_fields_and_keeps_every_combination():
    dataset = validate_bars(make_sessions(5), "ES", "synthetic-fixture")
    config = Strategy2Config(asset="ES", warmup_rth_bars=20)
    report = parameter_grid(dataset, config, {"z_entry": (1.6, 1.8), "adx_max": (20.0, 25.0)})
    assert len(report["results"]) == 4
    assert report["selection"] is None
    with pytest.raises(Strategy2DataError, match="Unknown"):
        parameter_grid(dataset, config, {"not_a_config_field": (1,)})
