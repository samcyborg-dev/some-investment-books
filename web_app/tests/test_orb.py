"""ORB dashboard checks: provenance, exact scenario totals, accounting, and API behavior."""
from pathlib import Path
import csv
import io
import json
import math

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from web_app.app import create_app
from web_app.orb_service import (SimulationInput, SizingInput, LedgerInput, simulate,
                                 position_size, analyze_ledger, ledger_template, session_plan)
from datetime import date

ROOT=Path(__file__).resolve().parents[2]
SAVED=json.loads((ROOT/'research/strategy_1/illustrative_results.json').read_text())


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'notes.json')) as c:
        yield c


def test_health_and_same_origin_assets(client):
    assert client.get('/api/orb/health').json()['broker_connection'] is False
    for path,mime in [('/','text/html'),('/static/orb.js','javascript'),('/static/orb.css','text/css'),
                      ('/static/fonts/inter-latin-variable.woff2','font/woff2')]:
        r=client.get(path)
        assert r.status_code==200
        assert mime in r.headers['content-type']
        assert 'X-Frame-Options' not in r.headers
    html=client.get('/').text
    assert 'cdn.' not in html and 'localhost' not in html
    assert 'frame-ancestors *' in client.get('/').headers['content-security-policy']
    assert client.get('/',headers={'host':'8000-example.e2b.app'}).status_code==200


def test_bootstrap_separates_evidence(client):
    data=client.get('/api/orb/bootstrap').json()
    assert len(data['registry']['sources'])==15
    assert len(data['published'])==7
    assert data['base']['evidence']=='ILLUSTRATIVE'
    assert all(value is None for value in data['actual_performance'].values())
    assert data['base']['metrics']['passed']==2073
    assert data['published'][2]['sharpe']==.21
    assert data['published'][2]['mdd']==35
    assert data['published'][3]['annual_label']=='Yearly Return'
    assert data['published'][3]['annual']==33
    assert client.post('/api/backtest').status_code==410


@pytest.mark.parametrize('row',SAVED['grid'])
def test_all_grid_cells_match_saved_research(row):
    r=simulate(SimulationInput(win_rate=row['win_probability']*100,risk_pct=row['risk_fraction']*100))
    for k in ['passed','breached','unresolved','median_days_if_pass']:
        assert r['metrics'][k]==row[k]
    assert r['metrics']['dd95_pct']==pytest.approx(row['dd95_pct'])
    assert sum(b['count'] for b in r['histogram'])==20_000
    assert len(r['paths'])==61
    assert r['paths'][0]['median']==100_000


@pytest.mark.parametrize('row',SAVED['stress'])
def test_stress_scenarios_match_dossier(row):
    r=simulate(SimulationInput(cost_r=row['cost_r'],activity_pct=row['activity_probability']*100,
                              floor=row['floor'],loss_persistence=row['loss_persistence'],
                              gap_probability_pct=row['gap_probability_given_loss']*100))
    for k in ['passed','breached','unresolved']:
        assert r['metrics'][k]==row[k]


def test_expectancy_and_censoring():
    r=simulate(SimulationInput())
    m=r['metrics']
    assert m['net_expectancy_r']==pytest.approx(.10)
    assert m['breakeven_pct']==pytest.approx(41.25)
    assert m['net_win_r']==pytest.approx(5/3-.1)
    assert m['median_days_if_pass']==46
    assert any('censored' in x for x in r['limitations'])
    for point in r['paths']:
        assert point['low']<=point['median']<=point['high']
        assert point['dd_low']<=point['dd_median']<=point['dd_high']


def test_gaps_are_included_in_expected_loss():
    r=simulate(SimulationInput(gap_probability_pct=2))
    assert r['metrics']['net_expectancy_r']==pytest.approx(.45*(5/3)-.55*(.98+.02*3)-.1)


def test_parameters_really_change_the_model():
    base=simulate(SimulationInput())
    changed=simulate(SimulationInput(win_rate=50,risk_pct=.75,sessions=90,target_atr=2.5))
    assert len(changed['paths'])==91
    assert changed['params']['sessions']==90
    assert changed['metrics']['passed']!=base['metrics']['passed']
    assert changed['metrics']['net_expectancy_r']==pytest.approx(.5*(2.5/1.2)-.5-.1)


@pytest.mark.parametrize('bad',[{'win_rate':95},{'sessions':500},{'risk_pct':-1},{'cost_r':float('inf')},
                                {'loss_persistence':0,'win_rate':25},{'unknown':1}])
def test_scenario_validation(bad):
    with pytest.raises(ValidationError):SimulationInput(**bad)


def test_sizing_exact_contracts():
    mes=position_size(SizingInput())
    es=position_size(SizingInput(instrument='ES',fees=5))
    assert (mes['contracts'],mes['budget_used'])==(14,483)
    assert (es['contracts'],es['budget_used'])==(1,330)
    assert position_size(SizingInput(budget=20))['contracts']==0
    assert position_size(SizingInput(atr=5.01))['stop_points']==6.25
    assert mes['budget_used']+mes['unused']==500


def test_nairobi_dst_and_weekend():
    assert session_plan(date(2026,9,8))['events'][0]['nairobi']=='16:30'
    assert session_plan(date(2026,12,8))['events'][0]['nairobi']=='17:30'
    assert session_plan(date(2026,9,12))['weekend'] is True


def test_ledger_accounting():
    r=analyze_ledger(LedgerInput(csv_text=ledger_template(True),example=True))
    m=r['metrics']
    assert m['count']==6
    assert m['net_pnl']==1030
    assert m['fees']==45
    assert m['wins']==4 and m['losses']==2
    assert m['profit_factor']==pytest.approx(1665/635)
    assert m['ending_equity']==100_000+sum(t['net_pnl'] for t in r['trades'])
    assert r['trades'][0]['net_pnl']==495
    assert r['trades'][1]['r_multiple']==-1.1
    assert r['trades'][2]['net_pnl']==495
    assert r['evidence']=='ILLUSTRATIVE'
    user=analyze_ledger(LedgerInput(csv_text=ledger_template(True)))
    assert user['evidence']=='USER-SUPPLIED'
    assert 'sharpe' not in user['metrics']


def modified_csv(column,value):
    rows=list(csv.DictReader(io.StringIO(ledger_template(True))))
    rows[0][column]=value
    s=io.StringIO();w=csv.DictWriter(s,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    return s.getvalue()


@pytest.mark.parametrize('column,value',[
    ('quantity','.2'),('quantity','nan'),('entry_price','6000.10'),('entry_price','1e308'),
    ('initial_risk_usd','0'),('initial_risk_usd','1e-323'),('fees','-5'),('fees','Infinity'),
    ('entry_time','2026-08-17T10:05:00'),('exit_time','2026-08-16T10:05:00-04:00'),
    ('symbol','BTC'),('side','BUY'),
])
def test_bad_ledger_data_rejected(column,value):
    with pytest.raises(ValueError):analyze_ledger(LedgerInput(csv_text=modified_csv(column,value)))


def test_duplicate_and_missing_ledger_data():
    sample=ledger_template(True)
    with pytest.raises(ValueError,match='duplicate'):
        analyze_ledger(LedgerInput(csv_text=sample+sample.splitlines()[1]+'\n'))
    with pytest.raises(ValueError,match='Missing columns'):
        analyze_ledger(LedgerInput(csv_text='a,b\n1,2'))
    with pytest.raises(ValueError,match='No trades'):
        analyze_ledger(LedgerInput(csv_text=ledger_template(False)))


def test_no_losses_profit_factor_is_unknown():
    lines=ledger_template(True).splitlines()
    r=analyze_ledger(LedgerInput(csv_text='\n'.join(lines[:2])))
    assert r['metrics']['profit_factor'] is None
    assert r['metrics']['max_closing_dd_pct']==0
    assert r['episodes']==[]


def test_unrecovered_drawdown_is_retained():
    lines=ledger_template(True).splitlines()
    r=analyze_ledger(LedgerInput(csv_text='\n'.join(lines[:3])))
    assert r['episodes'][-1]['recovery'] is None
    assert r['episodes'][-1]['duration']==1


def test_notes_persist_and_delete(tmp_path):
    path=tmp_path/'notes.json'
    with TestClient(create_app(path)) as c:
        assert c.get('/api/orb/journal').json()['entries']==[]
        note={'title':'Check fills','body':'<script>Not executable prose</script>','category':'Execution','session_date':'2026-09-08'}
        r=c.post('/api/orb/journal',json=note)
        assert r.status_code==201
        ident=r.json()['id']
    with TestClient(create_app(path)) as c:
        assert c.get('/api/orb/journal').json()['entries'][0]['title']=='Check fills'
        assert c.delete('/api/orb/journal/'+ident).status_code==204
        assert c.get('/api/orb/journal').json()['entries']==[]
        assert c.delete('/api/orb/journal/'+ident).status_code==404
        assert c.post('/api/orb/journal',json={**note,'title':'   '}).status_code==422


def test_corrupt_journal_is_not_overwritten(tmp_path):
    path=tmp_path/'notes.json';path.write_text('{invalid')
    with TestClient(create_app(path)) as c:
        assert c.get('/api/orb/journal').status_code==503
        assert c.post('/api/orb/journal',json={'title':'x','body':'y','category':'Research','session_date':'2026-09-08'}).status_code==503
    assert path.read_text()=='{invalid'


def test_report_and_safe_downloads(client):
    data=client.get('/api/orb/report').json()
    assert len(data['sections'])==49
    assert '{{TOC}}' not in str(data)
    assert '<script' not in str(data)
    assert '/api/orb/figure/' in str(data)
    for name,signature in [('dossier.pdf',b'%PDF-'),('grid.csv',b'name,'),('stress.csv',b'name,')]:
        r=client.get('/api/orb/download/'+name)
        assert r.status_code==200 and r.content.startswith(signature)
        assert 'attachment' in r.headers['content-disposition']
    assert client.get('/api/orb/download/../../.git/config').status_code!=200
    assert client.get('/api/orb/figure/not-a-figure.png').status_code==404
    assert client.get('/api/orb/figure/underwater.png').content.startswith(b'\x89PNG\r\n\x1a\n')


def test_failed_import_has_no_partial_results(client):
    r=client.post('/api/orb/ledger',json={'csv_text':'a,b\n1,2'})
    assert r.status_code==422 and 'trades' not in r.json()
    assert client.post('/api/orb/simulate',json={'sessions':999}).status_code==422
