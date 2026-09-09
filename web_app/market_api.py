"""Read-only price research and private snapshot import endpoints."""
import json
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,HTTPException,Query
from fastapi.responses import Response
from pydantic import BaseModel,Field,ConfigDict
from web_app.market_data import ASSETS,MarketStore,yahoo_url
from web_app.orb_backtest import BacktestParams,default_params,run_backtest

Asset=Literal['ES','MES','SPY','QQQ']

class ImportBars(BaseModel):
    model_config=ConfigDict(extra='forbid')
    asset:Asset='ES'
    text:str=Field(min_length=1,max_length=4000000)

class RefreshBars(BaseModel):
    model_config=ConfigDict(extra='forbid')
    asset:Asset='ES'
    days:int=Field(59,ge=5,le=59)


def market_router(root=None):
    router=APIRouter(prefix='/api/orb/market',tags=['Market data research'])
    store=MarketStore(root)
    store.seed_browser_capture()
    def payload(asset):
        data=store.read(asset)
        latest_path=store.root/'github-latest-results.json'
        latest=None
        if latest_path.exists():
            try:latest=json.loads(latest_path.read_text(encoding='utf-8'))
            except (OSError,ValueError):latest=None
        return dict(assets=ASSETS,asset=asset,dataset=data,backtest=run_backtest(data,default_params(asset)) if data else None,
                    github_results=latest,
                    connection=store.connection(asset),download_url=yahoo_url(asset),
                    yahoo_quote_url='https://finance.yahoo.com/quote/'+ASSETS[asset]['symbol']+'/',
                    delay_note='Yahoo lists CME at 10 minutes; this is not an exchange-direct real-time feed.',
                    terms_url='https://help.yahoo.com/kb/finance-for-web/exchanges-data-providers-yahoo-finance-sln2310.html',
                    retention_note='Request at most 59 recent calendar days of five-minute data, below the documented 60-day intraday limit. Actual coverage is checked, not assumed.')

    @router.get('/overview')
    def overview(asset:Asset='ES'):
        try:return payload(asset)
        except (ValueError,KeyError) as e:raise HTTPException(422,str(e)) from e

    @router.post('/refresh')
    def refresh(req:RefreshBars):
        try:
            connection=store.refresh(req.asset,req.days)
            return dict(connection=connection,retained_existing=not connection['connected'])
        except ValueError as e:raise HTTPException(422,str(e)) from e

    @router.post('/import')
    def import_bars(req:ImportBars):
        try:
            store.import_text(req.asset,req.text)
            return payload(req.asset)
        except (ValueError,KeyError,TypeError) as e:raise HTTPException(422,str(e)[:500]) from e

    @router.post('/backtest')
    def backtest(req:BacktestParams):
        try:
            data=store.read(req.asset)
            if data is None:raise ValueError('Load actual '+req.asset+' prices first. No proxy or synthetic substitute will be used.')
            return run_backtest(data,req)
        except (ValueError,KeyError) as e:raise HTTPException(422,str(e)) from e

    @router.get('/csv-template')
    def template():
        return Response('timestamp,open,high,low,close,volume\n',media_type='text/csv',
                        headers={'Content-Disposition':'attachment; filename="orb-price-bars-template.csv"'})

    return router
