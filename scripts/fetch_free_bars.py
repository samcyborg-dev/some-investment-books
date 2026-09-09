#!/usr/bin/env python3
"""Save a Yahoo 5-minute response on a computer with working Yahoo HTTPS access.

Standard library only. No credentials, price generation, adjustments or gap filling.
For private, informational research; respect the provider's terms and rate limits.
"""
import argparse
import hashlib
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import quote
from urllib.request import Request,urlopen

SYMBOLS={'ES':'ES=F','MES':'MES=F','SPY':'SPY','QQQ':'QQQ'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset',choices=SYMBOLS,default='ES')
    parser.add_argument('--days',type=int,default=59,help='Recent calendar days, 5–59. Not unlimited history.')
    parser.add_argument('--output',type=Path,help='Private output JSON path. Default data/market/ASSET-yahoo-download.json')
    args=parser.parse_args()
    if not 5<=args.days<=59:parser.error('--days must be 5–59')
    now=datetime.now(timezone.utc);symbol=SYMBOLS[args.asset]
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol,safe="")}?period1={int((now-timedelta(days=args.days)).timestamp())}&period2={int(now.timestamp())}&interval=5m&includePrePost=true'
    output=args.output or Path('data/market')/(args.asset+'-yahoo-download.json')
    request=Request(url,headers={'User-Agent':'Mozilla/5.0 (RangeLab personal research)','Accept':'application/json'})
    try:
        with urlopen(request,timeout=25) as response:
            raw=response.read(4000001)
        if len(raw)>4000000:raise ValueError('Response exceeded the 4 MB import limit.')
        data=json.loads(raw);chart=data.get('chart',{})
        if chart.get('error'):raise ValueError(str(chart['error']))
        result=chart['result'][0];meta=result['meta']
        if meta.get('symbol')!=symbol or meta.get('dataGranularity')!='5m':raise ValueError('Wrong source symbol or interval.')
        bars=len(result.get('timestamp',[]))
        if not bars:raise ValueError('No source candles were returned.')
    except HTTPError as e:
        raise SystemExit(f'Provider HTTP {e.code}. No output replaced. Do not evade rate limits or login restrictions.')
    except (URLError,ValueError,KeyError,TypeError,IndexError) as e:
        raise SystemExit(f'Download not completed: {e}\nNo prices generated and no existing output replaced. Try the source URL in your browser:\n{url}')
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.tmp');temp.write_bytes(raw);temp.replace(output)
    receipt=dict(source_url=url,acquired_at=now.isoformat(),asset=args.asset,source_symbol=symbol,source_rows=bars,
                 sha256=hashlib.sha256(raw).hexdigest(),is_live=False,
                 warning='Native source JSON; not yet quality-approved. Import into Range Lab for RTH, OHLC, tick and gap checks. Do not redistribute.')
    output.with_suffix('.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'Saved {bars} raw source timestamps to {output}.')
    print('Next: Market data & replay → select the matching asset → Import. This is not a live feed or a quality guarantee.')


if __name__=='__main__':main()
