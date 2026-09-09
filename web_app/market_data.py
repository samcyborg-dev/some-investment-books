"""Private, provenance-aware market snapshots. Never generates replacement prices."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import exchange_calendars as xc
import requests

NY=ZoneInfo('America/New_York')
UTC=timezone.utc
VERSION='market-normalizer-1.0'
ROOT=Path(__file__).resolve().parents[1]
ASSETS={
 'ES':dict(symbol='ES=F',name='E-mini S&P 500',kind='futures',point_value=50.,tick=.25,fee=5.,max_units=1,tv='CME_MINI:ES1!',note='Vendor front-contract series; exact historical contract mapping and rolls are not independently verified.'),
 'MES':dict(symbol='MES=F',name='Micro E-mini S&P 500',kind='futures',point_value=5.,tick=.25,fee=2.,max_units=10,tv='CME_MINI:MES1!',note='A separate MES feed is required. ES candles are never silently substituted.'),
 'SPY':dict(symbol='SPY',name='SPDR S&P 500 ETF',kind='etf',point_value=1.,tick=.01,fee=.007,max_units=1000,tv='AMEX:SPY',note='Alternative research candidate, not a validated transfer. Integer shares; 1× cash buying-power cap; no short-borrow model.'),
 'QQQ':dict(symbol='QQQ',name='Invesco QQQ ETF',kind='etf',point_value=1.,tick=.01,fee=.007,max_units=1000,tv='NASDAQ:QQQ',note='Alternative research candidate. The cited QQQ paper uses different entry rules; this ORB needs its own test.'),
}


def utcnow():return datetime.now(UTC)
def encoded(data):return json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(data):return hashlib.sha256(encoded(data)).hexdigest()
def reject_constant(value):raise ValueError('Non-finite JSON value: '+value)
def finite(v):return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)


def yahoo_url(asset,days=59,now=None):
    now=now or utcnow()
    return f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(ASSETS[asset]["symbol"],safe="")}?period1={int((now-timedelta(days=days)).timestamp())}&period2={int(now.timestamp())}&interval=5m&includePrePost=true'


def parse_yahoo(payload,asset):
    chart=payload.get('chart',{})
    if chart.get('error'):raise ValueError('Yahoo reported: '+str(chart['error'].get('description','data unavailable'))[:200])
    results=chart.get('result') or []
    if len(results)!=1:raise ValueError('Expected one Yahoo chart result.')
    result=results[0];meta=result.get('meta',{})
    if meta.get('symbol')!=ASSETS[asset]['symbol']:raise ValueError('The source symbol does not match the selected asset. No ES/MES substitution is permitted.')
    if meta.get('dataGranularity')!='5m':raise ValueError('Only native five-minute bars are supported; daily/hourly data cannot reconstruct this ORB.')
    if meta.get('currency')!='USD':raise ValueError('This adapter currently requires USD prices.')
    expected_type='FUTURE' if ASSETS[asset]['kind']=='futures' else 'ETF'
    if meta.get('instrumentType')!=expected_type:raise ValueError('The vendor instrument type does not match the selected asset.')
    stamps=result.get('timestamp') or []
    quotes=result.get('indicators',{}).get('quote') or []
    if not stamps or len(stamps)>25000 or len(quotes)!=1:raise ValueError('Expected 1–25,000 source bars and one OHLCV block.')
    q=quotes[0]
    if any(len(q.get(k,[]))!=len(stamps) for k in ['open','high','low','close','volume']):
        raise ValueError('Timestamp and OHLCV column lengths differ; import rejected without partial writes.')
    return [dict(timestamp=t,**{k:q[k][i] for k in ['open','high','low','close','volume']}) for i,t in enumerate(stamps)],meta


def parse_bar_csv(text,asset):
    reader=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    required={'timestamp','open','high','low','close','volume'}
    if not reader.fieldnames or not required.issubset(reader.fieldnames) or len(set(reader.fieldnames))!=len(reader.fieldnames):
        raise ValueError('Bar CSV needs unique timestamp, open, high, low, close, volume columns. This is not the trade-ledger CSV format.')
    rows=[]
    for i,row in enumerate(reader,2):
        if i>25001:raise ValueError('Maximum 25,000 source bars.')
        try:
            if None in row:raise ValueError('extra CSV cells')
            dt=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
            if dt.utcoffset() is None:raise ValueError('timestamp needs an explicit UTC offset')
            if row.get('symbol') and row['symbol'] not in (asset,ASSETS[asset]['symbol']):raise ValueError('symbol mismatch')
            rows.append(dict(timestamp=int(dt.timestamp()),**{k:float(row[k]) if row[k].strip() else None for k in required-{'timestamp'}}))
        except (ValueError,TypeError,KeyError) as e:raise ValueError(f'CSV row {i}: {e}') from e
    return rows,dict(symbol=ASSETS[asset]['symbol'],shortName='User-declared '+asset,dataGranularity='5m',currency='USD')


def normalize(rows,asset,provenance,now=None):
    now=now or utcnow();now_ts=now.timestamp()
    if not rows:raise ValueError('No source bars.')
    if len(rows)>25000:raise ValueError('Maximum 25,000 source bars.')
    if any(not finite(r.get('timestamp')) or int(r['timestamp'])!=r['timestamp'] for r in rows):raise ValueError('Timestamps must be finite integer epoch seconds.')
    stamps=[int(r['timestamp']) for r in rows]
    try:
        first=datetime.fromtimestamp(min(stamps),UTC).astimezone(NY).date()
        last=datetime.fromtimestamp(max(stamps),UTC).astimezone(NY).date()
    except (ValueError,OverflowError,OSError) as e:raise ValueError('Invalid timestamp range.') from e
    if first.year<2000 or last>now.date()+timedelta(days=1) or (last-first).days>366:
        raise ValueError('Supported snapshots span at most 366 days, from year 2000 through the current date.')
    cal=xc.get_calendar('XNYS',start=str(first-timedelta(days=7)),end=str(last+timedelta(days=7)))
    schedule=cal.schedule.loc[str(first):str(last)]
    sessions={str(d.date()):dict(date=str(d.date()),open=int(s['open'].timestamp()),close=int(s['close'].timestamp()),bars={},invalid=False)
              for d,s in schedule.iterrows()}
    counts=dict(source_rows=len(rows),outside_rth=0,non_bar_updates=0,unfinished_bars=0,invalid_prices=0,invalid_tick=0,
                identical_duplicates=0,conflicting_duplicates=0,zero_volume=0,missing_volume=0,negative_volume=0,missing_rth_bars=0)
    issues=[];seen={};blacklist=set()
    for row in sorted(rows,key=lambda r:r['timestamp']):
        t=int(row['timestamp']);day=datetime.fromtimestamp(t,UTC).astimezone(NY).date().isoformat();s=sessions.get(day)
        if not s or not s['open']<=t<s['close']:
            counts['outside_rth']+=1;continue
        if t%300:
            counts['non_bar_updates']+=1;s['invalid']=True;continue
        if t+300>now_ts:
            counts['unfinished_bars']+=1;continue
        vals=[row.get(k) for k in ['open','high','low','close']]
        if not all(finite(v) and 0<v<10_000_000 for v in vals) or not vals[2]<=min(vals[0],vals[3])<=max(vals[0],vals[3])<=vals[1]:
            counts['invalid_prices']+=1;s['invalid']=True;issues.append(dict(date=day,timestamp=t,reason='invalid OHLC'));continue
        if ASSETS[asset]['kind']=='futures' and any(abs(v/.25-round(v/.25))>1e-6 for v in vals):
            counts['invalid_tick']+=1;s['invalid']=True;issues.append(dict(date=day,timestamp=t,reason='off-tick futures price'));continue
        v=row.get('volume')
        if not finite(v):counts['missing_volume']+=1;v=None
        elif v<0:counts['negative_volume']+=1;v=None
        elif v==0:counts['zero_volume']+=1
        clean=dict(timestamp=t,open=float(vals[0]),high=float(vals[1]),low=float(vals[2]),close=float(vals[3]),volume=v)
        if t in seen:
            if seen[t]==clean:counts['identical_duplicates']+=1
            else:
                counts['conflicting_duplicates']+=1;s['invalid']=True;blacklist.add(t);s['bars'].pop(t,None)
                issues.append(dict(date=day,timestamp=t,reason='conflicting duplicate'))
            continue
        seen[t]=clean
        if t not in blacklist:s['bars'][t]=clean
    day_rows=[];bars=[];warnings=[]
    for s in sessions.values():
        expected=list(range(s['open'],s['close'],300));missing=[t for t in expected if t not in s['bars'] and t+300<=now_ts]
        full=s['close']-s['open']==23400
        complete=not missing and not s['invalid'] and s['close']<=now_ts
        if s['close']>now_ts:status='In progress / not yet complete'
        elif s['invalid']:status='Rejected: invalid price/duplicate'
        elif missing:status='Rejected: missing bars'
        elif not full:status='Short session: no trading'
        else:status='Complete'
        counts['missing_rth_bars']+=len(missing)
        sbars=sorted(s['bars'].values(),key=lambda r:r['timestamp']);bars.extend(sbars)
        opening=[b for b in sbars if b['timestamp']<s['open']+1800]
        day_rows.append(dict(date=s['date'],open=s['open'],close=s['close'],expected_bars=len(expected),observed_bars=len(sbars),
                             missing_bars=len(missing),complete=complete,tradeable=complete and full,status=status,
                             or_high=max(b['high'] for b in opening) if len(opening)==6 else None,
                             or_low=min(b['low'] for b in opening) if len(opening)==6 else None))
    if counts['zero_volume']:warnings.append(f"{counts['zero_volume']} bars report zero volume, including possible first-bar vendor artifacts. No volume filter is used; volumes were not invented.")
    if counts['missing_volume'] or counts['negative_volume']:warnings.append('Some volumes are missing/invalid; excluded from volume displays, not replaced with made-up activity.')
    if any(not d['complete'] for d in day_rows):warnings.append('Incomplete/invalid sessions are excluded from the test. Indicator warm-up restarts after missing sessions; gaps are never filled.')
    warnings.extend(['Structural checks do not independently authenticate vendor prices.',
                     'Full-session completeness is an ex-post data-quality selection, not a live entry rule.',
                     ASSETS[asset]['note']])
    if not bars:raise ValueError('No valid completed five-minute RTH price bars. The existing snapshot is unchanged.')
    clean_hash=digest(bars)
    return dict(asset=asset,info=ASSETS[asset],bars=bars,days=day_rows,provenance=provenance,
                quality=dict(**counts,accepted_price_bars=len(bars),complete_sessions=sum(d['complete'] for d in day_rows),
                             tradeable_sessions=sum(d['tradeable'] for d in day_rows),warnings=warnings,issues=issues[:100],
                             calendar='XNYS cash-session calendar, not the futures overnight calendar',normalizer=VERSION,clean_sha256=clean_hash),
                start=bars[0]['timestamp'],end=bars[-1]['timestamp'],is_live=False)


class MarketStore:
    def __init__(self,root=None):
        self.root=Path(root) if root else ROOT/'data/market';self.lock=threading.Lock()
    def _path(self,asset):
        if asset not in ASSETS:raise ValueError('Unsupported asset.')
        return self.root/(asset+'-snapshot.json')
    def _write(self,path,data):
        self.root.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix('.tmp');temp.write_bytes(encoded(data));temp.replace(path)
    def read(self,asset):
        p=self._path(asset)
        if not p.exists():return None
        data=json.loads(p.read_text())
        if digest(data['bars'])!=data['quality']['clean_sha256']:raise ValueError('Stored bar checksum failed. Reimport the source; no backtest was run.')
        # Recheck temporal completeness when a stored snapshot is reused, never fill it.
        return data
    def save(self,asset,rows,provenance):
        data=normalize(rows,asset,provenance)
        with self.lock:self._write(self._path(asset),data)
        return data
    def import_text(self,asset,text):
        if len(text.encode())>4_000_000:raise ValueError('Maximum upload is 4 MB.')
        stripped=text.lstrip('\ufeff \n\r\t')
        raw_hash=hashlib.sha256(text.encode()).hexdigest()
        if stripped.startswith('{'):rows,meta=parse_yahoo(json.loads(stripped,parse_constant=reject_constant),asset)
        else:rows,meta=parse_bar_csv(text,asset)
        provenance=dict(origin='USER_UPLOAD',provider_claim='Yahoo Finance' if stripped.startswith('{') else 'User-supplied CSV',
                        label='User-supplied prices · not independently verified',acquired_at=utcnow().isoformat(),
                        raw_sha256=raw_hash,short_name=meta.get('shortName'),live=False)
        data=self.save(asset,rows,provenance)
        # Keep private original input for audit; never exposed as a public repo file.
        self._write(self.root/(asset+'-source.json'),dict(provenance=provenance,input=text))
        return data
    def seed_browser_capture(self):
        path=self.root/'es-browser-capture.json'
        if self._path('ES').exists() or not path.exists():return
        capture=json.loads(path.read_text());rows=[]
        for s in capture['sessions']:
            if any(len(s[k])!=s['observed_count'] for k in ['open','high','low','close','volume']):raise ValueError('Capture column lengths do not reconcile.')
            if s['step']!=300 or s['observed_count']!=79:raise ValueError('Unexpected observed capture sequence.')
            for i in range(s['observed_count']):rows.append(dict(timestamp=s['start']+i*s['step'],**{k:s[k][i] for k in ['open','high','low','close','volume']}))
        self.save('ES',rows,dict(origin='BROWSER_CAPTURE',provider_claim='Yahoo Finance',
            label='Yahoo browser-retrieved snapshot · manually transferred',acquired_at=capture['captured_date'],
            raw_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),source_urls=[s['url'] for s in capture['sessions']],
            short_name=capture['short_name'],method=capture['method'],live=False))
    def connection(self,asset):
        path=self.root/(asset+'-connection.json')
        return json.loads(path.read_text()) if path.exists() else dict(state='Not attempted',connected=False,error=None)
    def refresh(self,asset,days=59):
        if asset not in ASSETS or not 5<=days<=59:raise ValueError('Choose a supported asset and a 5–59 calendar-day lookback.')
        with self.lock:
            previous=self.connection(asset)
            if previous.get('attempt_epoch',0)>utcnow().timestamp()-120:
                return dict(previous,cooldown=True)
            when=utcnow();attempt=dict(state='Fetching',connected=False,attempt_epoch=when.timestamp(),last_attempt=when.isoformat())
            self._write(self.root/(asset+'-connection.json'),attempt)
        url=yahoo_url(asset,days,when)
        try:
            # Fixed provider host, verified TLS, no credentials, cookies, proxies or synthetic fallback.
            with requests.get(url,headers={'User-Agent':'Mozilla/5.0 (RangeLab personal research)','Accept':'application/json'},
                              timeout=(8,20),stream=True,allow_redirects=False) as r:
                if r.status_code==429:raise ValueError('Yahoo rate-limited the request. Wait; no evasion or automatic retry.')
                if r.status_code!=200:raise ValueError(f'Yahoo returned HTTP {r.status_code}; existing snapshot retained.')
                chunks=[];size=0
                for chunk in r.iter_content(65536):
                    size+=len(chunk)
                    if size>4_000_000:raise ValueError('Provider response exceeded 4 MB.')
                    chunks.append(chunk)
                raw=b''.join(chunks);payload=json.loads(raw,parse_constant=reject_constant)
            rows,meta=parse_yahoo(payload,asset)
            provenance=dict(origin='SERVER_FETCH',provider_claim='Yahoo Finance',label='Yahoo HTTPS snapshot · vendor-reported',
                            acquired_at=utcnow().isoformat(),raw_sha256=hashlib.sha256(raw).hexdigest(),source_urls=[url],short_name=meta.get('shortName'),live=False)
            data=self.save(asset,rows,provenance)
            with self.lock:self._write(self.root/(asset+'-source.json'),dict(provenance=provenance,response=payload))
            result=dict(attempt,state='Fetched snapshot',connected=True,error=None,last_success=utcnow().isoformat(),bars=len(data['bars']))
        except requests.exceptions.SSLError:
            result=dict(attempt,state='Connection unavailable',error='The workspace could not establish a TLS connection to Yahoo. This is a network/transport failure, not a trading-research refusal. Existing prices were retained.')
        except requests.exceptions.RequestException:
            result=dict(attempt,state='Connection unavailable',error='Yahoo could not be reached from this workspace. Existing prices were retained; no replacement data was generated.')
        except (ValueError,KeyError,TypeError) as e:
            result=dict(attempt,state='Source rejected',error=str(e)[:300])
        with self.lock:self._write(self.root/(asset+'-connection.json'),result)
        return result
