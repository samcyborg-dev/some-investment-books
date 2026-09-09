"""Editorial content distilled from the saved Strategy 1 dossier, not new research."""

METRICS = [
    dict(id='expectancy',name='Net expectancy',group='Trade model',formula='p × average winning R − (1 − p) × average losing R − costs',description='Expected net payoff per trade under the stated distribution. In the scenario lab, probabilities and payoffs are assumptions, not estimates of an ES edge.'),
    dict(id='target',name='Target-hit rate',group='Scenario model',formula='Paths reaching the target first ÷ all simulated paths',description='A finite-horizon model outcome. Includes all paths in the denominator, not only resolved accounts. Not a calibrated firm pass probability.'),
    dict(id='breach',name='Floor-breach rate',group='Scenario model',formula='Paths reaching the loss floor first ÷ all simulated paths',description='Closed-trade floor detection only. Intrabar losses, firm-specific daily resets and actual execution are not represented.'),
    dict(id='unresolved',name='Unresolved rate',group='Scenario model',formula='Paths at neither boundary by the horizon ÷ all paths',description='Unresolved does not mean breached. Slow progress and a terminated account are different outcomes.'),
    dict(id='dd95',name='95th-percentile drawdown',group='Scenario model',formula='95th percentile of each stopped path’s maximum closing-equity drawdown',description='A percentile across simulated accounts, not a worst-case limit. Stopping at target or floor censors later losses. Intrabar drawdown is unknown.'),
    dict(id='breakeven',name='Break-even win rate',group='Trade model',formula='(Average gross loss + cost) ÷ (Gross win + average gross loss)',description='A two-outcome arithmetic threshold, not an estimated win rate. Trail and time exits change the payoff distribution.'),
    dict(id='payoff',name='Payoff ratio',group='Trade model',formula='Average net win ÷ magnitude of average net loss',description='A high reward-to-risk ratio can still lose money if wins are too infrequent. Costs and rare larger losses matter.'),
    dict(id='pnl',name='Net P&L',group='Trade records',formula='Signed (exit − entry) × contracts × point value − all fees',description='Actual fills already incorporate slippage; do not deduct the same slippage twice. Imported records assume no deposits, withdrawals or unreported fees.'),
    dict(id='winrate',name='Trade win rate',group='Trade records',formula='Positive-net closed trades ÷ all closed trades',description='Includes scratches in the denominator. This is not a daily hit ratio. A simulated win probability is an input, not an observed strategy win rate.'),
    dict(id='pf',name='Profit factor',group='Trade records',formula='Sum of positive net P&L ÷ absolute sum of negative net P&L',description='Undefined when there are no losses; never substitute a dollar profit amount. A small selected sample is not evidence of stable profitability.'),
    dict(id='r',name='Initial-risk R',group='Trade records',formula='Net trade P&L ÷ initial price-risk dollars',description='Use the original risk denominator, not a smaller denominator after a trailing stop moves. Include all round-trip costs exactly once.'),
    dict(id='drawdown',name='Maximum drawdown',group='Account risk',formula='max(1 − equity ÷ preceding high-water mark)',description='Must specify equity sampling. Trade-close drawdown can miss open losses and cannot certify intraday rule compliance.'),
    dict(id='recovery',name='Drawdown recovery',group='Account risk',formula='Recovery gain needed = depth ÷ (1 − depth)',description='An 8% loss needs an 8.70% gain to recover. Unrecovered episodes are right-censored and must not be excluded from duration statistics.'),
    dict(id='sharpe',name='Sharpe ratio',group='Account risk',formula='√252 × mean daily excess return ÷ SD(daily excess return)',description='Requires a risk-free-rate convention, complete session calendar and dependence treatment. Not inferred from a sparse closed-trade CSV. Published values retain the author’s definition.'),
    dict(id='sortino',name='Sortino ratio',group='Account risk',formula='Annualized mean excess over MAR ÷ annualized downside deviation',description='Downside deviation uses min(return − MAR, 0) squared over ALL observations, not the SD of negative returns alone.'),
    dict(id='calmar',name='Calmar ratio',group='Account risk',formula='CAGR ÷ maximum drawdown over the same window',description='Sensitive to one extreme episode and the sample endpoint. Not available without an appropriate equity history.'),
    dict(id='cagr',name='CAGR',group='Account risk',formula='(Ending equity ÷ starting equity)^(1 ÷ years) − 1',description='Geometric growth absent external cash flows. Short-sample annualization is unstable. Do not silently equate it with a paper’s IRR or Yearly Return label.'),
    dict(id='mae',name='MAE / MFE',group='Trade records',formula='Largest adverse / favorable excursion AFTER actual entry',description='Requires the post-entry price path, not merely entry and exit fills. Pre-entry bar extremes must not be used.'),
    dict(id='dsr',name='Deflated Sharpe ratio',group='Inference',formula='PSR evaluated against a search-adjusted Sharpe threshold',description='Uses sample length, return moments, trial dispersion and effective independent trials. Not an SSRN certificate or challenge pass probability.'),
    dict(id='pbo',name='Probability of backtest overfitting',group='Inference',formula='Probability the in-sample winner ranks below the out-of-sample median',description='Evaluates a selection process under a specified resampling framework. No PBO value has been established for ORB-30R.'),
]

AUDIT = [
    dict(title='Same-bar future information',severity='Critical',file='prop_volatility_breakout.py:245–278',detail='A completed close approves an entry priced at an earlier range crossing. Use prospective stop orders or a separate next-price close-confirmed model.'),
    dict(title='Target-first intrabar ordering',severity='Critical',file='prop_volatility_breakout.py:158–216',detail='An OHLC bar can touch both barriers without revealing their order. Favorable-first processing biases results; use sequenced data or adverse-first bounds.'),
    dict(title='Missing entry-bar protection',severity='Critical',file='prop_volatility_breakout.py:245–300',detail='New entries are evaluated after the management block. Immediate fill-bar stops and targets can be missed.'),
    dict(title='Fractional ES/MES contracts',severity='Critical',file='prop_volatility_breakout.py:254,282',detail='Hundredth-contract quantities and a forced 0.2 minimum are not executable. Use integer floor sizing and skip unaffordable positions.'),
    dict(title='Risk surveillance only before entry',severity='Critical',file='check_pre_trade / strategy event loop',detail='A flat-account entry gate is not continuous floating-equity monitoring or emergency liquidation. A stop cannot guarantee the account floor.'),
    dict(title='Fees do not reconcile',severity='Critical',file='portfolio.py:135,184',detail='Entry fees leave cash but are omitted from reported trade net P&L. Reconcile cash, trades and both sides of execution costs.'),
    dict(title='Range timing and ATR warm-up',severity='Review',file='prop_volatility_breakout.py:93,130',detail='The range is hardcoded before 10:00 without a 09:30 lower bound. ATR uses a rolling mean and backfill rather than past-only Wilder warm-up.'),
    dict(title='No walk-forward validation',severity='Critical',file='optimize_strategy_1.py',detail='54 configurations share one synthetic 90-session sample. No chronological out-of-sample partitions or untouched holdout were used.'),
    dict(title='Incompatible simulation and statistics',severity='Review',file='ssrn_validation.py / performance_metrics.py',detail='The old simulator forces daily activity, assumes unsupported DSR trial inputs, and uses a nonstandard Sortino denominator. Those outputs are not exposed as valid dashboard results.'),
]

RULES = [
    ('Instrument','ES or MES','Actual contract-month prices; integer contracts and 0.25-point ticks.'),
    ('Opening range','09:30–10:00 ET','Six complete five-minute regular-session bars; freeze the high and low at 10:00.'),
    ('Trend filter','EMA 20 / 50','Long: completed close > EMA20 > EMA50. Short: the symmetric below condition.'),
    ('Volatility','Wilder ATR 14','Five-minute RTH bars, carried across sessions; at least 250 valid warm-up bars.'),
    ('Range gate','Width ≤ 5 × ATR','A proposed heuristic, not a threshold proven by the cited research.'),
    ('Entry','One tick beyond range','Arm prospectively for the next bar. Skip a price already crossed before the order can be sent.'),
    ('Initial bracket','1.2 ATR / 2.0 ATR','Freeze ATR at arming, set the bracket from actual fill, tick-round and recheck risk.'),
    ('Trailing experiment','Activate 1.8 ATR · trail 1 ATR','Separate on/off experiment. Use post-entry extremes prospectively; never loosen the stop.'),
    ('Trade limit','One fill per session','Total across long and short. No pyramiding; cancel unfilled entries at 13:30 ET.'),
    ('Flat deadline','15:50 ET','Earlier on shortened sessions. Confirm actual flatness, not simply a chart timestamp.'),
]

VALIDATION = [
    dict(title='Research & causal specification',status='Documented',done=True,detail='49-page dossier and ORB-30R v0.1 specification.'),
    dict(title='Historical market data',status='Not connected',done=False,detail='No licensed ES/MES price history acquired for a validated test.'),
    dict(title='Execution engine repairs',status='Blocked',done=False,detail='Timing, fills, fees and continuous risk checks need correction.'),
    dict(title='Out-of-sample validation',status='Not run',done=False,detail='Freeze a chronological test and account for the complete search.'),
    dict(title='Forward / paper execution',status='No records',done=False,detail='Measure real order acknowledgments, slippage and reconciliation.'),
]
