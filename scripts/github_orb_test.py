#!/usr/bin/env python3
"""Fetch the largest permitted recent Yahoo intraday window and derive ORB metrics.

The workflow stores only derived results. Raw vendor bars remain in an ephemeral
runner temp directory and are deleted with the job. No credentials or orders.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

from web_app.market_data import ASSETS, MarketStore
from web_app.orb_backtest import default_params, run_backtest

NY = ZoneInfo("America/New_York")
VERSION = "github-yahoo-orb-test-1.0"


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).astimezone(NY).isoformat()


def finite_or_none(value):
    return None if value is None or not math.isfinite(float(value)) else float(value)


def metric_window(result, dataset, cutoff):
    """Metrics for trades whose source-session date falls in a calendar window.

    The full run supplies past-only indicator state and the sizing path. Window
    drawdown is reset at the requested window's initial equity solely to make
    short windows comparable. It is labelled reset, closing-trade drawdown.
    """
    params = result["params"]
    trades = [t for t in result["trades"] if t["date"] >= cutoff]
    pnl = np.array([t["net_pnl"] for t in trades], dtype=float)
    rs = np.array([t["r_multiple"] for t in trades], dtype=float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    win_rs = rs[pnl > 0]
    loss_rs = rs[pnl < 0]
    equity = np.r_[params["initial_equity"], params["initial_equity"] + np.cumsum(pnl)]
    drawdown = 100 * (1 - equity / np.maximum.accumulate(equity))
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    avg_win = finite_or_none(win_rs.mean()) if len(win_rs) else None
    avg_loss = finite_or_none(abs(loss_rs.mean())) if len(loss_rs) else None
    realized_rr = avg_win / avg_loss if avg_win is not None and avg_loss else None
    eligible_days = [d for d in result["daily"] if d["date"] >= cutoff and d["eligible"]]
    observed_days = [d for d in dataset["days"] if d["date"] >= cutoff and d["complete"]]
    return {
        "cutoff_date": cutoff,
        "observed_complete_sessions": len(observed_days),
        "eligible_sessions": len(eligible_days),
        "trades": len(trades),
        "wins": int((pnl > 0).sum()),
        "losses": int((pnl < 0).sum()),
        "hit_rate_pct": finite_or_none(100 * (pnl > 0).mean()) if len(pnl) else None,
        "net_pnl": float(pnl.sum()),
        "return_pct_from_reset_equity": float(100 * (equity[-1] / equity[0] - 1)),
        "fees": float(sum(t["fees"] for t in trades)),
        "profit_factor": gross_profit / gross_loss if gross_loss else None,
        "expectancy_r": finite_or_none(rs.mean()) if len(rs) else None,
        "average_win_r": avg_win,
        "average_loss_r": avg_loss,
        "realized_rr": realized_rr,
        "max_closing_drawdown_pct_from_reset": float(drawdown.max()),
        "ambiguous_trade_count": sum(bool(t["ambiguous"]) for t in trades),
        "trade_dates": sorted({t["date"] for t in trades}),
        "interpretation": "Closing-trade window summary; not intrabar drawdown, live performance or a firm pass probability.",
    }


def summarize(asset, dataset, result, requested_days):
    last_date = max(d["date"] for d in dataset["days"] if d["complete"])
    last_day = datetime.fromisoformat(last_date).date()
    windows = {}
    for days in (21, 30, 59):
        cutoff = (last_day - timedelta(days=days - 1)).isoformat()
        windows[str(days)] = metric_window(result, dataset, cutoff)
    q = dataset["quality"]
    p = dataset["provenance"]
    return {
        "asset": asset,
        "instrument": ASSETS[asset]["name"],
        "evidence": "YAHOO VENDOR PRICE SNAPSHOT / ASSUMED EXECUTION",
        "run_version": VERSION,
        "acquired_at": p.get("acquired_at"),
        "source_provider": "Yahoo Finance chart endpoint",
        "source_symbol": ASSETS[asset]["symbol"],
        "source_urls": p.get("source_urls", []),
        "raw_source_sha256": p.get("raw_sha256"),
        "normalized_price_sha256": q["clean_sha256"],
        "source_window": {"first_bar_et": iso(dataset["start"]), "last_bar_et": iso(dataset["end"]), "requested_calendar_days": requested_days},
        "quality": {
            "source_rows": q["source_rows"],
            "accepted_price_bars": q["accepted_price_bars"],
            "complete_sessions": q["complete_sessions"],
            "tradeable_sessions": q["tradeable_sessions"],
            "missing_rth_bars": q["missing_rth_bars"],
            "invalid_prices": q["invalid_prices"],
            "off_tick_prices": q["invalid_tick"],
            "conflicting_duplicates": q["conflicting_duplicates"],
            "zero_volume_bars": q["zero_volume"],
            "warnings": q["warnings"],
            "normalizer": q["normalizer"],
        },
        "rules": {
            "opening_range": "09:30–10:00 America/New_York",
            "entry_window": "10:00–13:30 America/New_York",
            "initial_stop": "1.2 Wilder ATR",
            "initial_target": "2.0 Wilder ATR",
            "indicator_warmup": "250 completed RTH five-minute bars",
            "one_trade_per_session": True,
            "entry": "one-tick prospective stop, prior-completed-bar EMA20/50 alignment",
            "execution": "integer units, assumed fees and one-tick-per-side slippage; conservative stop-first OHLC ambiguity",
        },
        "parameters": result["params"],
        "full_available_window": metric_window(result, dataset, min(d["date"] for d in dataset["days"])),
        "windows": windows,
        "skip_counts": result["skip_counts"],
        "limitations": result["limitations"],
    }


def markdown(report):
    lines = [
        "# ORB Yahoo price-data test",
        "",
        f"Run version: `{report['run_version']}` · acquired UTC: `{report['run_at']}`",
        "",
        "This report contains derived metrics only. Raw vendor bars were used on the ephemeral GitHub runner and are not published as an artifact.",
        "The source is delayed/vendor-reported; fills are assumptions. These are not live broker results.",
        "",
    ]
    for asset, data in report["assets"].items():
        lines += [f"## {asset} — {data.get('instrument', 'unavailable')}", ""]
        if data.get("error"):
            lines += [f"**Unavailable:** {data['error']}", ""]
            continue
        q = data["quality"]
        lines += [
            f"Coverage: `{data['source_window']['first_bar_et']}` to `{data['source_window']['last_bar_et']}` ET; `{q['accepted_price_bars']}` accepted RTH bars; `{q['complete_sessions']}` complete sessions.",
            f"Quality: missing bars `{q['missing_rth_bars']}`, invalid OHLC `{q['invalid_prices']}`, off-tick `{q['off_tick_prices']}`, conflicting duplicates `{q['conflicting_duplicates']}`, zero-volume `{q['zero_volume_bars']}`.",
            "",
            "| Window | Trades | Hit rate | Profit factor | Max closing DD | Realized R:R | Net P&L |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for window, m in data["windows"].items():
            def cell(v, suffix=""):
                return "—" if v is None else f"{v:.2f}{suffix}"
            lines.append(f"| {window} calendar days | {m['trades']} | {cell(m['hit_rate_pct'], '%')} | {cell(m['profit_factor'])} | {cell(m['max_closing_drawdown_pct_from_reset'], '%')} | {cell(m['realized_rr'])} | ${m['net_pnl']:.2f} |")
        lines += ["", "Skip counts: `" + json.dumps(data["skip_counts"], sort_keys=True) + "`", ""]
        lines += ["Limitations:"] + [f"- {x}" for x in data["limitations"]] + [""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", default="ES,MES")
    parser.add_argument("--days", type=int, default=59)
    parser.add_argument("--output", type=Path, default=Path("orb-github-results.json"))
    args = parser.parse_args()
    if not 5 <= args.days <= 59:
        parser.error("Yahoo's documented native intraday window is capped here at 59 calendar days.")
    assets = [x.strip().upper() for x in args.assets.split(",") if x.strip()]
    if not assets or any(x not in ASSETS for x in assets):
        parser.error("Assets must be chosen from ES,MES,SPY,QQQ.")
    report = {"run_version": VERSION, "run_at": datetime.now(timezone.utc).isoformat(), "requested_days": args.days, "assets": {}}
    success = 0
    with tempfile.TemporaryDirectory(prefix="orb-yahoo-") as temp:
        for asset in assets:
            print(f"Fetching {asset} native 5-minute data for {args.days} calendar days…", flush=True)
            try:
                store = MarketStore(Path(temp) / asset)
                connection = store.refresh(asset, args.days)
                if not connection.get("connected"):
                    raise RuntimeError(connection.get("error") or "Yahoo connection failed")
                dataset = store.read(asset)
                result = run_backtest(dataset, default_params(asset))
                report["assets"][asset] = summarize(asset, dataset, result, args.days)
                success += 1
                print(f"{asset}: {dataset['quality']['accepted_price_bars']} accepted RTH bars; {result['metrics']['trades']} modeled fills.", flush=True)
            except Exception as exc:
                report["assets"][asset] = {"asset": asset, "instrument": ASSETS[asset]["name"], "error": str(exc)[:500]}
                print(f"{asset}: unavailable — {str(exc)[:240]}", file=sys.stderr, flush=True)
    report["markdown"] = markdown(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp = args.output.with_suffix(".tmp")
    temp.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(args.output)
    md = args.output.with_suffix(".md")
    md.write_text(report["markdown"], encoding="utf-8")
    print(f"Derived report written to {args.output}; raw prices were not retained by this job.")
    if not success:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
