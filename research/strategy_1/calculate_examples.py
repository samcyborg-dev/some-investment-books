"""Reproducible educational arithmetic, NOT an ORB historical backtest.

All trade probabilities, costs in R, activity rates and dependencies are assumptions.
No price feed, ORB signal generator or prop firm's real contract is represented.
Run from any directory: python research/strategy_1/calculate_examples.py
"""
from pathlib import Path
from dataclasses import dataclass, asdict
import hashlib
import json
import math
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FIG = HERE / 'figures'
FIG.mkdir(exist_ok=True)
SEED = 20260908
N = 20000
HORIZON = 60
TEAL = '#117c83'
NAVY = '#162b43'
CORAL = '#c96351'
GOLD = '#be9145'
GRAY = '#64748b'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.labelcolor': NAVY, 'xtick.color': GRAY, 'ytick.color': GRAY,
                     'text.color': NAVY, 'axes.edgecolor': '#d2dce3',
                     'axes.titleweight': 'bold', 'figure.facecolor': 'white',
                     'savefig.facecolor': 'white'})

@dataclass(frozen=True)
class Scenario:
    name: str
    win_probability: float = .45
    risk_fraction: float = .005
    cost_r: float = .10
    activity_probability: float = .60
    loss_persistence: float | None = None
    floor: str = 'static'
    gap_probability_given_loss: float = 0.0
    gap_loss_r: float = 3.0


def wilson(k, n, z=1.959963984540054):
    p=k/n
    den=1+z*z/n
    centre=(p+z*z/(2*n))/den
    half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return (centre-half, centre+half)


def probability_run(n, loss_probability, k):
    # Probability of at least k consecutive losses in n independent trades.
    state=np.zeros(k);state[0]=1.
    for _ in range(n):
        nxt=np.zeros(k)
        nxt[0]=state.sum()*(1-loss_probability)
        nxt[1:]=state[:-1]*loss_probability
        state=nxt
    return float(1-state.sum())


def simulate(s, uniforms):
    u_activity, u_outcome, u_initial, u_gap = uniforms
    eq=np.full(N,100000.0)
    peak=eq.copy()
    maxdd=np.zeros(N)
    status=np.zeros(N,dtype=np.int8) # 0 unresolved, 1 target, 2 floor breach
    days=np.zeros(N,dtype=np.int16)
    trade_counts=np.zeros(N,dtype=np.int16)
    prev_loss=u_initial < (1-s.win_probability)
    # Stationary Markov next-trade loss probability preserves marginal win rate.
    if s.loss_persistence is not None:
        q_lw=(1-s.win_probability)*(1-s.loss_persistence)/s.win_probability
        assert 0 <= q_lw <= 1
    for d in range(HORIZON):
        active=(status==0)&(u_activity[d]<s.activity_probability)
        if s.loss_persistence is None:
            loss=u_outcome[d] >= s.win_probability
        else:
            loss=u_outcome[d] < np.where(prev_loss,s.loss_persistence,q_lw)
        prev_loss=np.where(active,loss,prev_loss)
        gap=loss&(u_gap[d]<s.gap_probability_given_loss)
        gross=np.where(loss,-1.,5/3)
        gross=np.where(gap,-s.gap_loss_r,gross)
        r=np.where(active,gross-s.cost_r,0.)
        eq*=1+s.risk_fraction*r
        trade_counts+=active
        peak=np.maximum(peak,eq)
        maxdd=np.maximum(maxdd,1-eq/peak)
        floor=92000. if s.floor=='static' else peak-8000.
        breach=(status==0)&(eq<=floor)
        passed=(status==0)&~breach&(eq>=108000.)
        status[breach]=2
        status[passed]=1
        days[breach|passed]=d+1
    passed=status==1;breached=status==2;unresolved=status==0
    assert passed.sum()+breached.sum()+unresolved.sum()==N
    ci=wilson(int(passed.sum()),N)
    return {**asdict(s), 'n_paths':N, 'horizon_sessions':HORIZON,
            'passed':int(passed.sum()),'breached':int(breached.sum()),'unresolved':int(unresolved.sum()),
            'pass_pct':100*passed.mean(),'breach_pct':100*breached.mean(),
            'unresolved_pct':100*unresolved.mean(),
            'pass_ci_low_pct':100*ci[0],'pass_ci_high_pct':100*ci[1],
            'median_days_if_pass':float(np.median(days[passed])) if passed.any() else None,
            'median_trades':float(np.median(trade_counts)),
            'dd95_pct':float(np.quantile(maxdd,.95))*100,
            'gross_expectancy_r':s.win_probability*(5/3)-(1-s.win_probability),
            'daily_intrabar_compliance':'NOT ESTIMATED'}


def save(fig,name):
    fig.savefig(FIG/f'{name}.png',dpi=190,bbox_inches='tight',pad_inches=.12)
    plt.close(fig)


def main():
    rng=np.random.default_rng(SEED)
    uniforms=(rng.random((HORIZON,N)),rng.random((HORIZON,N)),rng.random(N),rng.random((HORIZON,N)))
    grid=[simulate(Scenario(f'p{p:.0%}_f{f:.2%}',win_probability=p,risk_fraction=f),uniforms)
          for p in [.35,.40,.45,.50] for f in [.0025,.005,.0075]]
    stresses=[Scenario('Base: independent'),Scenario('Loss clustering',loss_persistence=.75),
              Scenario('Higher cost',cost_r=.20),Scenario('Trailing dollar floor',floor='trailing'),
              Scenario('Rare 3R loss',gap_probability_given_loss=.02),
              Scenario('Half as many signals',activity_probability=.30),
              Scenario('Combined adverse',loss_persistence=.75,cost_r=.20,
                       gap_probability_given_loss=.02,floor='trailing')]
    stress=[simulate(s,uniforms) for s in stresses]
    losing_runs=[{'losses':k,'fixed_block_probability':.55**k,
                 'at_least_one_run_in_100':probability_run(100,.55,k),
                 'dd_025':1-(1-.0025)**k,'dd_050':1-(1-.005)**k,
                 'dd_075':1-(1-.0075)**k} for k in [5,8,10,15,20]]
    # Deliberately constructed account marks; integer index is an illustration, not calendar history.
    toy=np.array([100,103,106,104,101,97,98,100,103,106,108,107,105,106,108,109,107,104,102,103,105.],float)*1000
    toy_peak=np.maximum.accumulate(toy);toy_dd=1-toy/toy_peak
    facts={'seed':SEED,'paths':N,'horizon_sessions':HORIZON,'win_gross_r':5/3,
           'loss_gross_r':-1,'base_cost_r':.1,
           'breakeven_p_no_cost':1/(1+5/3),'breakeven_p_cost_010':1.1/(1+5/3),
           'wilson_24_of_33':wilson(24,33),'zero_failure_1000_upper_one_sided_95':1-.05**(1/1000),
           'loss_streaks':losing_runs,'toy_equity':toy.tolist(), 'toy_max_dd_pct':100*float(toy_dd.max()),
           'paper2_consistency':{'claimed_return_pct':9350,'capital':25000,
                                 'wealth_implied_by_return':25000*(1+93.5),
                                 'claimed_wealth':6400000,
                                 'return_implied_by_wealth_pct':100*(6400000/25000-1)},
           'grid':grid,'stress':stress}
    (HERE/'illustrative_results.json').write_text(json.dumps(facts,indent=2)+'\n')
    pd.DataFrame(grid).to_csv(HERE/'illustrative_pass_grid.csv',index=False)
    pd.DataFrame(stress).to_csv(HERE/'illustrative_stress.csv',index=False)

    # 1: Geometric break-even, no empirical trade distribution implied.
    fig,ax=plt.subplots(figsize=(7.05,3.0))
    ps=np.linspace(.2,.75,200)
    for c,label,col in [(0,'No costs',GRAY),(.10,'Cost = 0.10R',TEAL),(.20,'Cost = 0.20R',CORAL)]:
        ax.plot(ps*100,ps*(5/3)-(1-ps)-c,label=label,color=col,lw=2)
    ax.axhline(0,color=NAVY,lw=.8)
    ax.set(xlabel='Assumed full-target win probability (%)',ylabel='Expected net R per trade')
    ax.legend(frameon=False,fontsize=8,loc='upper left');ax.grid(alpha=.15)
    save(fig,'expectancy')

    # 2: Original schematic long path in signal units, not price history.
    x=np.arange(18)
    y=np.array([5995,5997,5993,5998,5996,5999,6000,6000.5,6002,6003.5,6002.5,6006,6009.5,6008,6009,6010.5,6012,6011])
    fig,ax=plt.subplots(figsize=(7.05,3.0));ax.plot(x,y,color=TEAL,lw=2)
    ax.axvspan(0,5.9,color=TEAL,alpha=.10);ax.axvline(6,ls=':',color=GRAY)
    ax.axhline(6000,color=NAVY,ls='--',lw=1);ax.axhline(5992,color=NAVY,ls='--',lw=1)
    ax.hlines(5994.5,7,15,color=CORAL,label='Initial stop 5,994.50')
    ax.hlines(6010.5,7,15,color=GOLD,label='Target 6,010.50')
    ax.scatter([7],[6000.5],color=NAVY,zorder=5)
    ax.set(xticks=[0,6,7,12,17],xticklabels=['09:30','10:00','10:05','10:30','10:55'],ylabel='Illustrative futures price',xlabel='New York time; stylized line, not OHLC data')
    ax.legend(frameon=False,fontsize=7.5,loc='upper left');save(fig,'long_example')

    # 3: Non-transferability of measured opening-window results.
    fig,(ax,bx)=plt.subplots(1,2,figsize=(7.05,2.8),gridspec_kw={'wspace':.32})
    labels=['5m','15m','30m','60m']
    ax.bar(labels,[2.81,1.43,.21,.40],color=[TEAL,TEAL,CORAL,GRAY]);ax.set(ylabel='Reported Sharpe',title='Risk-adjusted return')
    bx.bar(labels,[12,11,35,21],color=[TEAL,TEAL,CORAL,GRAY]);bx.set(ylabel='Reported maximum drawdown (%)',title='Drawdown depth')
    save(fig,'paper_timeframes')

    # 4: Same total trade outcomes, different DD paths.
    fig,(ax,bx)=plt.subplots(2,1,figsize=(7.05,3.5),sharex=True,gridspec_kw={'height_ratios':[1.3,1],'hspace':.14})
    ax.plot(np.arange(len(toy)),toy/1000,color=TEAL,lw=2,label='Constructed equity')
    ax.step(np.arange(len(toy)),toy_peak/1000,where='post',color=GOLD,lw=1.2,label='High-water mark')
    ax.set(ylabel='Equity ($000)');ax.legend(frameon=False,fontsize=8,ncol=2)
    bx.fill_between(np.arange(len(toy)), -100*toy_dd,0,color=CORAL,alpha=.65)
    bx.set(xlabel='Illustrative session index (not dates)',ylabel='Drawdown (%)');save(fig,'underwater')

    # 5: Fixed fractional risk arithmetic, costs excluded by definition.
    fig,ax=plt.subplots(figsize=(7.05,2.8));k=np.arange(0,31)
    for f,col in [(.0025,TEAL),(.005,GOLD),(.0075,CORAL)]:
        ax.plot(k,100*(1-(1-f)**k),label=f'{100*f:.2f}% risk',color=col,lw=2)
    ax.axhline(8,ls='--',color=NAVY,lw=1,label='Illustrative 8% loss threshold')
    ax.set(xlabel='Consecutive full 1R losses (no costs or gaps)',ylabel='Loss of starting equity (%)')
    ax.legend(frameon=False,fontsize=8);ax.grid(alpha=.15);save(fig,'losing_streaks')

    # 6: Toy challenge pass grid, not historical ORB estimates.
    vals=np.array([r['pass_pct'] for r in grid]).reshape(4,3)
    fig,ax=plt.subplots(figsize=(7.05,2.9));im=ax.imshow(vals,cmap='YlGnBu',vmin=0,vmax=100,aspect='auto')
    ax.set(xticks=np.arange(3),xticklabels=['0.25%','0.50%','0.75%'],yticks=np.arange(4),yticklabels=['35%','40%','45%','50%'],xlabel='Assumed equity risk per trade',ylabel='Assumed win probability')
    for i in range(4):
        for j in range(3):ax.text(j,i,f'{vals[i,j]:.1f}%',ha='center',va='center',color='white' if vals[i,j]>60 else NAVY,fontweight='bold')
    fig.colorbar(im,ax=ax,label='Model-only target-hit rate (%)');save(fig,'pass_grid')

    # 7: Stress joint target / breach / unresolved probabilities.
    fig,ax=plt.subplots(figsize=(7.05,3.15));labels=[s.name for s in stresses]
    p=np.array([x['pass_pct'] for x in stress]);b=np.array([x['breach_pct'] for x in stress]);u=100-p-b
    ax.barh(labels,p,color=TEAL,label='Target hit');ax.barh(labels,b,left=p,color=CORAL,label='Floor breach')
    ax.barh(labels,u,left=p+b,color='#d7dfe7',label='Unresolved')
    ax.invert_yaxis();ax.set(xlabel='20,000 assumed paths; outcome within 60 sessions (%)',xlim=(0,100))
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.2),ncol=3,frameon=False,fontsize=8);save(fig,'stress')

    # 8: Original visual for feasible trade risk.
    fig,ax=plt.subplots(figsize=(7.05,2.8));dd=np.linspace(0,7.9,100)
    cushion=8-dd
    ax.plot(dd,np.minimum(.5,.10*cushion),color=TEAL,lw=2,label='min(0.50%, 10% of remaining cushion)')
    ax.set(xlabel='Loss from initial equity (%)',ylabel='Illustrative risk ceiling (% of initial)')
    ax.set_ylim(0,.6);ax.legend(frameon=False,fontsize=7.8);ax.grid(alpha=.15);save(fig,'cushion')

    files=['optimize_strategy_1.py','quant_engine/strategies/prop_volatility_breakout.py',
           'quant_engine/core/portfolio.py','quant_engine/core/risk_manager.py',
           'quant_engine/core/data_manager.py','quant_engine/analytics/ssrn_validation.py',
           'quant_engine/analytics/performance_metrics.py']
    hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}
    (HERE/'audited_code_hashes.json').write_text(json.dumps({'date':'2026-09-08','files':hashes},indent=2)+'\n')
    print(pd.DataFrame(grid)[['win_probability','risk_fraction','pass_pct','breach_pct','unresolved_pct']].to_string(index=False))
    print(pd.DataFrame(stress)[['name','pass_pct','breach_pct','unresolved_pct','median_days_if_pass','dd95_pct']].to_string(index=False))
    print('Wilson 24/33:',facts['wilson_24_of_33'])
    print('Loss runs:',losing_runs)

if __name__=='__main__':main()
