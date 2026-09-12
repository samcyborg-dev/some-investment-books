"""Unit and invariant tests for the causal Strategy 2 kernel.

Synthetic bars in this file are fixtures only.  They are not a backtest and
must never be copied into the dashboard as Strategy 2 performance evidence.
"""
from datetime import UTC, date, datetime, time, timedelta
import json

import pytest

from research.strategy_2.strategy2_engine import (
    NY,
    Bar,
    CausalIndicators,
    IndicatorState,
    Signal,
    Strategy2Config,
    Strategy2DataError,
    generate_signal,
    is_signal_window,
    load_csv_text,
    load_yahoo_json,
    resolve_barrier,
    run_backtest,
    round_tick,
    size_quantity,
    stop_price,
    target_price,
    validate_bars,
)


def make_session(day: date, closes=None, overnight=False):
    """Create a complete synthetic RTH session for plumbing tests only."""
    closes = list(closes or [100.0] * 78)
    assert len(closes) == 78
    start = datetime.combine(day, time(9, 30), NY)
    rows = []
    previous = closes[0]
    for index, close in enumerate(closes):
        open_price = previous if index else close
        high = max(open_price, close) + 0.25
        low = min(open_price, close) - 0.25
        rows.append(Bar(start + timedelta(minutes=5 * index), open_price, high, low, close, 100))
        previous = close
    if overnight:
        rows.insert(0, Bar(datetime.combine(day, time(8, 0), NY), 250, 300, 200, 275, 1))
    return rows


def test_quality_accepts_complete_rth_and_ignores_overnight():
    bars = make_session(date(2026, 1, 5), overnight=True) + make_session(date(2026, 1, 6))
    dataset = validate_bars(bars, "ES", "synthetic-fixture")
    assert len(dataset.bars) == 156
    assert dataset.receipt.raw_rows == 157
    assert dataset.receipt.overnight_rows == 1
    assert dataset.receipt.complete_sessions == 2
    assert dataset.receipt.tradeable_sessions == 2
    assert dataset.receipt.project_owned is False
    assert "overnight/pre-post" in " ".join(dataset.receipt.warnings)


def test_quality_rejects_only_incomplete_session_and_keeps_good_session():
    first = make_session(date(2026, 1, 5))
    second = make_session(date(2026, 1, 6))
    dataset = validate_bars(first[:-1] + second, "MES", "synthetic-fixture")
    assert dataset.receipt.complete_sessions == 1
    assert dataset.receipt.tradeable_sessions == 1
    assert dataset.receipt.sessions[0].complete is False
    assert dataset.receipt.sessions[1].complete is True
    assert len(dataset.bars) == 78


def test_quality_requires_a_complete_session():
    with pytest.raises(Strategy2DataError, match="No complete"):
        validate_bars(make_session(date(2026, 1, 5))[:-1], "ES", "synthetic-fixture")


def test_quality_detects_conflicting_duplicate_and_nonmonotonic_source():
    rows = make_session(date(2026, 1, 5))
    duplicate = rows[10]
    conflicting = Bar(duplicate.timestamp, duplicate.open + 0.25, duplicate.high + 0.25, duplicate.low + 0.25, duplicate.close + 0.25, duplicate.volume)
    dataset = validate_bars(rows[:20] + [conflicting] + rows[20:19:-1] + rows[21:], "ES", "synthetic-fixture")
    assert dataset.receipt.duplicate_rows >= 1
    assert dataset.receipt.conflicting_duplicates >= 1
    assert dataset.receipt.nonmonotonic_rows >= 1
    assert dataset.receipt.status.startswith("PASS_WITH_REJECTED")


def test_csv_requires_explicit_timezone_and_preserves_no_missing_bar_repair():
    rows = make_session(date(2026, 1, 5))
    csv_text = "timestamp,open,high,low,close,volume\n" + "\n".join(
        f"{bar.timestamp.isoformat()},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}" for bar in rows
    )
    loaded = load_csv_text(csv_text, "ES")
    assert loaded.receipt.complete_sessions == 1
    with pytest.raises(Strategy2DataError, match="explicit UTC offset"):
        load_csv_text(csv_text.replace("+00:00", "", 1), "ES")
    with pytest.raises(Strategy2DataError, match="Missing CSV columns"):
        load_csv_text(csv_text.replace(",close", "", 1), "ES")


def test_receipt_records_missing_and_zero_volume_without_inventing_values():
    rows = make_session(date(2026, 1, 5))
    rows[0] = Bar(rows[0].timestamp, rows[0].open, rows[0].high, rows[0].low, rows[0].close, None)
    rows[1] = Bar(rows[1].timestamp, rows[1].open, rows[1].high, rows[1].low, rows[1].close, 0)
    dataset = validate_bars(rows, "ES", "synthetic-fixture")
    assert dataset.receipt.missing_volume_rows == 1
    assert dataset.receipt.zero_volume_rows == 1
    assert "volume" in " ".join(dataset.receipt.warnings)


def test_csv_symbol_and_yahoo_metadata_are_not_silently_mixed(tmp_path):
    rows = make_session(date(2026, 1, 5))
    csv_text = "symbol,timestamp,open,high,low,close,volume\n" + "\n".join(
        f"ES=F,{bar.timestamp.isoformat()},{bar.open},{bar.high},{bar.low},{bar.close},{bar.volume}" for bar in rows
    )
    csv_path = tmp_path / "es.csv"
    csv_path.write_text(csv_text + "\n", encoding="utf-8")
    assert load_csv_text(csv_text, "ES").receipt.source_metadata["claimed_asset"] == "ES"
    with pytest.raises(Strategy2DataError, match="Symbol does not match"):
        load_csv_text(csv_text.replace("ES=F", "MES=F", 1), "ES")

    timestamps = [int(bar.timestamp.timestamp()) for bar in rows]
    values = {key: [getattr(bar, key) for bar in rows] for key in ("open", "high", "low", "close", "volume")}
    yahoo = {"chart": {"result": [{"meta": {"symbol": "ES=F", "dataGranularity": "5m", "instrumentType": "FUTURE", "fullExchangeName": "CME", "exchangeTimezoneName": "America/New_York"}, "timestamp": timestamps, "indicators": {"quote": [values]}}]}}
    yahoo_path = tmp_path / "es.json"
    yahoo_path.write_text(json.dumps(yahoo), encoding="utf-8")
    loaded = load_yahoo_json(yahoo_path, "ES")
    assert loaded.receipt.source_metadata["symbol"] == "ES=F"
    assert loaded.receipt.source_metadata["data_granularity"] == "5m"
    with pytest.raises(Strategy2DataError, match="does not match"):
        load_yahoo_json(yahoo_path, "MES")


def test_indicator_values_are_causal_and_use_sample_standard_deviation():
    config = Strategy2Config(z_length=3, rsi_length=2, adx_length=2, adx_smoothing=2, atr_length=2, warmup_rth_bars=3)
    bars = make_session(date(2026, 1, 5), closes=[100, 101, 99] + [100] * 75)
    stream = CausalIndicators(config)
    states = [stream.update(bar) for bar in bars[:3]]
    assert states[2].stddev == pytest.approx(1.0)
    assert states[2].ema == pytest.approx(99.75)
    assert states[2].z == pytest.approx(-0.75 / 1.0)

    prefix = CausalIndicators(config)
    full = CausalIndicators(config)
    for bar in bars[:20]:
        prefix_state = prefix.update(bar)
        full_state = full.update(bar)
        assert prefix_state == full_state
    # The state emitted at bar 20 remains the state that was observed then;
    # future bars are only allowed to affect later emissions.
    emitted = prefix.state()
    for bar in bars[20:]:
        prefix.update(bar)
        full.update(bar)
    assert emitted.rth_bars == 20
    assert prefix.state().rth_bars == len(bars)
    assert full.state() == prefix.state()


def test_overnight_bars_do_not_change_indicator_state():
    config = Strategy2Config(z_length=3, rsi_length=2, adx_length=2, adx_smoothing=2, atr_length=2, warmup_rth_bars=3)
    rth = make_session(date(2026, 1, 5), closes=[100, 101, 99] + [100] * 75)
    clean = CausalIndicators(config)
    with_overnight = CausalIndicators(config)
    for bar in rth[:20]:
        assert clean.update(bar) == with_overnight.update(bar)
    overnight = Bar(datetime.combine(date(2026, 1, 5), time(20, 0), NY), 500, 600, 400, 550, 1)
    assert with_overnight.update(overnight) == with_overnight.state()
    assert clean.state() == with_overnight.state()


def test_signal_filters_and_exact_clock_boundaries():
    config = Strategy2Config(warmup_rth_bars=250)
    state = IndicatorState(250, 100.0, 1.0, -2.0, 31.0, 20.0, 1.0)
    def bar_at(local_time):
        return Bar(datetime.combine(date(2026, 1, 5), local_time, NY), 99.0, 99.25, 98.75, 99.0, 100)
    assert generate_signal(bar_at(time(10, 14)), state, config) is None
    signal = generate_signal(bar_at(time(10, 15)), state, config)
    assert signal is not None and signal.direction == 1
    assert generate_signal(bar_at(time(15, 5)), state, config) is not None
    assert generate_signal(bar_at(time(15, 10)), state, config) is None
    assert is_signal_window(time(10, 15), config)
    assert is_signal_window(time(15, 5), config)
    assert not is_signal_window(time(15, 6), config)
    assert generate_signal(bar_at(time(10, 15)), IndicatorState(250, 100, 1, -2, 32, 20, 1), config) is None
    assert generate_signal(bar_at(time(10, 15)), IndicatorState(250, 100, 1, -2, 31, 25, 1), config) is None


def test_tick_rounding_sizing_and_integer_contracts():
    assert round_tick(100.01, 0.25, -1) == 100.0
    assert round_tick(100.01, 0.25, 1) == 100.25
    config = Strategy2Config(asset="ES", max_contracts=10, risk_pct=0.5, slippage_ticks_per_side=1)
    stop = stop_price(5000.25, 1, 2.0, config)
    assert stop == 4997.25
    quantity, required, budget = size_quantity(5000.25, stop, 100_000, config)
    assert quantity == 2
    assert required == pytest.approx(3.0 * 50 + 5.0 + 2.0 * 12.5)
    assert budget == 500
    assert isinstance(quantity, int)
    mes = Strategy2Config(asset="MES", max_contracts=100, risk_pct=0.5)
    assert size_quantity(5000.25, stop_price(5000.25, 1, 2.0, mes), 100_000, mes)[0] > quantity


def test_target_variants_are_explicit_and_nearer_has_fallback():
    base = dict(asset="ES", atr_target=1.8)
    assert target_price(100, 1, 103, 2, Strategy2Config(**base, target_mode="mean")) == 103.0
    assert target_price(100, 1, 103, 2, Strategy2Config(**base, target_mode="atr")) == 103.75
    assert target_price(100, 1, 103, 2, Strategy2Config(**base, target_mode="nearer")) == 103.0
    assert target_price(100, -1, 97, 2, Strategy2Config(**base, target_mode="nearer")) == 97.0
    assert target_price(100, 1, 99, 2, Strategy2Config(**base, target_mode="mean")) is None
    assert target_price(100, 1, 99, 2, Strategy2Config(**base, target_mode="nearer")) == 103.75


def test_conservative_barrier_resolution_marks_ambiguous_bars():
    config = Strategy2Config(asset="MES", slippage_ticks_per_side=1)
    position = {"direction": 1, "stop": 99.0, "target": 101.0}
    both = Bar(datetime(2026, 1, 5, 15, 0, tzinfo=UTC), 100.0, 101.25, 98.75, 100.0, 1)
    price, reason, ambiguous = resolve_barrier(position, both, config)
    assert price == 98.75
    assert reason == "AMBIGUOUS_STOP_FIRST"
    assert ambiguous is True
    target_bar = Bar(datetime(2026, 1, 5, 15, 5, tzinfo=UTC), 100.0, 101.25, 99.5, 101.0, 1)
    assert resolve_barrier(position, target_bar, config) == (101.0, "TARGET", False)
    gap = Bar(datetime(2026, 1, 5, 15, 10, tzinfo=UTC), 98.5, 99.0, 98.0, 98.75, 1)
    assert resolve_barrier(position, gap, config)[1] == "GAP_STOP"


def test_backtest_uses_next_bar_open_and_flattens_at_eod(monkeypatch):
    import research.strategy_2.strategy2_engine as engine

    day = date(2026, 1, 5)
    signal_local = datetime.combine(day, time(10, 15), NY)
    closes = [100.0] * 78
    signal_index = (10 * 60 + 15 - (9 * 60 + 30)) // 5
    closes[signal_index] = 98.0
    closes[signal_index + 1] = 100.0
    dataset = validate_bars(make_session(day, closes=closes), "MES", "synthetic-fixture")
    config = Strategy2Config(asset="MES", warmup_rth_bars=20, max_contracts=1, commission_round_trip=1.0)

    def fake_signal(bar, state, _config):
        if bar.timestamp == signal_local.astimezone(signal_local.tzinfo).astimezone(engine.UTC):
            return Signal(1, bar.timestamp, 100.0, 0.5, -2.0, 20.0, 10.0)
        return None

    monkeypatch.setattr(engine, "generate_signal", fake_signal)
    result = run_backtest(dataset, config)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.signal_bar == signal_local.astimezone(engine.UTC).isoformat()
    assert trade.entry_bar == (signal_local + timedelta(minutes=5)).astimezone(engine.UTC).isoformat()
    assert trade.entry_price != 98.0
    assert trade.exit_reason in {"TARGET", "AMBIGUOUS_STOP_FIRST", "EOD_15_50_OPEN", "Z_STOP_NEXT_OPEN"}
    assert trade.quantity == 1
    assert result.metrics["trade_count"] == 1
    assert result.metrics["fees"] == pytest.approx(1.0)
    assert result.diagnostics["fills"] == 1


def test_eod_order_is_submitted_at_1545_and_filled_at_1550_open(monkeypatch):
    import research.strategy_2.strategy2_engine as engine

    day = date(2026, 1, 5)
    dataset = validate_bars(make_session(day), "MES", "synthetic-fixture")
    config = Strategy2Config(asset="MES", warmup_rth_bars=20, max_contracts=1, commission_round_trip=1.0)

    def fake_signal(bar, state, _config):
        if bar.new_york.time().replace(tzinfo=None) == time(15, 40):
            return Signal(1, bar.timestamp, 100.0, 10.0, -2.0, 20.0, 10.0)
        return None

    monkeypatch.setattr(engine, "generate_signal", fake_signal)
    result = run_backtest(dataset, config)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_bar == datetime.combine(day, time(15, 45), NY).astimezone(engine.UTC).isoformat()
    assert trade.exit_bar == datetime.combine(day, time(15, 50), NY).astimezone(engine.UTC).isoformat()
    assert trade.exit_reason == "EOD_15_50_OPEN"
    assert result.diagnostics["eod_orders"] == 1


@pytest.mark.parametrize("guard", ["daily", "total"])
def test_loss_guards_halt_later_entries(monkeypatch, guard):
    import research.strategy_2.strategy2_engine as engine

    day = date(2026, 1, 5)
    bars = make_session(day)
    signal_index = (10 * 60 + 15 - (9 * 60 + 30)) // 5
    # The next bar crosses the long protective stop. All prices stay on the
    # MES tick grid, and this loss is larger than the selected 0.01% guard.
    entry_bar = bars[signal_index + 1]
    bars[signal_index + 1] = Bar(entry_bar.timestamp, entry_bar.open, entry_bar.open + 0.25, entry_bar.open - 3.25, entry_bar.open - 3.0, entry_bar.volume)
    dataset = validate_bars(bars, "MES", "synthetic-fixture")
    config = Strategy2Config(
        asset="MES",
        warmup_rth_bars=20,
        max_contracts=1,
        commission_round_trip=1.0,
        daily_kill_pct=0.01 if guard == "daily" else 99.0,
        total_loss_pct=0.01 if guard == "total" else 99.0,
    )
    signal_times = {time(10, 15), time(11, 0)}

    def fake_signal(bar, state, _config):
        if bar.new_york.time().replace(tzinfo=None) in signal_times:
            return Signal(1, bar.timestamp, 100.0, 2.0, -2.0, 20.0, 10.0)
        return None

    monkeypatch.setattr(engine, "generate_signal", fake_signal)
    result = run_backtest(dataset, config)
    assert len(result.trades) == 1
    assert result.diagnostics["fills"] == 1
    assert result.diagnostics[f"{guard}_halts"] >= 1


def test_trade_date_filter_warms_indicators_but_scores_only_the_sealed_oos_date(monkeypatch):
    import research.strategy_2.strategy2_engine as engine

    first = date(2026, 1, 5)
    second = date(2026, 1, 6)
    dataset = validate_bars(make_session(first) + make_session(second), "MES", "synthetic-fixture")
    config = Strategy2Config(asset="MES", warmup_rth_bars=20, max_contracts=1, commission_round_trip=1.0)

    def fake_signal(bar, state, _config):
        if bar.new_york.time().replace(tzinfo=None) == time(10, 15):
            return Signal(1, bar.timestamp, 100.0, 10.0, -2.0, 20.0, 10.0)
        return None

    monkeypatch.setattr(engine, "generate_signal", fake_signal)
    result = run_backtest(dataset, config, trade_dates={second})
    assert len(result.trades) == 1
    assert result.trades[0].session_date == second.isoformat()
    assert result.diagnostics["evaluation_sessions"] == 1
    assert result.diagnostics["sessions_processed"] == 2


def test_empty_signal_run_does_not_invent_metrics():
    dataset = validate_bars(make_session(date(2026, 1, 5)), "ES", "synthetic-fixture")
    config = Strategy2Config(asset="ES", warmup_rth_bars=250)
    result = run_backtest(dataset, config)
    assert result.trades == []
    assert result.metrics["trade_count"] == 0
    assert result.metrics["net_pnl"] == 0
    assert result.metrics["win_rate_pct"] is None
    assert result.metrics["profit_factor"] is None
    assert result.evidence.endswith("NOT PROJECT-OWNED")
