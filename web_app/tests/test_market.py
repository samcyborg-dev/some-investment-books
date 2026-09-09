"""Data-integrity and causal-execution tests. Constructed fixtures are NOT evidence."""
import copy
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
import pytest
import requests
from fastapi.testclient import TestClient
from web_app.app import create_app
from web_app.market_data import MarketStore,normalize,parse_yahoo,parse_bar_csv,digest,yahoo_url
from web_app.orb_backtest import Indicators,BacktestParams,default_params,prospective_signal,resolve_exit,run_backtest

NOW=datetime(2026,9,8,12,tzinfo=timezone.utc)
START=int(datetime(2026,8,31,13,30,tzinfo=timezone.utc).timestamp())


def fixture_rows(days=5):
    # A deliberately constructed, uninterrupted uptrend ONLY for software tests.
    out=[]
    for d in range(days):
        for i in range(78):
            op=100+(d*78+i)*.25
            out.append(dict(timestamp=START+d*86400+i*300,open=op,high=op+.5,low=op-.25,close=op+.25,volume=10))
    return out


def fixture_data(days=5):
    return normalize(fixture_rows(days),'ES',{'origin':'SYNTHETIC_TEST_FIXTURE'},NOW)


def yahoo_fixture(rows=None,asset='ES=F'):
    rows=fixture_rows() if rows is None else rows
    return {'chart':{'error':None,'result':[{'meta':{'symbol':asset,'currency':'USD','instrumentType':'FUTURE','dataGranularity':'5m'},
        'timestamp':[r['timestamp'] for r in rows], 'indicators':{'quote':[{k:[r[k] for r in rows] for k in ['open','high','low','close','volume']}]}}]}}


def test_complete_calendar_and_dst():
    d=fixture_data()
    assert len(d['bars'])==390 and len(d['days'])==5
    assert d['quality']['missing_rth_bars']==0
    assert all(x['expected_bars']==78 and x['complete'] for x in d['days'])
    assert d['days'][0]['or_high']==max(x['high'] for x in fixture_rows()[:6])


def test_holiday_is_not_an_invented_missing_session():
    rows=fixture_rows()
    # Extend through 9/8 without inventing 9/7 Labor Day cash-session bars.
    rows.extend([{**r,'timestamp':r['timestamp']+8*86400} for r in fixture_rows(1)])
    d=normalize(rows,'ES',{'origin':'SYNTHETIC_TEST_FIXTURE'},datetime(2026,9,9,tzinfo=timezone.utc))
    assert '2026-09-07' not in [x['date'] for x in d['days']]
    assert len(d['days'])==6


def test_no_fill_or_interpolation():
    rows=fixture_rows();missing=rows.pop(20)['timestamp'];d=normalize(rows,'ES',{},NOW)
    assert missing not in [r['timestamp'] for r in d['bars']]
    assert d['quality']['missing_rth_bars']==1
    assert d['days'][0]['complete'] is False


def test_invalid_prices_exclude_the_session():
    rows=fixture_rows();rows[20]['high']=1;d=normalize(rows,'ES',{},NOW)
    assert d['quality']['invalid_prices']==1 and not d['days'][0]['complete']


def test_futures_tick_validation():
    rows=fixture_rows();rows[10]['close']+=.01;d=normalize(rows,'ES',{},NOW)
    assert d['quality']['invalid_tick']==1


def test_duplicate_policies():
    rows=fixture_rows();d=normalize(rows+[dict(rows[0])],'ES',{},NOW)
    assert len(d['bars'])==390 and d['quality']['identical_duplicates']==1
    bad={**rows[0],'close':rows[0]['close']-.25}
    d=normalize(rows+[bad],'ES',{},NOW)
    assert d['quality']['conflicting_duplicates']==1 and not d['days'][0]['complete']


def test_volume_warnings_are_not_fabricated_replacements():
    rows=fixture_rows();rows[0]['volume']=0;rows[1]['volume']=None
    d=normalize(rows,'ES',{},NOW)
    assert d['bars'][0]['volume']==0 and d['bars'][1]['volume'] is None
    assert d['quality']['zero_volume']==1 and d['quality']['missing_volume']==1


def test_unfinished_bars_do_not_enter_backtest():
    d=normalize(fixture_rows(1),'ES',{},datetime.fromtimestamp(START+600,timezone.utc))
    assert len(d['bars'])==2 and d['days'][0]['complete'] is False
    assert run_backtest(d,default_params('ES'))['metrics']['trades']==0


def test_only_native_5m_correct_symbol():
    p=yahoo_fixture();rows,_=parse_yahoo(p,'ES');assert len(rows)==390
    with pytest.raises(ValueError,match='symbol'):parse_yahoo(p,'MES')
    p['chart']['result'][0]['meta']['dataGranularity']='1h'
    with pytest.raises(ValueError,match='five-minute'):parse_yahoo(p,'ES')


def test_misaligned_columns_rejected():
    p=yahoo_fixture();p['chart']['result'][0]['timestamp'].pop()
    with pytest.raises(ValueError,match='lengths'):parse_yahoo(p,'ES')


def test_csv_requires_offsets_and_correct_schema():
    with pytest.raises(ValueError,match='offset'):parse_bar_csv('timestamp,open,high,low,close,volume\n2026-09-01T09:30:00,100,101,99,100,5','ES')
    with pytest.raises(ValueError,match='timestamp'):parse_bar_csv('entry_time,exit_time,fees\nx,y,5','ES')


def test_wilder_and_past_only_indicators():
    ind=Indicators()
    for _ in range(13):ind.update(dict(high=11,low=9,close=10))
    assert ind.atr is None
    ind.update(dict(high=11,low=9,close=10));assert ind.atr==2
    ind.update(dict(high=14,low=10,close=12));assert ind.atr==pytest.approx((13*2+4)/14)
    assert prospective_signal(ind,15,9,.25)[1]=='warmup'


def test_prospective_entry_and_already_crossed():
    i=Indicators();i.n=250;i.atr=2;i.ema20=100;i.ema50=99;i.prev_close=101
    assert prospective_signal(i,102,100,.25)[0]==(1,102.25,2)
    i.prev_close=103;assert prospective_signal(i,102,100,.25)[1]=='already_crossed'


def test_stops_before_targets_and_gap_slippage():
    pos=dict(direction=1,stop=99,target=102)
    price,reason,amb=resolve_exit(pos,dict(open=100,high=103,low=98),.25,.25)
    assert (price,reason,amb)==(98.75,'STOP',True)
    price,reason,_=resolve_exit(pos,dict(open=98,high=103,low=97),.25,.25)
    assert (price,reason)==(97.75,'GAP_STOP')


def test_entry_bar_is_protected_and_flagged():
    p=dict(direction=1,stop=99,target=102)
    price,reason,amb=resolve_exit(p,dict(open=98,high=101,low=98),.25,.25,new_entry=True)
    assert (price,reason,amb)==(98.75,'STOP',True)


def test_limit_requires_trade_through():
    p=dict(direction=1,stop=99,target=102)
    assert resolve_exit(p,dict(open=100,high=102,low=100),.25,.25)[0] is None
    assert resolve_exit(p,dict(open=100,high=102.25,low=100),.25,.25)[0]==102


def test_warmup_zero_trade_metrics_are_unknown():
    r=run_backtest(fixture_data(3),default_params('ES'))
    assert r['metrics']['trades']==0
    assert r['metrics']['win_rate'] is None and r['metrics']['profit_factor'] is None
    assert r['metrics']['sharpe_diagnostic'] is None


def test_cash_reconciliation_integer_units_and_one_fill_per_day():
    data=fixture_data();before=digest(data)
    r=run_backtest(data,default_params('ES'))
    assert r['metrics']['trades']>0
    assert all(isinstance(t['quantity'],int) and t['quantity']>=1 for t in r['trades'])
    assert len({t['date'] for t in r['trades']})==len(r['trades'])
    assert r['metrics']['ending_equity']==pytest.approx(100000+sum(t['net_pnl'] for t in r['trades']))
    assert r['metrics']['fees']==pytest.approx(sum(t['fees'] for t in r['trades']))
    assert all(t['signal_bar']<t['entry_bar']<=t['exit_bar'] for t in r['trades'])
    assert all(s['information_through']<=s['armed_at'] and s['completed_bars']>=250 for s in r['signal_audit'])
    assert digest(data)==before,'backtesting may not mutate source bars or hashes'


def test_future_prices_do_not_change_past_fills():
    data=fixture_data();p=default_params('ES');r=run_backtest(data,p)
    cutoff=r['trades'][0]['exit_bar']+300
    changed=copy.deepcopy(data)
    for b in changed['bars']:
        if b['timestamp']>cutoff:
            for k in ['open','high','low','close']:b[k]+=500
    changed['quality']['clean_sha256']=digest(changed['bars'])
    rr=run_backtest(changed,p)
    assert rr['trades'][0]==r['trades'][0]


def test_unauthorized_asset_proxy_is_rejected():
    with pytest.raises(ValueError,match='mismatch'):run_backtest(fixture_data(),default_params('MES'))


def test_checksum_blocks_corrupted_bars(tmp_path):
    s=MarketStore(tmp_path);s.save('ES',fixture_rows(),{})
    path=tmp_path/'ES-snapshot.json';j=json.loads(path.read_text());j['bars'][0]['close']+=1;path.write_text(json.dumps(j))
    with pytest.raises(ValueError,match='checksum'):s.read('ES')


def test_transport_failure_is_truthful_and_keeps_prices(tmp_path):
    s=MarketStore(tmp_path);d=s.save('ES',fixture_rows(),{})
    with patch('web_app.market_data.requests.get',side_effect=requests.exceptions.SSLError('test transport failure')) as get:
        result=s.refresh('ES')
        assert result['connected'] is False and 'TLS' in result['error']
        assert s.read('ES')['quality']['clean_sha256']==d['quality']['clean_sha256']
        assert s.refresh('ES')['cooldown'] is True and get.call_count==1


def test_failed_import_does_not_overwrite(tmp_path):
    s=MarketStore(tmp_path);s.save('ES',fixture_rows(),{});before=(tmp_path/'ES-snapshot.json').read_bytes()
    with pytest.raises(ValueError):s.import_text('ES',json.dumps(yahoo_fixture(asset='MES=F')))
    assert (tmp_path/'ES-snapshot.json').read_bytes()==before


def test_yahoo_url_is_fixed_host_and_5m():
    url=yahoo_url('ES',59,NOW)
    assert url.startswith('https://query1.finance.yahoo.com/v8/finance/chart/ES%3DF?')
    assert 'interval=5m' in url and 'period1=' in url


def test_market_api_import_backtest_and_missing_asset(tmp_path):
    app=create_app(tmp_path/'notes.json',tmp_path/'prices')
    with TestClient(app) as c:
        assert c.get('/api/orb/market/overview?asset=MES').json()['dataset'] is None
        r=c.post('/api/orb/market/import',json={'asset':'ES','text':json.dumps(yahoo_fixture())})
        assert r.status_code==200
        data=r.json();assert data['dataset']['provenance']['origin']=='USER_UPLOAD'
        assert data['dataset']['is_live'] is False
        assert c.post('/api/orb/market/backtest',json=default_params('ES').model_dump()).status_code==200
        assert c.post('/api/orb/market/backtest',json=default_params('MES').model_dump()).status_code==422
        assert c.post('/api/orb/market/backtest',json={'asset':'ES','risk_pct':100}).status_code==422
        assert c.get('/api/orb/market/overview?asset=../../etc/passwd').status_code==422


def test_browser_capture_if_present():
    path=Path(__file__).resolve().parents[2]/'data/market/es-browser-capture.json'
    if not path.exists():pytest.skip('Private vendor snapshot is intentionally excluded from Git.')
    capture=json.loads(path.read_text())
    assert len(capture['sessions'])==5
    for s in capture['sessions']:
        assert all(len(s[k])==79 for k in ['open','high','low','close','volume'])
        assert all(s[k][-1] is None for k in ['open','high','low','close','volume'])
        assert s['volume'][0]==0  # Retained vendor issue, not fabricated corrections.
