"""Research-only ORB calculations. No market feed, backtester, or broker actions.

The baseline reproduces the dossier's seeded educational model. Imported ledgers
are user-supplied records, never described as independently verified results.
"""
from __future__ import annotations

import csv
import io
import math
import re
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

N_PATHS = 20_000


class SimulationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    win_rate: float = Field(45, ge=25, le=75)
    risk_pct: float = Field(.5, ge=.05, le=2)
    cost_r: float = Field(.1, ge=0, le=.5)
    activity_pct: float = Field(60, ge=10, le=100)
    sessions: int = Field(60, ge=20, le=120)
    initial_equity: float = Field(100_000, ge=1_000, le=10_000_000)
    stop_atr: float = Field(1.2, ge=.5, le=4)
    target_atr: float = Field(2, ge=.5, le=8)
    target_pct: float = Field(8, ge=1, le=20)
    loss_limit_pct: float = Field(8, ge=1, le=20)
    floor: Literal['static', 'trailing'] = 'static'
    loss_persistence: float | None = Field(None, ge=0, le=1)
    gap_probability_pct: float = Field(0, ge=0, le=5)
    gap_loss_r: float = Field(3, ge=1, le=10)
    seed: int = Field(20260908, ge=0, le=4_294_967_295)

    @model_validator(mode='after')
    def valid_markov(self):
        if self.loss_persistence is not None:
            p = self.win_rate / 100
            if not 0 <= (1-p)*(1-self.loss_persistence)/p <= 1:
                raise ValueError('Loss persistence is incompatible with the marginal win probability.')
        return self


def wilson(k: int, n: int):
    z = 1.959963984540054
    p = k/n
    den = 1+z*z/n
    centre = (p+z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [100*(centre-half), 100*(centre+half)]


@lru_cache(maxsize=8)
def _simulate_cached(encoded: str):
    s = SimulationInput.model_validate_json(encoded)
    n, horizon = N_PATHS, s.sessions
    rng = np.random.default_rng(s.seed)
    # Preserve the exact draw order used in research/strategy_1/calculate_examples.py.
    activity = rng.random((horizon, n))
    outcome = rng.random((horizon, n))
    initial = rng.random(n)
    gaps = rng.random((horizon, n))
    p, f = s.win_rate/100, s.risk_pct/100
    win_r = s.target_atr/s.stop_atr
    eq = np.full(n, s.initial_equity)
    peak = eq.copy()
    maxdd = np.zeros(n)
    status = np.zeros(n, dtype=np.int8)
    days = np.zeros(n, dtype=np.int16)
    trades = np.zeros(n, dtype=np.int16)
    prev_loss = initial < (1-p)
    history = np.empty((horizon+1, n))
    dd_history = np.empty_like(history)
    history[0] = eq
    dd_history[0] = 0
    loss_allowance = s.initial_equity*s.loss_limit_pct/100
    target = s.initial_equity*(1+s.target_pct/100)
    q_lw = ((1-p)*(1-s.loss_persistence)/p) if s.loss_persistence is not None else None
    for d in range(horizon):
        active = (status == 0) & (activity[d] < s.activity_pct/100)
        loss = (outcome[d] >= p) if q_lw is None else (outcome[d] < np.where(prev_loss, s.loss_persistence, q_lw))
        prev_loss = np.where(active, loss, prev_loss)
        gap = loss & (gaps[d] < s.gap_probability_pct/100)
        gross = np.where(loss, -1., win_r)
        gross = np.where(gap, -s.gap_loss_r, gross)
        net_r = np.where(active, gross-s.cost_r, 0.)
        eq *= 1+f*net_r
        trades += active
        peak = np.maximum(peak, eq)
        dd = 1-eq/peak
        maxdd = np.maximum(maxdd, dd)
        floor = (s.initial_equity-loss_allowance) if s.floor == 'static' else peak-loss_allowance
        breach = (status == 0) & (eq <= floor)
        passed = (status == 0) & ~breach & (eq >= target)
        status[breach] = 2
        status[passed] = 1
        days[breach | passed] = d+1
        history[d+1] = eq
        dd_history[d+1] = dd*100
    passed, breached, unresolved = (int((status == x).sum()) for x in (1, 2, 0))
    assert passed+breached+unresolved == n
    bands = np.quantile(history, [.05, .50, .95], axis=1)
    ddbands = np.quantile(dd_history, [.05, .50, .95], axis=1)
    paths = [dict(session=i, low=float(bands[0,i]), median=float(bands[1,i]), high=float(bands[2,i]),
                  dd_low=float(ddbands[0,i]), dd_median=float(ddbands[1,i]), dd_high=float(ddbands[2,i]))
             for i in range(horizon+1)]
    end_return = 100*(eq/s.initial_equity-1)
    counts, edges = np.histogram(end_return, bins=24)
    mean_loss = 1+(s.gap_probability_pct/100)*(s.gap_loss_r-1)
    gross_expectancy = p*win_r-(1-p)*mean_loss
    return {
        'evidence': 'ILLUSTRATIVE', 'kind': 'uncalibrated_two_outcome_model',
        'params': s.model_dump(), 'n_paths': n,
        'metrics': {
            'passed': passed, 'breached': breached, 'unresolved': unresolved,
            'pass_pct': 100*passed/n, 'breach_pct': 100*breached/n, 'unresolved_pct': 100*unresolved/n,
            'pass_ci': wilson(passed, n),
            'median_days_if_pass': float(np.median(days[status == 1])) if passed else None,
            'dd95_pct': float(np.quantile(maxdd, .95))*100,
            'median_max_dd_pct': float(np.median(maxdd))*100,
            'median_ending_equity': float(np.median(eq)),
            'median_return_pct': float(np.median(end_return)),
            'median_trades': float(np.median(trades)),
            'gross_expectancy_r': gross_expectancy, 'net_expectancy_r': gross_expectancy-s.cost_r,
            'gross_win_r': win_r, 'net_win_r': win_r-s.cost_r, 'net_ordinary_loss_r': -1-s.cost_r,
            'breakeven_pct': 100*(mean_loss+s.cost_r)/(win_r+mean_loss),
            'payoff_ratio': max(0, win_r-s.cost_r)/(mean_loss+s.cost_r),
        },
        'paths': paths,
        'histogram': [dict(low=float(edges[i]), high=float(edges[i+1]), count=int(counts[i])) for i in range(len(counts))],
        'limitations': [
            'All probabilities are assumed, not estimated from ES/MES trades.',
            'No market prices, ORB signals, integer contracts, or intrabar equity are simulated.',
            'Paths stop at the target or floor, then remain flat for display. Drawdown is censored.',
            'Changing target geometry does not preserve the real strategy win probability.',
            'Not a firm-specific pass probability or an execution/compliance test.',
        ],
    }


def simulate(s: SimulationInput):
    return _simulate_cached(s.model_dump_json())


class SizingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    instrument: Literal['ES', 'MES'] = 'MES'
    budget: float = Field(500, gt=0, le=1_000_000)
    atr: float = Field(5, gt=0, le=1000)
    stop_atr: float = Field(1.2, ge=.1, le=10)
    fees: float = Field(2, ge=0, le=500)
    slippage_ticks: int = Field(2, ge=0, le=100)


def position_size(s: SizingInput):
    d = lambda x: Decimal(str(x))
    tick, multiplier = d('.25'), d(50 if s.instrument == 'ES' else 5)
    distance = (d(s.atr)*d(s.stop_atr)/tick).to_integral_value(rounding=ROUND_CEILING)*tick
    price_risk = distance*multiplier
    reserve = d(s.slippage_ticks)*tick*multiplier
    unit = price_risk+d(s.fees)+reserve
    qty = int((d(s.budget)/unit).to_integral_value(rounding=ROUND_FLOOR))
    return dict(evidence='DERIVED', instrument=s.instrument, contracts=qty, stop_points=float(distance),
                price_risk_per_contract=float(price_risk), reserve_per_contract=float(reserve),
                cost_per_contract=float(unit), budget_used=float(qty*unit), unused=float(d(s.budget)-qty*unit),
                note='Execution allowance is a reserve, not a maximum-loss guarantee. No orders are placed.')


class LedgerInput(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    csv_text: str = Field(min_length=1, max_length=1_000_000)
    initial_equity: float = Field(100_000, ge=1_000, le=10_000_000)
    example: bool = False


LEDGER_COLUMNS = ['entry_time', 'exit_time', 'symbol', 'side', 'quantity', 'entry_price', 'exit_price', 'fees', 'initial_risk_usd']


def ledger_template(sample=False):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(LEDGER_COLUMNS)
    if sample:
        rows = [
            ['2026-08-17T10:05:00-04:00','2026-08-17T10:40:00-04:00','ES','LONG',1,6000.50,6010.50,5,300],
            ['2026-08-18T10:10:00-04:00','2026-08-18T10:20:00-04:00','ES','LONG',1,6000.50,5994.00,5,300],
            ['2026-08-19T10:05:00-04:00','2026-08-19T11:00:00-04:00','ES','SHORT',1,5991.50,5981.50,5,300],
            ['2026-08-20T10:25:00-04:00','2026-08-20T10:50:00-04:00','ES','LONG',1,6000.50,6004.50,5,300],
            ['2026-08-21T10:05:00-04:00','2026-08-21T10:20:00-04:00','ES','SHORT',1,5991.50,5997.50,5,300],
            ['2026-08-24T10:15:00-04:00','2026-08-24T11:15:00-04:00','MES','LONG',10,6000.00,6010.00,20,300],
        ]
        writer.writerows(rows)
    return out.getvalue()


def analyze_ledger(s: LedgerInput):
    """Closing-trade accounting only. No inferred no-trade calendar or intrabar risk."""
    stream = io.StringIO(s.csv_text.lstrip('\ufeff'))
    reader = csv.DictReader(stream)
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('CSV must have a unique header row. Download the template for the required format.')
    missing = set(LEDGER_COLUMNS)-set(reader.fieldnames)
    if missing:
        raise ValueError('Missing columns: '+', '.join(sorted(missing)))
    trades, seen = [], set()
    for i, row in enumerate(reader, start=2):
        if i > 5001:
            raise ValueError('Limit: 5,000 trades per import.')
        if None in row or any(row[k] is None for k in LEDGER_COLUMNS):
            raise ValueError(f'Row {i}: unexpected or missing CSV cells.')
        if all(not (v or '').strip() for v in row.values()):
            continue
        try:
            entry_time = datetime.fromisoformat(row['entry_time'].strip().replace('Z','+00:00'))
            exit_time = datetime.fromisoformat(row['exit_time'].strip().replace('Z','+00:00'))
            if entry_time.utcoffset() is None or exit_time.utcoffset() is None:
                raise ValueError('timestamps must include a UTC offset')
            if exit_time <= entry_time:
                raise ValueError('exit must be after entry')
            symbol = row['symbol'].strip().upper()
            if not re.fullmatch(r'(MES|ES)([FGHJKMNQUVXZ]\d{1,4})?',symbol):
                raise ValueError('symbol must be ES/MES, optionally with a futures month code')
            side = row['side'].strip().upper()
            if side not in ('LONG','SHORT'):
                raise ValueError('side must be LONG or SHORT')
            quantity, entry, exit_, fees, risk = [float(row[k]) for k in ['quantity','entry_price','exit_price','fees','initial_risk_usd']]
            if not all(math.isfinite(v) for v in [quantity,entry,exit_,fees,risk]):
                raise ValueError('numeric values must be finite')
            if quantity != int(quantity) or not 1 <= quantity <= 10000:
                raise ValueError('quantity must be a positive integer, at most 10,000')
            if not (.25 <= entry <= 10_000_000 and .25 <= exit_ <= 10_000_000):
                raise ValueError('prices must be between 0.25 and 10,000,000 points')
            if not (0 <= fees <= 100_000_000 and .01 <= risk <= 1_000_000_000_000):
                raise ValueError('fees must be nonnegative and initial risk must be at least $0.01, within supported limits')
            if any(abs(v*4-round(v*4)) > 1e-7 for v in [entry,exit_]):
                raise ValueError('ES/MES fill prices must lie on the 0.25-point tick grid')
            key = tuple(row[k].strip() for k in LEDGER_COLUMNS)
            if key in seen:
                raise ValueError('duplicate trade')
            seen.add(key)
            multiplier = 5 if symbol.startswith('MES') else 50
            pnl = (exit_-entry)*(1 if side == 'LONG' else -1)*quantity*multiplier-fees
            trades.append(dict(entry_time=entry_time.isoformat(),exit_time=exit_time.isoformat(),symbol=symbol,side=side,
                               quantity=int(quantity),entry_price=entry,exit_price=exit_,fees=fees,initial_risk_usd=risk,
                               net_pnl=pnl,r_multiple=pnl/risk,holding_minutes=(exit_time-entry_time).total_seconds()/60))
        except (ValueError, TypeError) as exc:
            raise ValueError(f'Row {i}: {exc}') from exc
    if not trades:
        raise ValueError('No trades found. Add closed trades beneath the header.')
    trades.sort(key=lambda t: datetime.fromisoformat(t['entry_time']))
    for a,b in zip(trades,trades[1:]):
        if datetime.fromisoformat(b['entry_time']) < datetime.fromisoformat(a['exit_time']):
            raise ValueError('Overlapping positions are not supported by this one-position closing-trade analysis.')
    pnl = np.array([t['net_pnl'] for t in trades])
    rs = np.array([t['r_multiple'] for t in trades])
    equity = np.r_[s.initial_equity, s.initial_equity+np.cumsum(pnl)]
    if np.any(equity <= 0):
        raise ValueError('The starting equity is insufficient for this ledger. Check equity, quantities and fees.')
    peaks = np.maximum.accumulate(equity)
    dd = 100*(1-equity/peaks)
    gp, gl = float(pnl[pnl>0].sum()), float(-pnl[pnl<0].sum())
    streak = longest = 0
    for x in pnl:
        streak = streak+1 if x<0 else 0
        longest = max(longest,streak)
    episodes = []
    peak_index = 0
    start = None
    for i in range(1,len(equity)):
        if equity[i] >= equity[peak_index]:
            if start is not None:
                trough = start+int(np.argmin(equity[start:i+1]))
                episodes.append(dict(peak=peak_index,trough=trough,recovery=i,depth_pct=float(dd[trough]),duration=i-peak_index))
                start = None
            peak_index = i
        elif start is None:
            start = i
    if start is not None:
        trough = start+int(np.argmin(equity[start:]))
        episodes.append(dict(peak=peak_index,trough=trough,recovery=None,depth_pct=float(dd[trough]),duration=len(equity)-1-peak_index))
    points = [dict(index=0,label='Start',equity=float(equity[0]),drawdown=0)]
    for i,t in enumerate(trades,1):
        t['id'] = i
        t['equity'] = float(equity[i])
        points.append(dict(index=i,label=t['exit_time'],equity=float(equity[i]),drawdown=float(dd[i])))
    return dict(evidence='ILLUSTRATIVE' if s.example else 'USER-SUPPLIED', kind='closed_trade_ledger',
                initial_equity=s.initial_equity, trades=trades, curve=points, episodes=episodes,
                metrics=dict(net_pnl=float(pnl.sum()),total_return_pct=float(100*(equity[-1]/equity[0]-1)),
                             count=len(trades),wins=int((pnl>0).sum()),losses=int((pnl<0).sum()),scratches=int((pnl==0).sum()),
                             win_rate=float(100*(pnl>0).mean()),expectancy_r=float(rs.mean()),
                             profit_factor=gp/gl if gl else None,profit_factor_note='No losses; ratio undefined' if not gl else '',
                             avg_win=float(pnl[pnl>0].mean()) if (pnl>0).any() else None,
                             avg_loss=float(-pnl[pnl<0].mean()) if (pnl<0).any() else None,
                             max_closing_dd_pct=float(dd.max()),longest_loss_streak=longest,
                             fees=float(sum(t['fees'] for t in trades)),ending_equity=float(equity[-1])),
                limitations=['User-supplied records are not independently verified; ORB signal validity is not tested.',
                             'Equity is reconstructed at trade closes, assumes no external cash flows, and excludes open P&L.',
                             'Intraday drawdown, Sharpe, Sortino and firm pass probability are not inferred from this file.',
                             'Imported records are processed in memory, not saved to the server.'])


def session_plan(day):
    ny, nairobi = ZoneInfo('America/New_York'), ZoneInfo('Africa/Nairobi')
    events = [('Opening range starts',9,30),('Range frozen · entries eligible',10,0),('New entries stop',13,30),('Proposed flat deadline',15,50)]
    rows = []
    for label,h,m in events:
        dt = datetime(day.year,day.month,day.day,h,m,tzinfo=ny)
        nai = dt.astimezone(nairobi)
        rows.append(dict(label=label,new_york=dt.strftime('%H:%M'),nairobi=nai.strftime('%H:%M'),utc=dt.astimezone(ZoneInfo('UTC')).strftime('%H:%M'),offset=dt.strftime('%Z')))
    return dict(date=day.isoformat(),weekend=day.weekday()>4,events=rows,
                note='Timezone conversion only. Check the exchange holiday calendar and broker rules before trading.')
