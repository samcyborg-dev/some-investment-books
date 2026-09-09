"""ORB research dashboard: one same-origin, self-contained FastAPI application.

Run: python3 -m uvicorn web_app.app:app --host 0.0.0.0 --port 8000
The superseded multi-strategy prototype is preserved in legacy_app.py, not imported.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock, BoundedSemaphore
from typing import Literal
from uuid import uuid4

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field
from web_app.orb_service import SimulationInput, SizingInput, LedgerInput, simulate, position_size, analyze_ledger, ledger_template, session_plan
from web_app.orb_content import METRICS, AUDIT, RULES, VALIDATION
from web_app.market_api import market_router

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESEARCH = ROOT/'research'/'strategy_1'
LIMITER = BoundedSemaphore(2)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def model_result(params):
    if not LIMITER.acquire(timeout=2):
        raise HTTPException(429,'Two scenarios are already running. Please try again shortly.')
    try:
        return simulate(params)
    finally:
        LIMITER.release()


class NoteInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)
    category: Literal['Research','Execution','Risk','Review'] = 'Research'
    session_date: date


class JournalStore:
    def __init__(self, path):
        self.path = path
        self.lock = Lock()

    def read(self):
        if not self.path.exists():
            return []
        try:
            data = read_json(self.path)
            if not isinstance(data,list) or len(data)>200:
                raise ValueError('Invalid journal')
            for item in data:
                if not isinstance(item,dict) or not re.fullmatch(r'[a-f0-9]{32}',str(item.get('id',''))):
                    raise ValueError('Invalid note record')
                NoteInput.model_validate({k:item[k] for k in ('title','body','category','session_date')})
            return data
        except (ValueError,KeyError,OSError):
            raise HTTPException(503,'Journal unavailable. Existing notes have not been replaced.')

    def write(self, entries):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        temp.replace(self.path)

    def add(self,note):
        with self.lock:
            data = self.read()
            if len(data)>=200:
                raise HTTPException(409,'The journal is limited to 200 notes. Export and remove older notes first.')
            item = dict(id=uuid4().hex,**note.model_dump(mode='json'),created_at=datetime.now(timezone.utc).isoformat())
            data.insert(0,item)
            self.write(data)
            return item

    def delete(self, ident):
        with self.lock:
            data = self.read()
            remaining = [n for n in data if n['id'] != ident]
            if len(remaining)==len(data):
                raise HTTPException(404,'Note not found.')
            self.write(remaining)


def published_rows(sources):
    s1,s2,s3 = (sources[i]['facts'] for i in range(3))
    rows = []
    for key,label in [('base','Base 5-minute ORB'),('selected_5m','Stocks in Play · 5-minute')]:
        x=s1[key]
        rows.append(dict(name=label,instrument='US stocks',family='Fixed-range ORB',annual=x['irr_pct'],annual_label='IRR',sharpe=x['sharpe_reported'],mdd=x['mdd_pct'],source=1,sample='2016–2023'))
    x=s1['timeframes'][2]
    rows.append(dict(name='Stocks in Play · 30-minute',instrument='US stocks',family='Fixed-range ORB',annual=x['irr_pct'],annual_label='IRR',sharpe=x['sharpe_reported'],mdd=x['mdd_pct'],source=1,sample='2016–2023'))
    for key,label,asset in [('qqq_table2','Opening direction · QQQ','QQQ'),('tqqq_table2','Opening direction · TQQQ','TQQQ')]:
        x=s2[key]
        rows.append(dict(name=label,instrument=asset,family='Opening-direction entry',annual=x['yearly_return_reported_pct'],annual_label='Yearly Return',sharpe=x['sharpe_reported'],mdd=x['mdd_pct'],source=2,sample='2016–Feb 2023'))
    for key,label in [('unlevered_refined','Dynamic bands · unlevered'),('final_table3','Dynamic bands · scaled')]:
        x=s3[key]
        rows.append(dict(name=label,instrument='SPY',family='Intraday-band momentum',annual=x['irr_pct'],annual_label='IRR',sharpe=x['sharpe_reported'],mdd=x['mdd_pct'],source=3,sample='2007–Apr 2024'))
    return rows


def create_app(journal_path=None,market_path=None):
    app=FastAPI(title='Range Lab · ORB Research',version='1.1.0')
    app.include_router(market_router(market_path))
    store=JournalStore(Path(journal_path) if journal_path else RESEARCH/'dashboard_journal.json')
    app.state.journal=store
    app.mount('/static',StaticFiles(directory=HERE/'static'),name='static')

    @app.middleware('http')
    async def headers(request:Request,call_next):
        length=request.headers.get('content-length')
        if length:
            try:
                limit=5_000_000 if request.url.path=='/api/orb/market/import' else 1_100_000
                if int(length)>limit:
                    return JSONResponse({'detail':'Request too large for this endpoint.'},status_code=413)
            except ValueError:
                return JSONResponse({'detail':'Invalid content length.'},status_code=400)
        response=await call_next(request)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self' https://www.tradingview-widget.com https://s.tradingview.com https://www.tradingview.com; frame-ancestors *; base-uri 'self'; form-action 'self'"
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
        return response

    @app.get('/')
    @app.get('/orb')
    def index():
        return FileResponse(HERE/'templates'/'orb.html',media_type='text/html',headers={'Cache-Control':'no-cache'})

    @app.get('/favicon.svg')
    def favicon():
        return FileResponse(HERE/'static'/'orb-mark.svg',media_type='image/svg+xml')

    @app.get('/api/orb/health')
    def health():
        return {'status':'ok','mode':'research','market_feed':False,'broker_connection':False}

    @app.get('/api/orb/bootstrap')
    def bootstrap():
        registry=read_json(RESEARCH/'sources.json')
        return dict(as_of=registry['accessed'],registry=registry,saved=read_json(RESEARCH/'illustrative_results.json'),
                    base=model_result(SimulationInput()),published=published_rows(registry['sources']),
                    glossary=METRICS,audit=AUDIT,rules=RULES,validation=VALIDATION,
                    actual_performance={'win_rate':None,'expectancy_r':None,'sharpe':None,'max_drawdown':None,'pass_probability':None},
                    provenance={'model':'Uncalibrated educational model','source':'research/strategy_1/illustrative_results.json','seed':20260908,
                                'historical_backtest':'Not validated','broker':'Not connected','pine':'Not implemented'})

    @app.post('/api/orb/simulate')
    def run(params:SimulationInput):
        return model_result(params)

    @app.post('/api/orb/size')
    def size(params:SizingInput):
        return position_size(params)

    @app.get('/api/orb/session')
    def session(day:date=Query(date(2026,9,8))):
        return session_plan(day)

    @app.post('/api/orb/ledger')
    def ledger(params:LedgerInput):
        try:
            return analyze_ledger(params)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc

    @app.get('/api/orb/ledger-template')
    def template(sample:bool=False):
        return Response(ledger_template(sample),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="orb-{ "fictional-example" if sample else "trade-template"}.csv"'})

    @app.get('/api/orb/journal')
    def get_journal():
        return {'entries':store.read(),'note':'Research notes are saved in the workspace. These are not verified broker records.'}

    @app.post('/api/orb/journal',status_code=201)
    def add_note(note:NoteInput):
        return store.add(note)

    @app.delete('/api/orb/journal/{ident}',status_code=204)
    def delete_note(ident:str):
        store.delete(ident)
        return Response(status_code=204)

    @app.get('/api/orb/report')
    def report():
        md=MarkdownIt('commonmark',{'html':False}).enable('table')
        raw=(RESEARCH/'report.md').read_text(encoding='utf-8')
        parts=re.split(r'<!-- PAGE (.*?) -->',raw)
        sections=[]
        for i in range(1,len(parts),2):
            ident,category,title=[x.strip() for x in parts[i].split('|')]
            body=parts[i+1].replace('{{TOC}}','Use the chapter selector above to navigate the complete dossier.')
            body=re.sub(r':::formula\n(.*?)\n:::',r'```text\n\1\n```',body,flags=re.S)
            body=re.sub(r'\]\(figures/([^/]+\.png)\)',r'](/api/orb/figure/\1)',body)
            sections.append(dict(id=ident,category=category,title=title,number=len(sections)+1,html=md.render(body)))
        return {'sections':sections,'pages':49,'date':'2026-09-08'}

    @app.get('/api/orb/figure/{name}')
    def figure(name:str):
        allowed={p.name for p in (RESEARCH/'figures').glob('*.png')}
        if name not in allowed:
            raise HTTPException(404,'Figure not found.')
        return FileResponse(RESEARCH/'figures'/name,media_type='image/png')

    @app.get('/api/orb/download/{name}')
    def download(name:Literal['dossier.pdf','grid.csv','stress.csv','sources.json','manuscript.md']):
        files={
            'dossier.pdf':(ROOT/'STRATEGY_1_ORB_FORENSIC_RESEARCH.pdf','application/pdf'),
            'grid.csv':(RESEARCH/'illustrative_pass_grid.csv','text/csv'),
            'stress.csv':(RESEARCH/'illustrative_stress.csv','text/csv'),
            'sources.json':(RESEARCH/'sources.json','application/json'),
            'manuscript.md':(RESEARCH/'report.md','text/markdown'),
        }
        path,mime=files[name]
        if not path.is_file():
            raise HTTPException(404,'Research file not found.')
        return FileResponse(path,media_type=mime,filename=path.name)

    @app.post('/api/backtest',status_code=410)
    def retired_backtest():
        return {'detail':'The legacy synthetic backtester is not a valid ORB result source. Use the labeled scenario model or import trade records.'}

    return app


app=create_app()

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='0.0.0.0',port=8000)
