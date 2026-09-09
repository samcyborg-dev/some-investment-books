"""Causal OHLC research kernel, separate from the retired synthetic engine.

Real source candles + explicitly assumed fills. Never live execution/compliance.
"""
from __future__ import annotations
from collections import Counter
from math import ceil,floor,sqrt
from typing import Literal
import numpy as np
from pydantic import BaseModel,ConfigDict,Field
from web_app.market_data import ASSETS,digest

VERSION='ORB-30R-price-research-0.1a'


class BacktestParams(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    asset:Literal['ES','MES','SPY','QQQ']='ES'
    initial_equity:float=Field(100000,ge=1000,le=10000000)
    risk_pct:float=Field(.5,ge=.05,le=2)
    round_trip_fee:float=Field(5,ge=0,le=500)
    slippage_ticks:int=Field(1,ge=0,le=20)
    max_units:int=Field(1,ge=1,le=1000)


def default_params(asset):
    a=ASSETS[asset]
    return BacktestParams(asset=asset,round_trip_fee=a['fee'],max_units=a['max_units'])


class Indicators:
    def __init__(self):self.reset()
    def reset(self):
        self.n=0;self.ema20=None;self.ema50=None;self.atr=None;self.prev_close=None;self.trs=[]
    def update(self,b):
        c=b['close'];tr=b['high']-b['low']
        if self.prev_close is not None:tr=max(tr,abs(b['high']-self.prev_close),abs(b['low']-self.prev_close))
        self.ema20=c if self.ema20 is None else self.ema20+(2/21)*(c-self.ema20)
        self.ema50=c if self.ema50 is None else self.ema50+(2/51)*(c-self.ema50)
        if self.atr is None:
            self.trs.append(tr)
            if len(self.trs)==14:self.atr=sum(self.trs)/14
        else:self.atr=(13*self.atr+tr)/14
        self.prev_close=c;self.n+=1


def prospective_signal(ind,range_high,range_low,tick):
    """Only completed prior information can arm the coming bar's stop order."""
    if ind.n<250 or not ind.atr or ind.atr<=0:return None,'warmup'
    if range_high-range_low>5*ind.atr:return None,'range_gate'
    c=ind.prev_close
    if c>ind.ema20>ind.ema50:
        trigger=range_high+tick
        return ((1,trigger,ind.atr),None) if c<trigger else (None,'already_crossed')
    if c<ind.ema20<ind.ema50:
        trigger=range_low-tick
        return ((-1,trigger,ind.atr),None) if c>trigger else (None,'already_crossed')
    return None,'trend_gate'


def round_price(value,tick,direction):
    return round((ceil(value/tick-1e-10) if direction>0 else floor(value/tick+1e-10))*tick,8)


def resolve_exit(pos,b,tick,slippage,new_entry=False):
    d=pos['direction'];stop=pos['stop'];target=pos['target'];op=b['open']
    # A pre-entry open cannot become a retroactive stop fill.
    if not new_entry and ((d==1 and op<=stop) or (d==-1 and op>=stop)):
        return round_price(op-d*slippage,tick,-d),'GAP_STOP',False
    stop_hit=b['low']<=stop if d==1 else b['high']>=stop
    target_hit=b['high']>=target+tick if d==1 else b['low']<=target-tick
    # Five-minute bars cannot sequence their extremes. Report the pessimistic bound.
    if stop_hit:return round_price(stop-d*slippage,tick,-d),'STOP',bool(new_entry or target_hit)
    if target_hit:return target,'TARGET',False
    return None,None,False


def run_backtest(dataset,params):
    if dataset['asset']!=params.asset:raise ValueError('Dataset/valuation asset mismatch. ES cannot silently become MES.')
    if digest(dataset['bars'])!=dataset['quality']['clean_sha256']:raise ValueError('Price checksum mismatch.')
    a=ASSETS[params.asset];tick=a['tick'];pv=a['point_value'];slip=params.slippage_ticks*tick
    by_day={d['date']:[] for d in dataset['days']}
    for b in dataset['bars']:
        # Match exact scheduled UTC bounds; never rely on the machine/chart timezone.
        for day in dataset['days']:
            if day['open']<=b['timestamp']<day['close']:
                by_day[day['date']].append(b);break
    cash=params.initial_equity;ind=Indicators();trades=[];daily=[];marks=[];skips=Counter();signal_log=[];rejected=[]
    start_t=dataset['start'];marks.append(dict(timestamp=start_t,equity=cash,drawdown=0))
    peak=cash;maxdd=0.;fees_total=0.;eligible_sessions=0;warmup_sessions=0
    def mark(t,pos,close):
        nonlocal peak,maxdd
        eq=cash+(pos['direction']*(close-pos['entry'])*pv*pos['quantity'] if pos else 0)
        peak=max(peak,eq);dd=100*(1-eq/peak);maxdd=max(maxdd,dd)
        marks.append(dict(timestamp=t,equity=eq,drawdown=dd))
    def finish(pos,price,bar,reason,ambiguous):
        nonlocal cash,fees_total
        q=pos['quantity'];gross=pos['direction']*(price-pos['entry'])*pv*q;fee=q*params.round_trip_fee
        cash+=gross-fee/2;fees_total+=fee/2
        trades.append(dict(id=len(trades)+1,date=pos['date'],side='LONG' if pos['direction']==1 else 'SHORT',quantity=q,
            entry_bar=pos['entry_bar'],exit_bar=bar['timestamp'],signal_bar=pos['signal_bar'],entry_price=pos['entry'],exit_price=price,
            entry_timing=pos['entry_timing'],exit_reason=reason,stop=pos['stop'],target=pos['target'],atr_armed=pos['atr'],
            initial_risk_usd=pos['risk'],net_pnl=gross-fee,r_multiple=(gross-fee)/pos['risk'],fees=fee,
            ambiguous=ambiguous,evidence='HISTORICAL PRICES / ASSUMED FILLS'))
    for day in dataset['days']:
        bars=by_day[day['date']]
        if not day['complete']:
            ind.reset();skips['incomplete_session']+=1
            continue
        before=cash;pos=None;traded=False;eligible=False;or_high=None;or_low=None
        for i,b in enumerate(bars):
            t=b['timestamp'];minute=(t-day['open'])//60
            # 15:50 open, not the close of the 15:50-labeled bar.
            if pos and t>=day['close']-600:
                # An already-resting target may be crossed at the opening print.
                # Do not grant a favorable gap beyond that conservative limit fill.
                through_target=(b['open']>=pos['target']+tick if pos['direction']==1 else b['open']<=pos['target']-tick)
                price=pos['target'] if through_target else round_price(b['open']-pos['direction']*slip,tick,-pos['direction'])
                finish(pos,price,b,'TARGET_AT_FLAT_OPEN' if through_target else 'TIME_EXIT',False);pos=None
            if pos:
                price,reason,amb=resolve_exit(pos,b,tick,slip)
                if price is not None:finish(pos,price,b,reason,amb);pos=None
            # Current high/low can execute a pre-armed order, never approve its filter.
            if not traded and not pos and day['tradeable'] and 30<=minute<240:
                if ind.n>=250:eligible=True
                signal,why=prospective_signal(ind,or_high,or_low,tick)
                if why:skips[why]+=1
                if signal:
                    direction,trigger,atr=signal
                    # ETFs need explicit borrow/short permissions; this initial comparison is long-only.
                    if direction<0 and a['kind']=='etf':skips['etf_long_only']+=1
                    else:
                        reached=b['high']>=trigger if direction==1 else b['low']<=trigger
                        if reached:
                            stop_dist=ceil(1.2*atr/tick-1e-10)*tick
                            target_dist=max(tick,floor(2.*atr/tick+1e-10)*tick)
                            price_risk=stop_dist*pv
                            q=min(params.max_units,floor((cash*params.risk_pct/100)/(price_risk+params.round_trip_fee+2*slip*pv)))
                            if a['kind']=='etf':
                                planned_fill=round_price(trigger+slip,tick,1)
                                q=min(q,floor(cash/(planned_fill+params.round_trip_fee/2)))
                            gap=b['open']>=trigger if direction==1 else b['open']<=trigger
                            base=(max(b['open'],trigger) if direction==1 else min(b['open'],trigger))
                            fill=round_price(base+direction*slip,tick,direction)
                            if a['kind']=='etf' and q*(fill+params.round_trip_fee/2)>cash:
                                # Reject the pre-sized order rather than resize using a future fill.
                                skips['gap_buying_power']+=1
                                mark(t+300,None,b['close']);ind.update(b)
                                continue
                            if q<=0:
                                skips['unaffordable']+=1
                                rejected.append(dict(date=day['date'],bar=t,side='LONG' if direction==1 else 'SHORT',
                                    reason='One integer unit exceeds the risk allowance',budget=cash*params.risk_pct/100,
                                    required_per_unit=price_risk+params.round_trip_fee+2*slip*pv,trigger=trigger,atr=atr))
                            else:
                                cash-=q*params.round_trip_fee/2;fees_total+=q*params.round_trip_fee/2
                                pos=dict(direction=direction,entry=fill,stop=round(fill-direction*stop_dist,8),
                                    target=round(fill+direction*target_dist,8),quantity=q,risk=q*price_risk,
                                    entry_bar=t,signal_bar=bars[i-1]['timestamp'],date=day['date'],atr=atr,
                                    entry_timing='bar open / gap model' if gap else 'within five-minute bar; exact time unknown')
                                traded=True
                                signal_log.append(dict(date=day['date'],armed_at=t,information_through=bars[i-1]['timestamp']+300,
                                    completed_bars=ind.n,ema20=ind.ema20,ema50=ind.ema50,atr=atr,trigger=trigger))
                                price,reason,amb=resolve_exit(pos,b,tick,slip,new_entry=True)
                                if price is not None:finish(pos,price,b,reason,amb);pos=None
            mark(t+300,pos,b['close'])
            ind.update(b)
            if i==5:or_high=max(r['high'] for r in bars[:6]);or_low=min(r['low'] for r in bars[:6])
        assert pos is None,'A complete session must contain the 15:50 liquidation bar.'
        if eligible:eligible_sessions+=1
        elif day['tradeable']:warmup_sessions+=1
        daily.append(dict(date=day['date'],equity=cash,net_pnl=cash-before,return_pct=100*(cash/before-1),eligible=eligible))
        if cash<=0:break
    assert abs(cash-(params.initial_equity+sum(t['net_pnl'] for t in trades)))<1e-6
    assert abs(fees_total-sum(t['fees'] for t in trades))<1e-6
    pnl=np.array([t['net_pnl'] for t in trades]);rs=np.array([t['r_multiple'] for t in trades])
    wins=pnl[pnl>0];losses=pnl[pnl<0];win_rs=rs[pnl>0];loss_rs=rs[pnl<0]
    gp=float(wins.sum());gl=float(-losses.sum())
    avg_win_r=float(win_rs.mean()) if len(win_rs) else None
    avg_loss_r=float(abs(loss_rs.mean())) if len(loss_rs) else None
    realized_rr=(avg_win_r/avg_loss_r) if avg_win_r is not None and avg_loss_r else None
    planned_rr=float(np.mean([abs(t['target']-t['entry_price'])/abs(t['entry_price']-t['stop']) for t in trades])) if trades else None
    eligible_returns=[d['return_pct']/100 for d in daily if d['eligible']]
    sharpe=None
    if len(eligible_returns)>=20 and np.std(eligible_returns,ddof=1)>0:
        sharpe=float(sqrt(252)*np.mean(eligible_returns)/np.std(eligible_returns,ddof=1))
    # Exact trade-close drawdown is distinct from the available five-minute marks.
    ce=np.r_[params.initial_equity,params.initial_equity+np.cumsum(pnl)]
    closing_dd=100*(1-ce/np.maximum.accumulate(ce))
    curve=[dict(index=i,label='Start' if i==0 else str(trades[i-1]['exit_bar']),equity=float(v),drawdown=float(closing_dd[i])) for i,v in enumerate(ce)]
    return dict(version=VERSION,evidence='PRICE-DATA RESEARCH BACKTEST / NOT LIVE',params=params.model_dump(),
        data_sha256=dataset['quality']['clean_sha256'],source_origin=dataset['provenance'].get('origin','UNKNOWN'),
        metrics=dict(trades=len(trades),wins=int((pnl>0).sum()),losses=int((pnl<0).sum()),
            win_rate=float(100*(pnl>0).mean()) if len(pnl) else None,net_pnl=cash-params.initial_equity,
            return_pct=100*(cash/params.initial_equity-1),profit_factor=gp/gl if gl else None,
            expectancy_r=float(rs.mean()) if len(rs) else None,average_win_r=avg_win_r,average_loss_r=avg_loss_r,
            realized_rr=realized_rr,planned_rr=planned_rr,ending_equity=cash,fees=fees_total,
            max_closing_dd_pct=float(closing_dd.max()),max_5m_close_dd_pct=maxdd,sharpe_diagnostic=sharpe,
            eligible_sessions=eligible_sessions,warmup_only_sessions=warmup_sessions,ambiguous_trades=sum(t['ambiguous'] for t in trades)),
        trades=trades,curve=curve,daily=daily,signal_audit=signal_log,rejected_triggers=rejected,skip_counts=dict(skips),
        limitations=[
            'Observed vendor prices, assumed execution. Neither exchange-authenticated data nor actual broker trades.',
            'Tiny samples are pipeline smoke tests, not evidence of a durable edge. No parameter optimization or walk-forward result is claimed.',
            'Five-minute OHLC cannot order extremes. Stop-first handling includes entry-bar uncertainty and can be pessimistic.',
            'Stop-market entries are armed prospectively from prior completed bars. ATR is frozen at arming; orders expire after one bar.',
            'Stop 1.2 ATR rounded out; target 2 ATR rounded in; target needs one-tick trade-through. No trailing stop or news filter.',
            'Integer units, assumed fees/slippage, one fill per cash session. ETFs are long-only with 1× cash buying power.',
            'Floating intrabar drawdown, futures margin, short borrow, order queues and firm-specific pass/compliance are NOT established.',
            'The test continues across the whole available sample; it does not stop early at a hypothetical profit target.',
        ])
