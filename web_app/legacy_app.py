"""
Interactive Quantitative Strategy Research & SSRN Validation Web Application.
Built with FastAPI, Chart.js, and Tailwind CSS.
"""

import os
import json
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from quant_engine.core.data_manager import MarketDataManager
from quant_engine.strategies.prop_volatility_breakout import PropVolatilityBreakoutStrategy
from quant_engine.strategies.prop_mean_reversion import PropMeanReversionStrategy
from quant_engine.strategies.personal_dual_momentum import PersonalDualMomentumStrategy
from quant_engine.strategies.personal_trend_risk_parity import PersonalTrendRiskParityStrategy
from quant_engine.analytics.report_generator import generate_html_tearsheet

app = FastAPI(title="Quantitative Strategy Engine & SSRN Research Hub")

# Global market data cache for instant backtests
data_manager = MarketDataManager(seed=42)
cached_daily = data_manager.generate_daily_multiverse(start_date="2018-01-01", end_date="2026-06-01")
cached_intraday = data_manager.generate_intraday_bars(symbol="ES_FUT", days=60)


class BacktestRequest(BaseModel):
    strategy_id: str = "prop_vol_breakout"  # 'prop_vol_breakout', 'prop_mean_rev', 'personal_dual_mom', 'personal_trend_rp'
    account_size: float = 100_000.0
    risk_per_trade_pct: float = 0.50
    daily_kill_switch_pct: float = 2.5
    profit_target_pct: float = 8.0
    atr_stop_mult: float = 1.2
    atr_tp_mult: float = 2.0
    enable_trailing_stop: bool = True
    target_annual_vol: float = 0.12


@app.get("/", response_class=HTMLResponse)
async def serve_index(request: Request):
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Templates missing</h1>")


@app.post("/api/backtest")
async def run_backtest_api(req: BacktestRequest):
    try:
        if req.strategy_id == "prop_vol_breakout":
            strat = PropVolatilityBreakoutStrategy(
                account_size=req.account_size,
                risk_per_trade_pct=req.risk_per_trade_pct,
                atr_stop_mult=req.atr_stop_mult,
                atr_tp_mult=req.atr_tp_mult,
                daily_kill_switch_pct=req.daily_kill_switch_pct,
                profit_target_pct=req.profit_target_pct,
                enable_trailing_stop=req.enable_trailing_stop
            )
            eq_df, tr_df, metrics = strat.run_backtest(cached_intraday)

        elif req.strategy_id == "prop_mean_rev":
            strat = PropMeanReversionStrategy(
                account_size=req.account_size,
                risk_per_trade_pct=req.risk_per_trade_pct,
                atr_stop_mult=req.atr_stop_mult,
                atr_tp_mult=req.atr_tp_mult,
                daily_kill_switch_pct=req.daily_kill_switch_pct,
                profit_target_pct=req.profit_target_pct
            )
            eq_df, tr_df, metrics = strat.run_backtest(cached_intraday)

        elif req.strategy_id == "personal_dual_mom":
            strat = PersonalDualMomentumStrategy(
                account_size=req.account_size,
                target_annual_vol=req.target_annual_vol
            )
            eq_df, tr_df, metrics = strat.run_backtest(cached_daily)

        elif req.strategy_id == "personal_trend_rp":
            strat = PersonalTrendRiskParityStrategy(
                account_size=req.account_size,
                target_annual_vol=req.target_annual_vol,
                atr_stop_mult=req.atr_stop_mult
            )
            eq_df, tr_df, metrics = strat.run_backtest(cached_daily)

        else:
            return JSONResponse({"status": "error", "message": "Unknown strategy ID"}, status_code=400)

        # Downsample equity curve for smooth rendering
        if len(eq_df) > 300:
            step = max(1, len(eq_df) // 300)
            sampled_eq = eq_df.iloc[::step].copy()
        else:
            sampled_eq = eq_df.copy()

        equity_chart_data = {
            "labels": [ts.strftime("%Y-%m-%d %H:%M") if hasattr(ts, 'strftime') else str(ts) for ts in sampled_eq.index],
            "equity": [round(float(v), 2) for v in sampled_eq["equity"].values],
            "drawdown": [round(float(v), 2) for v in sampled_eq["drawdown_pct"].values],
            "daily_drawdown": [round(float(v), 2) for v in sampled_eq["daily_drawdown_pct"].values] if "daily_drawdown_pct" in sampled_eq.columns else []
        }

        # Trade logs sample
        recent_trades = []
        if not tr_df.empty:
            for _, r in tr_df.tail(25).iterrows():
                recent_trades.append({
                    "id": int(r.get("trade_id", 0)),
                    "symbol": str(r.get("symbol", "")),
                    "direction": str(r.get("direction", "")),
                    "entry_price": round(float(r.get("entry_price", 0)), 2),
                    "exit_price": round(float(r.get("exit_price", 0)), 2),
                    "net_pnl": round(float(r.get("net_pnl", 0)), 2),
                    "r_multiple": round(float(r.get("r_multiple", 0)), 2),
                    "return_pct": round(float(r.get("return_pct", 0) * 100), 2),
                    "exit_reason": str(r.get("exit_reason", ""))
                })

        return JSONResponse({
            "status": "success",
            "strategy_id": req.strategy_id,
            "metrics": metrics,
            "equity_chart": equity_chart_data,
            "recent_trades": recent_trades
        })

    except Exception as e:
        import traceback
        return JSONResponse({"status": "error", "message": str(e), "traceback": traceback.format_exc()}, status_code=500)


@app.get("/api/download-guide")
async def download_master_guide():
    pdf_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "QUANT_ALPHA_MASTER_SYSTEM_GUIDE.pdf")
    if os.path.exists(pdf_path):
        from fastapi.responses import FileResponse
        return FileResponse(pdf_path, media_type="application/pdf", filename="QUANT_ALPHA_MASTER_SYSTEM_GUIDE.pdf")
    return JSONResponse({"status": "error", "message": "PDF guide not found"}, status_code=404)


@app.get("/api/book-references")
async def get_book_references():
    return JSONResponse({
        "books": [
            {
                "title": "Algorithmic Trading: Winning Strategies and Their Rationale",
                "author": "Ernie Chan",
                "year": 2013,
                "domain": "Mean Reversion & Stat Arb",
                "core_concepts": "Ornstein-Uhlenbeck Process, Hurst Exponent (H < 0.5), Half-life of mean reversion, Bollinger Band Z-score, Kelly sizing",
                "ssrn_cross_ref": "Avellaneda & Lee (2010) Statistical Arbitrage in US Equities",
                "repo_file": "Algorithmic Trading - Winning Strategies and Their Rationale 2013.pdf"
            },
            {
                "title": "Dual Momentum Investing: An Innovative Strategy for Higher Returns with Lower Risk",
                "author": "Gary Antonacci",
                "year": 2015,
                "domain": "Cross-Asset Momentum",
                "core_concepts": "Relative Momentum (Cross-sectional ranking) + Absolute Momentum (Time-series trend filter), Cash/Bond safe haven rotation",
                "ssrn_cross_ref": "Moskowitz, Ooi, Pedersen (2012) Time Series Momentum; Asness et al. (2013) Value and Momentum Everywhere",
                "repo_file": "Dual Momentum Investing - An Innovative Strategy for Higher Returns with Lower Risk 2015.epub"
            },
            {
                "title": "Evidence-Based Technical Analysis: Applying the Scientific Method",
                "author": "David Aronson",
                "year": 2007,
                "domain": "Statistical Validation & Bias",
                "core_concepts": "Data mining bias, Monte Carlo permutation null hypothesis, White's Reality Check, Hansen SPA test, Out-of-Sample verification",
                "ssrn_cross_ref": "Bailey & Lopez de Prado (2014) The Deflated Sharpe Ratio (SSRN 2460551); Harvey, Liu, Zhu (2016) Factor Zoo",
                "repo_file": "Evidence-Based Technical Analysis - Applying the Scientific Method and Statistical Inference to Trading Signals 2007.pdf"
            },
            {
                "title": "Way of the Turtle & Trend Following",
                "author": "Curtis Faith / Michael Covel",
                "year": "2007/2009",
                "domain": "Managed Futures & Breakouts",
                "core_concepts": "Donchian Breakouts (20-day / 55-day), ATR Volatility sizing (N units), Elder 6% portfolio heat cap, Dynamic trailing stops",
                "ssrn_cross_ref": "Baltas & Kosowski (2013) Momentum Strategies in Futures Markets & Volatility Scaling",
                "repo_file": "Way of the Turtle - The Secret Methods that Turned Ordinary People into Legendary Traders 2007.pdf"
            },
            {
                "title": "Long-Term Secrets to Short-Term Trading",
                "author": "Larry Williams",
                "year": 1999,
                "domain": "Short-Term Volatility Breakout",
                "core_concepts": "Range expansion breakouts, Opening Range Breakout (ORB), Smash day reversals, Volatility contraction preceding expansion",
                "ssrn_cross_ref": "Cooper, Gutierrez, Hameed (2004) Market Regimes & Short-Term Reversals (SSRN)",
                "repo_file": "Long-Term Secrets to Short-Term Trading 1999.pdf"
            },
            {
                "title": "The New Trading for a Living",
                "author": "Dr. Alexander Elder",
                "year": 2014,
                "domain": "Prop Risk Rules & Triple Screen",
                "core_concepts": "2% Rule (Max risk per trade), 6% Rule (Max monthly risk stop), Triple Screen multi-timeframe confirmation, Dynamic Impulse system",
                "ssrn_cross_ref": "Prop Firm Evaluation Protocols (FTMO, Topstep, Apex) Max Daily & Total DD constraints",
                "repo_file": "The New Trading for a Living - Psychology, Discipline, Trading Tools and Systems, Risk Control, Trade Management 2014.pdf"
            }
        ]
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
