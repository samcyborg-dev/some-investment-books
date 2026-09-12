"""Causal Strategy 2 research kernel.

This module is deliberately separate from the older ``quant_engine`` prototype.
It accepts five-minute OHLCV bars, validates the RTH data contract, and models
one explicit next-bar execution convention.  It does not download prices,
connect to a broker, or turn vendor data into project-owned evidence.

The unit tests use synthetic fixtures only to test accounting and causality.
Any historical result must carry the input receipt and remain labelled as
user-supplied/vendor-reported until the project data gate is independently
approved.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from math import ceil, floor, isfinite, sqrt
from pathlib import Path
from statistics import median
from typing import Iterable, Literal, Sequence
from zoneinfo import ZoneInfo
import csv
import hashlib
import io
import json

NY = ZoneInfo("America/New_York")
UTC = timezone.utc
TICK = 0.25
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
BAR_MINUTES = 5
EXPECTED_RTH_BARS = 78

Asset = Literal["ES", "MES"]
TargetMode = Literal["nearer", "mean", "atr"]

ASSET_SPECS: dict[str, dict[str, float | str]] = {
    "ES": {"point_value": 50.0, "tick_value": 12.5, "tick_size": 0.25},
    "MES": {"point_value": 5.0, "tick_value": 1.25, "tick_size": 0.25},
}


class Strategy2DataError(ValueError):
    """Raised when a source cannot satisfy the declared five-minute contract."""


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise Strategy2DataError("Every bar timestamp must include a timezone offset.")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(UTC))
        for name in ("open", "high", "low", "close"):
            value = getattr(self, name)
            if not isfinite(value):
                raise Strategy2DataError(f"{name} must be finite.")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise Strategy2DataError("OHLC relationship is invalid.")
        if self.volume is not None and (not isfinite(self.volume) or self.volume < 0):
            raise Strategy2DataError("Volume must be finite and non-negative when supplied.")

    @property
    def new_york(self) -> datetime:
        return self.timestamp.astimezone(NY)

    @property
    def session_date(self) -> date:
        return self.new_york.date()

    @property
    def rth(self) -> bool:
        local = self.new_york
        return local.weekday() < 5 and RTH_OPEN <= local.time().replace(tzinfo=None) < RTH_CLOSE


@dataclass(frozen=True)
class SessionReceipt:
    session_date: str
    expected_bars: int
    observed_bars: int
    missing_bars: int
    invalid_bars: int
    complete: bool
    tradeable: bool
    status: str


@dataclass(frozen=True)
class QualityReceipt:
    asset: Asset
    source: str
    source_sha256: str | None
    acquired_at: str | None
    raw_rows: int
    rth_rows: int
    overnight_rows: int
    duplicate_rows: int
    conflicting_duplicates: int
    invalid_rows: int
    off_tick_rows: int
    misaligned_rows: int
    nonmonotonic_rows: int
    sessions: tuple[SessionReceipt, ...]
    warnings: tuple[str, ...]
    issues: tuple[str, ...]
    status: str
    project_owned: bool = False
    missing_volume_rows: int = 0
    zero_volume_rows: int = 0
    source_metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)

    @property
    def complete_sessions(self) -> int:
        return sum(row.complete for row in self.sessions)

    @property
    def tradeable_sessions(self) -> int:
        return sum(row.tradeable for row in self.sessions)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["sessions"] = [asdict(row) for row in self.sessions]
        result["complete_sessions"] = self.complete_sessions
        result["tradeable_sessions"] = self.tradeable_sessions
        return result


@dataclass(frozen=True)
class ValidatedDataset:
    asset: Asset
    bars: tuple[Bar, ...]
    receipt: QualityReceipt

    @property
    def tradeable_dates(self) -> set[date]:
        return {date.fromisoformat(row.session_date) for row in self.receipt.sessions if row.tradeable}

    def to_dict(self) -> dict:
        return {
            "asset": self.asset,
            "bar_count": len(self.bars),
            "receipt": self.receipt.to_dict(),
        }


@dataclass(frozen=True)
class Strategy2Config:
    asset: Asset = "ES"
    z_length: int = 20
    rsi_length: int = 14
    adx_length: int = 14
    adx_smoothing: int = 14
    atr_length: int = 14
    warmup_rth_bars: int = 250
    z_entry: float = 1.8
    z_stop: float = 3.2
    rsi_long: float = 32.0
    rsi_short: float = 68.0
    adx_max: float = 25.0
    atr_stop: float = 1.5
    atr_target: float = 1.8
    target_mode: TargetMode = "nearer"
    risk_pct: float = 0.50
    max_contracts: int = 1
    max_daily_fills: int = 4
    daily_kill_pct: float = 2.5
    total_loss_pct: float = 8.0
    commission_round_trip: float = 5.0
    slippage_ticks_per_side: float = 1.0
    initial_equity: float = 100_000.0
    signal_start: time = time(10, 15)
    signal_end: time = time(15, 5)
    eod_order_time: time = time(15, 45)
    eod_fill_time: time = time(15, 50)
    barrier_policy: str = "conservative_stop"

    def __post_init__(self) -> None:
        if self.asset not in ASSET_SPECS:
            raise Strategy2DataError(f"Unsupported asset: {self.asset}")
        if self.target_mode not in ("nearer", "mean", "atr"):
            raise Strategy2DataError("target_mode must be nearer, mean, or atr.")
        if self.barrier_policy != "conservative_stop":
            raise Strategy2DataError("Only the declared conservative_stop policy is implemented.")
        if any(value < 1 for value in (self.z_length, self.rsi_length, self.adx_length, self.adx_smoothing, self.atr_length)):
            raise Strategy2DataError("Indicator lengths must be positive.")
        if self.max_contracts < 1 or self.max_daily_fills < 1 or self.warmup_rth_bars < self.z_length:
            raise Strategy2DataError("Invalid contract cap, fill cap, or warm-up.")
        if any(value < 0.0 for value in (self.risk_pct, self.commission_round_trip, self.slippage_ticks_per_side)):
            raise Strategy2DataError("Risk, cost, and slippage values cannot be negative.")
        if self.risk_pct == 0.0 or self.daily_kill_pct <= 0.0 or self.total_loss_pct <= 0.0:
            raise Strategy2DataError("Risk budget and loss-guard percentages must be positive.")
        if self.initial_equity <= 0.0 or self.atr_stop <= 0.0 or self.atr_target <= 0.0:
            raise Strategy2DataError("Initial equity and ATR distances must be positive.")

    @property
    def point_value(self) -> float:
        return float(ASSET_SPECS[self.asset]["point_value"])

    @property
    def tick_size(self) -> float:
        return float(ASSET_SPECS[self.asset]["tick_size"])

    @property
    def tick_value(self) -> float:
        return float(ASSET_SPECS[self.asset]["tick_value"])

    @property
    def slippage_points(self) -> float:
        return self.slippage_ticks_per_side * self.tick_size


@dataclass(frozen=True)
class IndicatorState:
    rth_bars: int
    ema: float | None
    stddev: float | None
    z: float | None
    rsi: float | None
    adx: float | None
    atr: float | None


class CausalIndicators:
    """RTH-only indicators updated once, at a completed bar's close."""

    def __init__(self, config: Strategy2Config):
        self.config = config
        self.reset()

    def reset(self) -> None:
        self.rth_bars = 0
        self.ema: float | None = None
        self.prior_close: float | None = None
        self.prior_high: float | None = None
        self.prior_low: float | None = None
        self.close_window: deque[float] = deque(maxlen=self.config.z_length)
        self.tr_values: list[float] = []
        self.atr: float | None = None
        self.rsi_deltas: list[float] = []
        self.rsi_avg_gain: float | None = None
        self.rsi_avg_loss: float | None = None
        self.di_values: list[tuple[float, float, float]] = []
        self.smoothed_tr: float | None = None
        self.smoothed_plus_dm: float | None = None
        self.smoothed_minus_dm: float | None = None
        self.dx_values: list[float] = []
        self.adx: float | None = None

    def update(self, bar: Bar) -> IndicatorState:
        if not bar.rth:
            return self.state()
        tr = bar.high - bar.low
        gain = loss = 0.0
        plus_dm = minus_dm = 0.0
        if self.prior_close is not None:
            tr = max(tr, abs(bar.high - self.prior_close), abs(bar.low - self.prior_close))
            delta = bar.close - self.prior_close
            gain = max(delta, 0.0)
            loss = max(-delta, 0.0)
            up = bar.high - (self.prior_high if self.prior_high is not None else bar.high)
            down = (self.prior_low if self.prior_low is not None else bar.low) - bar.low
            plus_dm = up if up > down and up > 0.0 else 0.0
            minus_dm = down if down > up and down > 0.0 else 0.0

        self.rth_bars += 1
        alpha = 2.0 / (self.config.z_length + 1.0)
        self.ema = bar.close if self.ema is None else self.ema + alpha * (bar.close - self.ema)
        self.close_window.append(bar.close)
        if len(self.close_window) >= self.config.z_length:
            mean = sum(self.close_window) / len(self.close_window)
            variance = sum((value - mean) ** 2 for value in self.close_window) / (len(self.close_window) - 1)
            stddev = sqrt(max(variance, 0.0))
        else:
            stddev = None

        self.tr_values.append(tr)
        if len(self.tr_values) == self.config.atr_length:
            self.atr = sum(self.tr_values) / self.config.atr_length
        elif self.atr is not None:
            self.atr = ((self.atr * (self.config.atr_length - 1)) + tr) / self.config.atr_length

        if self.prior_close is not None:
            self.rsi_deltas.append(gain - loss)
            if len(self.rsi_deltas) == self.config.rsi_length:
                self.rsi_avg_gain = sum(max(delta, 0.0) for delta in self.rsi_deltas) / self.config.rsi_length
                self.rsi_avg_loss = sum(max(-delta, 0.0) for delta in self.rsi_deltas) / self.config.rsi_length
            elif self.rsi_avg_gain is not None and self.rsi_avg_loss is not None:
                self.rsi_avg_gain = ((self.rsi_avg_gain * (self.config.rsi_length - 1)) + gain) / self.config.rsi_length
                self.rsi_avg_loss = ((self.rsi_avg_loss * (self.config.rsi_length - 1)) + loss) / self.config.rsi_length

        if self.rsi_avg_gain is not None and self.rsi_avg_loss is not None:
            self._rsi = 100.0 if self.rsi_avg_loss == 0.0 else 100.0 - 100.0 / (1.0 + self.rsi_avg_gain / self.rsi_avg_loss)
        else:
            self._rsi = None

        self.di_values.append((tr, plus_dm, minus_dm))
        if len(self.di_values) == self.config.adx_length:
            self.smoothed_tr = sum(row[0] for row in self.di_values) / self.config.adx_length
            self.smoothed_plus_dm = sum(row[1] for row in self.di_values) / self.config.adx_length
            self.smoothed_minus_dm = sum(row[2] for row in self.di_values) / self.config.adx_length
        elif self.smoothed_tr is not None:
            self.smoothed_tr = ((self.smoothed_tr * (self.config.adx_length - 1)) + tr) / self.config.adx_length
            self.smoothed_plus_dm = ((self.smoothed_plus_dm * (self.config.adx_length - 1)) + plus_dm) / self.config.adx_length
            self.smoothed_minus_dm = ((self.smoothed_minus_dm * (self.config.adx_length - 1)) + minus_dm) / self.config.adx_length

        if self.smoothed_tr and self.smoothed_tr > 0.0 and self.smoothed_plus_dm is not None and self.smoothed_minus_dm is not None:
            plus_di = 100.0 * self.smoothed_plus_dm / self.smoothed_tr
            minus_di = 100.0 * self.smoothed_minus_dm / self.smoothed_tr
            total_di = plus_di + minus_di
            if total_di > 0.0:
                dx = 100.0 * abs(plus_di - minus_di) / total_di
                self.dx_values.append(dx)
                if len(self.dx_values) == self.config.adx_smoothing:
                    self.adx = sum(self.dx_values) / self.config.adx_smoothing
                elif self.adx is not None:
                    self.adx = ((self.adx * (self.config.adx_smoothing - 1)) + dx) / self.config.adx_smoothing

        self.prior_close = bar.close
        self.prior_high = bar.high
        self.prior_low = bar.low
        self._stddev = stddev
        self._z = (bar.close - self.ema) / stddev if stddev and stddev > 0.0 else None
        return self.state()

    def state(self) -> IndicatorState:
        return IndicatorState(
            rth_bars=self.rth_bars,
            ema=self.ema,
            stddev=getattr(self, "_stddev", None),
            z=getattr(self, "_z", None),
            rsi=getattr(self, "_rsi", None),
            adx=self.adx,
            atr=self.atr,
        )


@dataclass(frozen=True)
class Signal:
    direction: int
    signal_bar: datetime
    frozen_mean: float
    frozen_atr: float
    z: float
    rsi: float
    adx: float


def is_signal_window(local_time: time, config: Strategy2Config) -> bool:
    return config.signal_start <= local_time <= config.signal_end


def generate_signal(bar: Bar, state: IndicatorState, config: Strategy2Config) -> Signal | None:
    if not bar.rth or not is_signal_window(bar.new_york.time().replace(tzinfo=None), config):
        return None
    if state.rth_bars < config.warmup_rth_bars or any(value is None for value in (state.ema, state.z, state.rsi, state.adx, state.atr)):
        return None
    assert state.ema is not None and state.z is not None and state.rsi is not None and state.adx is not None and state.atr is not None
    if state.adx >= config.adx_max:
        return None
    if state.z <= -config.z_entry and state.rsi < config.rsi_long:
        return Signal(1, bar.timestamp, state.ema, state.atr, state.z, state.rsi, state.adx)
    if state.z >= config.z_entry and state.rsi > config.rsi_short:
        return Signal(-1, bar.timestamp, state.ema, state.atr, state.z, state.rsi, state.adx)
    return None


def round_tick(price: float, tick: float = TICK, direction: int = 0) -> float:
    """Round a price conservatively: direction +1 up, -1 down, 0 nearest."""
    if not isfinite(price) or tick <= 0.0:
        raise Strategy2DataError("Price and tick must be finite and positive.")
    quotient = price / tick
    if direction > 0:
        units = ceil(quotient - 1e-10)
    elif direction < 0:
        units = floor(quotient + 1e-10)
    else:
        units = floor(quotient + 0.5)
    return round(units * tick, 8)


def stop_price(entry: float, direction: int, atr: float, config: Strategy2Config) -> float:
    raw = entry - direction * atr * config.atr_stop
    return round_tick(raw, config.tick_size, -direction)


def target_price(entry: float, direction: int, mean: float, atr: float, config: Strategy2Config) -> float | None:
    atr_target = entry + direction * atr * config.atr_target
    mean_is_favorable = direction * (mean - entry) > config.tick_size * 0.5
    mean_target = round_tick(mean, config.tick_size, direction) if mean_is_favorable else None
    if config.target_mode == "atr":
        return round_tick(atr_target, config.tick_size, direction)
    if config.target_mode == "mean":
        return mean_target
    if mean_target is None:
        return round_tick(atr_target, config.tick_size, direction)
    if direction == 1:
        return min(mean_target, round_tick(atr_target, config.tick_size, direction))
    return max(mean_target, round_tick(atr_target, config.tick_size, direction))


def size_quantity(entry: float, stop: float, equity: float, config: Strategy2Config) -> tuple[int, float, float]:
    if equity <= 0.0:
        return 0, 0.0, 0.0
    price_risk = abs(entry - stop) * config.point_value
    slippage = 2.0 * config.slippage_ticks_per_side * config.tick_value
    per_contract = price_risk + config.commission_round_trip + slippage
    budget = equity * config.risk_pct / 100.0
    quantity = min(config.max_contracts, floor(budget / per_contract)) if per_contract > 0.0 else 0
    return int(max(quantity, 0)), per_contract, budget


def resolve_barrier(position: dict, bar: Bar, config: Strategy2Config) -> tuple[float | None, str | None, bool]:
    """Return exit price, reason, and ambiguity flag using the conservative tie rule."""
    direction = int(position["direction"])
    stop = float(position["stop"])
    target = float(position["target"])
    slip = config.slippage_points
    if (direction == 1 and bar.open <= stop) or (direction == -1 and bar.open >= stop):
        return round_tick(bar.open - direction * slip, config.tick_size, -direction), "GAP_STOP", False
    target_hit = bar.high >= target if direction == 1 else bar.low <= target
    stop_hit = bar.low <= stop if direction == 1 else bar.high >= stop
    if stop_hit and target_hit:
        return round_tick(stop - direction * slip, config.tick_size, -direction), "AMBIGUOUS_STOP_FIRST", True
    if stop_hit:
        return round_tick(stop - direction * slip, config.tick_size, -direction), "STOP", False
    if target_hit:
        return target, "TARGET", False
    return None, None, False


@dataclass
class Trade:
    id: int
    session_date: str
    side: str
    quantity: int
    signal_bar: str
    entry_bar: str
    exit_bar: str
    entry_price: float
    exit_price: float
    target: float
    stop: float
    frozen_mean: float
    frozen_atr: float
    signal_z: float
    signal_rsi: float
    signal_adx: float
    initial_risk_usd: float
    gross_pnl: float
    fees: float
    net_pnl: float
    r_multiple: float
    exit_reason: str
    ambiguous: bool
    entry_gap: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestResult:
    config: Strategy2Config
    receipt: QualityReceipt
    trades: list[Trade]
    marks: list[dict]
    diagnostics: dict[str, int | float | str | list]
    metrics: dict[str, float | int | None | dict]
    evidence: str = "HISTORICAL PRICES / ASSUMED FILLS / NOT PROJECT-OWNED"

    def to_dict(self) -> dict:
        result = {
            "config": {key: (value.isoformat() if isinstance(value, time) else value) for key, value in asdict(self.config).items()},
            "receipt": self.receipt.to_dict(),
            "trades": [trade.to_dict() for trade in self.trades],
            "marks": self.marks,
            "diagnostics": self.diagnostics,
            "metrics": self.metrics,
            "evidence": self.evidence,
        }
        return result


def _period_key(local_dt: datetime, period: str) -> str:
    if period == "day":
        return local_dt.date().isoformat()
    if period == "week":
        monday = local_dt.date() - timedelta(days=local_dt.weekday())
        return monday.isoformat()
    if period == "month":
        return local_dt.strftime("%Y-%m")
    raise ValueError(period)


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    low = floor(position)
    high = ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def calculate_metrics(trades: Sequence[Trade], marks: Sequence[dict], initial_equity: float) -> dict[str, float | int | None | dict]:
    net = [trade.net_pnl for trade in trades]
    gross = [trade.gross_pnl for trade in trades]
    r_values = [trade.r_multiple for trade in trades]
    wins = [value for value in net if value > 0.0]
    losses = [value for value in net if value < 0.0]
    periods: dict[str, dict[str, float]] = {"day": {}, "week": {}, "month": {}}
    for trade in trades:
        local = datetime.fromisoformat(trade.exit_bar).astimezone(NY)
        for period in periods:
            key = _period_key(local, period)
            periods[period][key] = periods[period].get(key, 0.0) + trade.net_pnl
    equity = [float(mark["equity"]) for mark in marks]
    peak = initial_equity
    max_dd_dollars = 0.0
    max_dd_pct = 0.0
    peak_index = trough_index = 0
    max_duration = 0
    for index, value in enumerate(equity):
        if value > peak:
            peak = value
            peak_index = index
        dd = peak - value
        if dd > max_dd_dollars:
            max_dd_dollars = dd
            max_dd_pct = 100.0 * dd / peak if peak else 0.0
            trough_index = index
        if value < peak:
            max_duration = max(max_duration, index - peak_index)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    current_streak = longest_streak = 0
    for value in net:
        if value < 0.0:
            current_streak += 1
            longest_streak = max(longest_streak, current_streak)
        else:
            current_streak = 0
    by_side = {}
    for side in ("LONG", "SHORT"):
        side_values = [trade.net_pnl for trade in trades if trade.side == side]
        by_side[side] = {"count": len(side_values), "net_pnl": sum(side_values), "expectancy": (sum(side_values) / len(side_values) if side_values else None)}
    return {
        "trade_count": len(trades),
        "gross_pnl": sum(gross),
        "net_pnl": sum(net),
        "fees": sum(trade.fees for trade in trades),
        "expectancy_usd": (sum(net) / len(net) if net else None),
        "average_trade": (sum(net) / len(net) if net else None),
        "median_trade": (median(net) if net else None),
        "win_rate_pct": (100.0 * len(wins) / len(net) if net else None),
        "loss_rate_pct": (100.0 * len(losses) / len(net) if net else None),
        "average_win": (sum(wins) / len(wins) if wins else None),
        "average_loss": (sum(losses) / len(losses) if losses else None),
        "payoff_ratio": (sum(wins) / len(wins) / (abs(sum(losses) / len(losses))) if wins and losses else None),
        "profit_factor": (gross_profit / gross_loss if gross_loss else None),
        "expectancy_r": (sum(r_values) / len(r_values) if r_values else None),
        "r_quantiles": {str(q): _quantile(r_values, q) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
        "max_drawdown_usd": max_dd_dollars,
        "max_drawdown_pct": max_dd_pct,
        "max_drawdown_duration_marks": max_duration,
        "longest_loss_streak": longest_streak,
        "worst_day": min(periods["day"].values()) if periods["day"] else None,
        "worst_week": min(periods["week"].values()) if periods["week"] else None,
        "worst_month": min(periods["month"].values()) if periods["month"] else None,
        "ambiguous_bar_count": sum(trade.ambiguous for trade in trades),
        "time_in_trade_minutes": sum((datetime.fromisoformat(trade.exit_bar) - datetime.fromisoformat(trade.entry_bar)).total_seconds() / 60.0 for trade in trades),
        "by_side": by_side,
    }


def run_backtest(
    dataset: ValidatedDataset,
    config: Strategy2Config | None = None,
    trade_dates: set[date] | None = None,
) -> BacktestResult:
    """Run the causal kernel, optionally scoring only a sealed date subset.

    Indicator state still advances through every accepted session in
    chronological order when ``trade_dates`` is supplied.  This makes a
    walk-forward OOS run causal: prior sessions can warm the indicators, but
    signals and fills are allowed only on the requested evaluation dates.
    """
    config = config or Strategy2Config(asset=dataset.asset)
    if dataset.asset != config.asset:
        raise Strategy2DataError("Dataset and configuration asset differ; ES cannot become MES.")
    tradeable = dataset.tradeable_dates
    evaluation_dates = tradeable if trade_dates is None else set(trade_dates) & tradeable
    bars_by_date: dict[date, list[Bar]] = {session: [] for session in tradeable}
    for bar in dataset.bars:
        if bar.session_date in tradeable:
            bars_by_date.setdefault(bar.session_date, []).append(bar)
    for rows in bars_by_date.values():
        rows.sort(key=lambda bar: bar.timestamp)

    indicators = CausalIndicators(config)
    trades: list[Trade] = []
    marks: list[dict] = [{"timestamp": dataset.bars[0].timestamp.isoformat(), "equity": config.initial_equity, "drawdown_pct": 0.0}] if dataset.bars else []
    diagnostics: Counter[str] = Counter()
    cash = config.initial_equity
    position: dict | None = None
    pending_entry: Signal | None = None
    pending_exit: str | None = None
    fills_today = 0
    current_day: date | None = None
    day_start_equity = config.initial_equity
    peak_equity = config.initial_equity
    daily_halted = total_halted = False
    last_timestamp: datetime | None = None

    def open_equity(mark_price: float) -> float:
        if position is None:
            return cash
        direction = int(position["direction"])
        unrealized = direction * (mark_price - float(position["entry_price"])) * config.point_value * int(position["quantity"])
        reserved_exit_fee = int(position["quantity"]) * config.commission_round_trip / 2.0
        return cash + unrealized - reserved_exit_fee

    def record_mark(bar: Bar) -> None:
        nonlocal peak_equity
        value = open_equity(bar.close)
        peak_equity = max(peak_equity, value)
        dd = 100.0 * max(0.0, peak_equity - value) / peak_equity if peak_equity else 0.0
        marks.append({"timestamp": bar.timestamp.isoformat(), "equity": value, "drawdown_pct": dd})

    def close_position(bar: Bar, price: float, reason: str, ambiguous: bool = False) -> None:
        nonlocal cash, position
        assert position is not None
        direction = int(position["direction"])
        quantity = int(position["quantity"])
        gross = direction * (price - float(position["entry_price"])) * config.point_value * quantity
        fees = quantity * config.commission_round_trip
        cash += gross - fees / 2.0
        trade = Trade(
            id=len(trades) + 1,
            session_date=str(position["session_date"]),
            side="LONG" if direction == 1 else "SHORT",
            quantity=quantity,
            signal_bar=position["signal_bar"],
            entry_bar=position["entry_bar"],
            exit_bar=bar.timestamp.isoformat(),
            entry_price=float(position["entry_price"]),
            exit_price=price,
            target=float(position["target"]),
            stop=float(position["stop"]),
            frozen_mean=float(position["frozen_mean"]),
            frozen_atr=float(position["frozen_atr"]),
            signal_z=float(position["signal_z"]),
            signal_rsi=float(position["signal_rsi"]),
            signal_adx=float(position["signal_adx"]),
            initial_risk_usd=float(position["initial_risk_usd"]),
            gross_pnl=gross,
            fees=fees,
            net_pnl=gross - fees,
            r_multiple=(gross - fees) / float(position["initial_risk_usd"]) if position["initial_risk_usd"] else 0.0,
            exit_reason=reason,
            ambiguous=ambiguous,
            entry_gap=bool(position["entry_gap"]),
        )
        trades.append(trade)
        position = None

    for session_date in sorted(bars_by_date):
        bars = bars_by_date[session_date]
        if current_day is not None and session_date != current_day:
            if position is not None or pending_entry is not None or pending_exit is not None:
                raise AssertionError("Complete session ended with a carried position or pending order.")
        current_day = session_date
        fills_today = 0
        day_start_equity = cash
        daily_halted = False
        for index, bar in enumerate(bars):
            last_timestamp = bar.timestamp
            if pending_entry is not None and position is None:
                signal = pending_entry
                pending_entry = None
                entry = round_tick(bar.open + signal.direction * config.slippage_points, config.tick_size, signal.direction)
                stop = stop_price(entry, signal.direction, signal.frozen_atr, config)
                target = target_price(entry, signal.direction, signal.frozen_mean, signal.frozen_atr, config)
                if target is None or signal.direction * (target - entry) <= 0.0:
                    diagnostics["invalid_mean_target_skips"] += 1
                elif fills_today >= config.max_daily_fills or daily_halted or total_halted:
                    diagnostics["entry_canceled_risk"] += 1
                else:
                    quantity, required, budget = size_quantity(entry, stop, open_equity(bar.open), config)
                    if quantity <= 0:
                        diagnostics["unaffordable_skips"] += 1
                    else:
                        cash -= quantity * config.commission_round_trip / 2.0
                        fills_today += 1
                        position = {
                            "direction": signal.direction,
                            "quantity": quantity,
                            "entry_price": entry,
                            "entry_bar": bar.timestamp.isoformat(),
                            "signal_bar": signal.signal_bar.isoformat(),
                            "session_date": session_date,
                            "stop": stop,
                            "target": target,
                            "frozen_mean": signal.frozen_mean,
                            "frozen_atr": signal.frozen_atr,
                            "signal_z": signal.z,
                            "signal_rsi": signal.rsi,
                            "signal_adx": signal.adx,
                            "initial_risk_usd": abs(entry - stop) * config.point_value * quantity,
                            "entry_gap": abs(bar.open - signal.frozen_mean) > config.tick_size,
                        }
                        diagnostics["fills"] += 1
                        if bar.open != signal.frozen_mean:
                            diagnostics["market_open_entries"] += 1

            if position is not None and pending_exit is not None:
                close_position(bar, round_tick(bar.open - int(position["direction"]) * config.slippage_points, config.tick_size, -int(position["direction"])), pending_exit)
                diagnostics[pending_exit.lower()] += 1
                pending_exit = None

            if position is not None:
                price, reason, ambiguous = resolve_barrier(position, bar, config)
                if price is not None:
                    close_position(bar, price, reason or "UNKNOWN", ambiguous)
                    diagnostics[(reason or "unknown").lower()] += 1

            state = indicators.update(bar)
            signal = (
                generate_signal(bar, state, config)
                if bar.session_date in evaluation_dates and position is None and pending_entry is None
                else None
            )
            if signal is not None and not daily_halted and not total_halted and fills_today < config.max_daily_fills:
                pending_entry = signal
                diagnostics["signals"] += 1

            local_time = bar.new_york.time().replace(tzinfo=None)
            if position is not None and state.z is not None:
                direction = int(position["direction"])
                z_stop_hit = (direction == 1 and state.z <= -config.z_stop) or (direction == -1 and state.z >= config.z_stop)
                if z_stop_hit and pending_exit is None:
                    pending_exit = "Z_STOP_NEXT_OPEN"
                    diagnostics["z_stop_signals"] += 1
            if position is not None and local_time == config.eod_order_time and pending_exit is None:
                pending_exit = "EOD_15_50_OPEN"
                diagnostics["eod_orders"] += 1

            value = open_equity(bar.close)
            if value <= day_start_equity * (1.0 - config.daily_kill_pct / 100.0):
                daily_halted = True
                diagnostics["daily_halts"] += 1
            if value <= config.initial_equity * (1.0 - config.total_loss_pct / 100.0):
                total_halted = True
                diagnostics["total_halts"] += 1
            if daily_halted or total_halted:
                pending_entry = None
            record_mark(bar)

        if position is not None:
            raise AssertionError("A complete RTH session must be flat after the 15:50 bar.")
        if pending_entry is not None or pending_exit is not None:
            diagnostics["stale_orders_canceled"] += 1
            pending_entry = pending_exit = None
        if indicators.rth_bars and any(bar.session_date == session_date for bar in bars):
            pass

    if last_timestamp is None and dataset.bars:
        last_timestamp = dataset.bars[-1].timestamp
    metrics = calculate_metrics(trades, marks, config.initial_equity)
    diagnostics["sessions_processed"] = len(bars_by_date)
    diagnostics["tradeable_sessions"] = len(tradeable)
    diagnostics["evaluation_sessions"] = len(evaluation_dates)
    diagnostics["project_owned_data"] = int(dataset.receipt.project_owned)
    return BacktestResult(config, dataset.receipt, trades, marks, dict(diagnostics), metrics)


def _parse_float(value: str, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise Strategy2DataError(f"Invalid {field_name}: {value!r}") from exc
    if not isfinite(parsed):
        raise Strategy2DataError(f"Invalid {field_name}: {value!r}")
    return parsed


def parse_timestamp(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise Strategy2DataError(f"Invalid ISO timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise Strategy2DataError("Timestamps must include an explicit UTC offset.")
    return parsed.astimezone(UTC)


def load_csv(path: str | Path, asset: Asset, source: str | None = None) -> ValidatedDataset:
    file_path = Path(path)
    raw = file_path.read_bytes()
    return load_csv_text(raw.decode("utf-8-sig"), asset, source=source or str(file_path), source_sha256=hashlib.sha256(raw).hexdigest())


def load_csv_text(text: str, asset: Asset, source: str = "USER_SUPPLIED_CSV", source_sha256: str | None = None) -> ValidatedDataset:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise Strategy2DataError("CSV has no header.")
    normalized_headers = [field.strip().lower() for field in reader.fieldnames if field]
    if len(normalized_headers) != len(set(normalized_headers)):
        raise Strategy2DataError("CSV headers must be unique.")
    fields = {field.strip().lower(): field for field in reader.fieldnames if field}
    required = {"timestamp", "open", "high", "low", "close"}
    missing = sorted(required - set(fields))
    if missing:
        raise Strategy2DataError("Missing CSV columns: " + ", ".join(missing))
    bars: list[Bar] = []
    accepted_symbols = {asset, f"{asset}=F"}
    for row_number, row in enumerate(reader, start=2):
        try:
            if "symbol" in fields and row.get(fields["symbol"], "").strip() not in accepted_symbols:
                raise Strategy2DataError(f"Symbol does not match selected {asset} asset.")
            volume = row.get(fields.get("volume", "")) if "volume" in fields else None
            bars.append(Bar(parse_timestamp(row[fields["timestamp"]]), _parse_float(row[fields["open"]], "open"), _parse_float(row[fields["high"]], "high"), _parse_float(row[fields["low"]], "low"), _parse_float(row[fields["close"]], "close"), _parse_float(volume, "volume") if volume not in (None, "") else None))
        except (KeyError, Strategy2DataError) as exc:
            raise Strategy2DataError(f"Row {row_number}: {exc}") from exc
    return validate_bars(
        bars,
        asset,
        source,
        source_sha256,
        source_metadata={"format": "csv", "claimed_asset": asset, "timeframe": "5m"},
    )


def load_yahoo_json(path: str | Path, asset: Asset, source: str | None = None) -> ValidatedDataset:
    file_path = Path(path)
    raw = file_path.read_bytes()
    expected_symbol = f"{asset}=F"
    try:
        payload = json.loads(raw)
        chart = payload["chart"]
        if chart.get("error"):
            raise Strategy2DataError(f"Yahoo chart error: {chart['error']}")
        result = chart["result"][0]
        meta = result.get("meta", {})
        if meta.get("symbol") != expected_symbol:
            raise Strategy2DataError(f"Yahoo symbol {meta.get('symbol')!r} does not match selected {asset} ({expected_symbol}).")
        if meta.get("dataGranularity") != "5m":
            raise Strategy2DataError("Only native Yahoo five-minute bars are supported.")
        if meta.get("instrumentType") not in (None, "FUTURE"):
            raise Strategy2DataError("Yahoo input is not a futures instrument.")
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        if not timestamps or any(len(quote[key]) != len(timestamps) for key in ("open", "high", "low", "close")):
            raise Strategy2DataError("Yahoo timestamp and OHLC arrays do not reconcile.")
        volume_values = quote.get("volume")
        if volume_values is not None and len(volume_values) != len(timestamps):
            raise Strategy2DataError("Yahoo timestamp and volume arrays do not reconcile.")
        bars = []
        for index, timestamp in enumerate(timestamps):
            values = [quote[key][index] for key in ("open", "high", "low", "close")]
            if any(value is None for value in values):
                raise Strategy2DataError(f"Yahoo row {index} has missing OHLC; input rejected without gap repair.")
            volume = volume_values[index] if volume_values is not None else None
            bars.append(Bar(datetime.fromtimestamp(timestamp, UTC), *(float(value) for value in values), float(volume) if volume is not None else None))
    except Strategy2DataError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError, json.JSONDecodeError) as exc:
        raise Strategy2DataError(f"Invalid Yahoo chart JSON: {exc}") from exc
    return validate_bars(
        bars,
        asset,
        source or str(file_path),
        hashlib.sha256(raw).hexdigest(),
        source_metadata={
            "format": "yahoo-chart-json",
            "symbol": meta.get("symbol"),
            "instrument_type": meta.get("instrumentType"),
            "data_granularity": meta.get("dataGranularity"),
            "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
            "exchange_timezone": meta.get("exchangeTimezoneName"),
            "short_name": meta.get("shortName"),
        },
    )


def _expected_timestamps(session_date: date) -> list[datetime]:
    start = datetime.combine(session_date, RTH_OPEN, NY)
    return [start.astimezone(UTC) + timedelta(minutes=BAR_MINUTES * index) for index in range(EXPECTED_RTH_BARS)]


def _off_tick(value: float, tick: float = TICK) -> bool:
    return abs(value / tick - round(value / tick)) > 1e-7


def validate_bars(
    bars: Iterable[Bar],
    asset: Asset,
    source: str,
    source_sha256: str | None = None,
    acquired_at: str | None = None,
    source_metadata: dict[str, str | int | float | bool | None] | None = None,
) -> ValidatedDataset:
    if asset not in ASSET_SPECS:
        raise Strategy2DataError(f"Unsupported asset: {asset}")
    original = list(bars)
    if not original:
        raise Strategy2DataError("No bars supplied.")
    duplicates = conflicting = invalid = off_tick = misaligned = nonmonotonic = overnight = 0
    missing_volume = zero_volume = 0
    issues: list[str] = []
    seen: dict[datetime, Bar] = {}
    last_timestamp: datetime | None = None
    for bar in original:
        if last_timestamp is not None and bar.timestamp < last_timestamp:
            nonmonotonic += 1
            issues.append("Timestamps are not strictly increasing in source order.")
        last_timestamp = max(last_timestamp, bar.timestamp) if last_timestamp is not None else bar.timestamp
        if bar.volume is None:
            missing_volume += 1
        elif bar.volume == 0.0:
            zero_volume += 1
        if not bar.rth:
            overnight += 1
            continue
        expected_minute = (bar.new_york.hour * 60 + bar.new_york.minute - 9 * 60 - 30)
        if expected_minute % BAR_MINUTES != 0 or bar.new_york.second != 0 or bar.new_york.microsecond != 0:
            misaligned += 1
        if asset in ASSET_SPECS and any(_off_tick(getattr(bar, name), float(ASSET_SPECS[asset]["tick_size"])) for name in ("open", "high", "low", "close")):
            off_tick += 1
        if bar.timestamp in seen:
            duplicates += 1
            if seen[bar.timestamp] != bar:
                conflicting += 1
            continue
        seen[bar.timestamp] = bar
    rth = sorted(seen.values(), key=lambda item: item.timestamp)
    sessions: list[SessionReceipt] = []
    accepted: list[Bar] = []
    by_date: dict[date, list[Bar]] = {}
    for bar in rth:
        by_date.setdefault(bar.session_date, []).append(bar)
    for session_date, rows in sorted(by_date.items()):
        expected = _expected_timestamps(session_date)
        observed = {row.timestamp for row in rows}
        missing = sum(timestamp not in observed for timestamp in expected)
        row_invalid = sum(any(_off_tick(getattr(row, name), TICK) for name in ("open", "high", "low", "close")) for row in rows)
        full = len(rows) == EXPECTED_RTH_BARS and missing == 0 and row_invalid == 0 and session_date.weekday() < 5
        status = "Complete" if full else "Rejected: incomplete or invalid RTH session"
        sessions.append(SessionReceipt(session_date.isoformat(), EXPECTED_RTH_BARS, len(rows), missing, row_invalid, full, full, status))
        if full:
            accepted.extend(rows)
    if duplicates:
        issues.append(f"{duplicates} duplicate timestamp rows encountered; identical duplicates were excluded.")
    if conflicting:
        issues.append(f"{conflicting} conflicting duplicate timestamps encountered.")
    if off_tick:
        issues.append(f"{off_tick} off-tick futures price observations encountered.")
    if misaligned:
        issues.append(f"{misaligned} RTH timestamps are not aligned to five-minute boundaries.")
    if not accepted:
        raise Strategy2DataError("No complete, valid 09:30-16:00 RTH sessions remain after quality checks.")
    warnings = [
        "Structural quality checks do not authenticate vendor prices or execution.",
        "Incomplete sessions are excluded; no bars are filled or relabelled.",
        "This receipt is not project-owned evidence unless independently approved.",
    ]
    if overnight:
        warnings.append(f"{overnight} overnight/pre-post rows were ignored for RTH indicator state.")
    if missing_volume:
        warnings.append(f"{missing_volume} bars have missing volume; no volume was invented and volume is not used as a signal filter.")
    if zero_volume:
        warnings.append(f"{zero_volume} bars report zero volume; retained for price testing but flagged for source review.")
    status = "PASS_FOR_KERNEL / NOT_PROJECT_OWNED" if not conflicting and not off_tick and not misaligned and not nonmonotonic else "PASS_WITH_REJECTED_SESSIONS / NOT_PROJECT_OWNED"
    receipt = QualityReceipt(
        asset,
        source,
        source_sha256,
        acquired_at,
        len(original),
        len(rth),
        overnight,
        duplicates,
        conflicting,
        invalid,
        off_tick,
        misaligned,
        nonmonotonic,
        tuple(sessions),
        tuple(warnings),
        tuple(issues),
        status,
        False,
        missing_volume,
        zero_volume,
        dict(source_metadata or {}),
    )
    return ValidatedDataset(asset, tuple(accepted), receipt)
