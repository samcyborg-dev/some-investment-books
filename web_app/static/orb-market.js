// Actual-price research has its own state and provenance, never the simulation's.
import { ledgerChart } from "./orb-charts.js";
const $ = (q, r = document) => r.querySelector(q);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (n) =>
  `<svg class="icon" aria-hidden="true"><use href="/static/orb-icons.svg#${n}"/></svg>`;
const num = (n, d = 2) =>
  Number.isFinite(n)
    ? new Intl.NumberFormat("en-US", {
        minimumFractionDigits: d,
        maximumFractionDigits: d,
      }).format(n)
    : "—";
const cash = (n) =>
  Number.isFinite(n) ? (n < 0 ? "−" : "") + "$" + num(Math.abs(n)) : "—";
const et = (t) =>
  new Date(t * 1000).toLocaleString("en-GB", {
    timeZone: "America/New_York",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
const state = {
  asset: "ES",
  payload: null,
  result: null,
  params: null,
  day: null,
  loading: false,
  error: "",
  dirty: false,
  auto: false,
  timer: null,
};
const tag = (s, kind = "") => `<span class="tag ${kind}">${s}</span>`;
const metricHelp = (id) =>
  `<button class="metric-help" data-action="metric" data-id="${id}" aria-label="Explain ${id}">${icon("info")}</button>`;
const btn = (label, action, style = "", ico = "", extra = "") =>
  `<button type="button" class="button ${style}" data-market-action="${action}" ${extra}>${ico ? icon(ico) : ""}${label}</button>`;

async function request(path, body) {
  let r;
  try {
    r = await fetch("/api/orb/market/" + path, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : {},
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    throw Error(
      "The dashboard server could not be reached. Your stored snapshot is unchanged.",
    );
  }
  const j = await r.json().catch(() => {
    throw Error(
      "The server returned HTTP " +
        r.status +
        ". Stored prices were not replaced.",
    );
  });
  if (!r.ok)
    throw Error(
      Array.isArray(j.detail)
        ? j.detail.map((e) => e.msg).join(" · ")
        : j.detail || "Request failed.",
    );
  return j;
}
export function renderMarket() {
  return '<div id="market-root"><div class="loading-screen"><span class="loader"></span><h1>Opening the market-data workspace</h1><p>Loading source provenance, quality checks and the price-data test…</p></div></div>';
}
export function mountMarket() {
  if (state.payload) paint();
  else load();
}
async function load() {
  if (state.loading) return;
  state.loading = true;
  try {
    const p = await request("overview?asset=" + state.asset);
    state.payload = p;
    state.result = p.backtest;
    state.params = p.backtest ? { ...p.backtest.params } : defaults(p);
    state.day = p.dataset?.days.filter((d) => d.observed_bars).at(-1)?.date;
    state.dirty = false;
  } catch (e) {
    state.error = e.message;
  } finally {
    state.loading = false;
    paint();
  }
}
function defaults(p) {
  const a = p.assets[state.asset];
  return {
    asset: state.asset,
    initial_equity: 100000,
    risk_pct: 0.5,
    round_trip_fee: a.fee,
    slippage_ticks: 1,
    max_units: a.max_units,
  };
}
function stat(label, value, note, tone = "", metric = "") {
  return `<article class="stat-card"><div class="stat-heading"><span>${label}</span>${metric ? metricHelp(metric) : ""}</div><div class="stat-value ${tone}">${value}</div><div class="stat-foot">${note}</div></article>`;
}
function inputs() {
  const p = state.params;
  return `<form id="market-test-form" class="market-test-form"><div class="field-row">${[
    ["initial_equity", "Assumed equity ($)", 1000, 10000000, 1000],
    ["risk_pct", "Risk allowance (%)", 0.05, 2, 0.05],
    ["round_trip_fee", "Round-trip fee / unit ($)", 0, 500, 0.001],
    ["slippage_ticks", "Market slippage (ticks)", 0, 20, 1],
    ["max_units", "Maximum integer units", 1, 1000, 1],
  ]
    .map(
      ([k, label, min, max, step]) =>
        `<div><label class="field-label" for="market-${k}">${label}</label><input class="input" id="market-${k}" data-market-param="${k}" type="number" min="${min}" max="${max}" step="${step}" value="${p[k]}" ${state.loading ? "disabled" : ""} required></div>`,
    )
    .join(
      "",
    )}<div class="market-run-control"><button class="button primary wide" type="submit" ${state.loading ? "disabled" : ""}>${state.loading ? '<span class="loader"></span>' : icon("lab")}Run price-data test</button></div></div><p class="field-help" id="market-draft">${state.dirty ? "Edited assumptions · displayed results are still from the last completed run." : "Results use the displayed assumptions. Fees are examples—not a broker quote."}</p></form>`;
}
function connectionBox() {
  const c = state.payload.connection;
  return `<div class="market-connection ${c.connected ? "available" : ""}"><div>${icon(c.connected ? "check" : "shield")}<strong>${c.connected ? "Snapshot collector reached Yahoo" : c.state === "Not attempted" ? "Snapshot collector not connected" : esc(c.state)}</strong></div><p>${esc(c.error || "Stored candles are not a continuous real-time feed. Fetching preserves the original source and its timestamp.")}</p>${c.last_attempt ? `<small>Last attempt: ${esc(c.last_attempt.replace("T", " ").slice(0, 19))} UTC</small>` : ""}</div>`;
}
function githubResultCard() {
  const report = state.payload?.github_results;
  const item = report?.assets?.[state.asset];
  if (!report || !item) return "";
  if (item.error)
    return `<section class="card section-gap market-github-card"><div class="card-head"><div><h2>Latest GitHub data job</h2><p class="card-subtitle">The external runner could not produce a result for ${state.asset}.</p></div>${tag("UNAVAILABLE", "warning")}</div><div class="card-body"><p class="field-help">${esc(item.error)}</p></div></section>`;
  const rows = [21, 30, 59]
    .map((days) => item.windows?.[String(days)])
    .filter(Boolean);
  return `<section class="card section-gap market-github-card"><div class="card-head"><div><h2>Derived results from the GitHub runner</h2><p class="card-subtitle">${esc(item.source_provider)} · acquired ${esc(item.acquired_at || report.run_at || "unknown")} · native ${esc(item.source_symbol)} candles</p></div>${tag("DERIVED · NOT LIVE", "reported")}</div><div class="card-body"><div class="market-runner-note">${icon("layers")}<div><strong>These are the requested 21-, 30- and 59-day snapshots.</strong><p>Raw vendor bars were processed on an ephemeral runner and are not published. The results use assumed fills and the frozen ORB kernel. A 59-day window is the current Yahoo intraday limit used here.</p></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>WINDOW</th><th class="num">TRADES</th><th class="num">HIT RATE</th><th class="num">PF</th><th class="num">CLOSING DD</th><th class="num">REALIZED R:R</th><th class="num">NET P&L</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${row.cutoff_date} → ${daysLabel(row, item)}</td><td class="num">${row.trades}</td><td class="num">${formatMetric(row.hit_rate_pct, "%")}</td><td class="num">${formatMetric(row.profit_factor)}</td><td class="num negative">${formatMetric(row.max_closing_drawdown_pct_from_reset, "%")}</td><td class="num">${formatMetric(row.realized_rr)}</td><td class="num ${row.net_pnl >= 0 ? "positive" : "negative"}">${cash(row.net_pnl)}</td></tr>`).join("") || '<tr><td colspan="7">No derived window results.</td></tr>'}</tbody></table></div><p class="field-help">Hit rate is positive net closed trades ÷ trades. PF is gross positive net P&L ÷ gross negative net P&L. DD is reset, closing-trade DD—not intrabar or firm-account DD. R:R is average winning R ÷ average losing R; it is unknown when one side is absent.</p></div></section>`;
}
function daysLabel(row, item) {
  const cutoff = new Date(row.cutoff_date + "T00:00:00Z");
  const requested = item.source_window?.requested_calendar_days || 59;
  const last = new Date(item.source_window?.last_bar_et || 0);
  const rough = Math.min(
    requested,
    Math.max(1, Math.round((last - cutoff) / 86400000) + 1),
  );
  return `${rough}d window`;
}
function formatMetric(value, suffix = "") {
  return value === null ||
    value === undefined ||
    !Number.isFinite(Number(value))
    ? "—"
    : `${Number(value).toFixed(2)}${suffix}`;
}
function sourceFallback() {
  return `<section class="card section-gap"><div class="card-head"><div><h2>A way forward when the connection fails</h2><p class="card-subtitle">A provider or network failure never becomes a made-up price history.</p></div>${tag("NO API KEY REQUIRED", "model")}</div><div class="card-body"><div class="market-upload-steps"><div><span>01</span><h3>Open the source</h3><p>Open Yahoo’s public five-minute JSON in your browser. It requests the latest 59 calendar days, not unlimited history.</p><a class="text-link" href="${esc(state.payload.download_url)}" target="_blank" rel="noopener noreferrer">Open ${state.asset} source JSON ${icon("external")}</a></div><div><span>02</span><h3>Save, then import</h3><p>Save the complete JSON response to a file. Or use a timestamped OHLCV CSV. Do not round, fill gaps or invent missing candles.</p>${btn("Import price file", "import", "", "upload")}</div><div><span>03</span><h3>Let the checks decide</h3><p>The same quality checks and conservative kernel run on imported data. Uploads remain labeled user-supplied, not authenticated.</p><a class="text-link" href="/api/orb/market/csv-template" download>Price CSV template ${icon("download")}</a></div></div><p class="method-note">Yahoo data is supplied “as is” for informational use and must not be redistributed. Price inputs stay in this private workspace and are excluded from Git. A dated source snapshot is not a licensed live feed. <a class="text-link" href="${esc(state.payload.terms_url)}" target="_blank" rel="noopener noreferrer">Provider terms & delays ↗</a></p></div></section>`;
}
function alternatives() {
  return `<section class="card section-gap"><div class="card-head"><div><h2>Other assets to investigate</h2><p class="card-subtitle">Candidates, not declarations that the strategy works.</p></div></div><div class="market-candidates"><div><span class="asset-square">MES</span><h3>Same index, smaller units</h3><p>$5 per point versus ES’s $50. More granular sizing may help when one ES contract does not fit. It still needs its own MES prices and execution test.</p></div><div><span class="asset-square violet">QQQ</span><h3>Nasdaq-100 ETF</h3><p>A sensible next research candidate. The QQQ paper uses a different opening-direction entry, so it does not validate this 30-minute breakout.</p></div><div><span class="asset-square">SPY</span><h3>S&P 500 ETF</h3><p>Another candidate for cash-session testing. This initial ETF adapter is long-only with 1× cash buying power; it is not directly comparable to futures leverage.</p></div></div></section>`;
}

function paint() {
  const root = $("#market-root");
  if (!root) return;
  if (!state.payload) {
    root.innerHTML = `<div class="loading-screen"><h1>Market data could not load</h1><p>${esc(state.error)}</p>${btn("Try again", "reload", "primary")}</div>`;
    return;
  }
  const p = state.payload,
    d = p.dataset,
    r = state.result,
    m = r?.metrics,
    q = d?.quality;
  const select = `<select class="select" id="market-asset" aria-label="Choose market asset" ${state.loading ? "disabled" : ""}>${Object.entries(
    p.assets,
  )
    .map(
      ([k, a]) =>
        `<option value="${k}" ${k === state.asset ? "selected" : ""}>${k} · ${a.name}</option>`,
    )
    .join("")}</select>`;
  root.innerHTML = `<div class="page-head"><div><div class="eyebrow">OBSERVED PRICES · EXPLICIT ASSUMPTIONS</div><h1>Market data & replay</h1><p class="page-description">A separate research view for real source candles—not the Monte Carlo model.</p></div><div class="head-actions">${select}${btn(state.loading ? "Working…" : "Fetch Yahoo · 59 days", "refresh", "primary", "refresh", state.loading ? "disabled" : "")}${btn("Import", "import", "", "upload", state.loading ? "disabled" : "")}</div></div><input type="file" id="market-file" accept=".json,.csv,application/json,text/csv" hidden>
 ${state.error ? `<div class="callout">${icon("warning")}<div>${esc(state.error)}</div></div>` : ""}
 <div class="callout blue">${icon("clock")}<div><strong>${d ? "Dated snapshot, not a live connection." : "No price data for this asset yet."}</strong> ${d ? esc(d.provenance.label) + ". Last stored bar: " + et(d.end) + " ET." : "No synthetic or ES-to-MES replacement will be used."} Yahoo lists CME quotes at a 10-minute delay; actual freshness must still be checked.</div></div>
 ${githubResultCard()}
 ${
   d
     ? `<div class="stat-grid">${stat("Accepted RTH price bars", num(q.accepted_price_bars, 0), q.complete_sessions + " complete cash sessions")}${stat("Missing RTH bars", num(q.missing_rth_bars, 0), q.invalid_prices + " invalid OHLC · " + q.invalid_tick + " off-tick", q.missing_rth_bars ? "negative" : "")}${stat("Modeled fills", num(m.trades, 0), m.eligible_sessions + " sessions reached the warm-up gate")}${stat("Backtested net P&L", cash(m.net_pnl), m.trades ? "Assumed fills, fees and capital" : "No fills—not evidence of an edge", m.net_pnl > 0 ? "positive" : m.net_pnl < 0 ? "negative" : "", "pnl")}</div>
 <div class="analysis-grid market-analysis"><section class="card"><div class="card-head"><div><h2>${state.asset} · observed five-minute candles</h2><p class="card-subtitle">${esc(d.provenance.short_name || p.assets[state.asset].name)} · New York cash session</p></div><select class="small-select" id="market-day" aria-label="Choose stored session">${d.days
   .filter((day) => day.observed_bars)
   .map(
     (day) =>
       `<option value="${day.date}" ${day.date === state.day ? "selected" : ""}>${day.date}${day.complete ? "" : " · incomplete"}</option>`,
   )
   .join(
     "",
   )}</select></div><div class="chart-host market-candle-host" id="market-candles"></div><div class="chart-legend"><span class="legend-item"><span class="legend-line"></span>Observed OHLC</span><span class="legend-item"><span class="legend-dashed"></span>Opening range · known at 10:00 ET</span></div><div class="card-note">This is historical source data. Changing the session replays stored observations, not current market prices. No bid/ask or queue data is available.</div></section><aside class="card assumptions-card market-source-card"><div class="card-head"><div><h2>Know what you are looking at</h2><p class="card-subtitle">Source and sample boundaries</p></div></div><div class="card-body"><div class="assumption-row"><span>Source origin</span><strong>${d.provenance.origin === "BROWSER_CAPTURE" ? "Browser capture" : d.provenance.origin === "SERVER_FETCH" ? "HTTPS snapshot" : "User upload"}</strong></div><div class="assumption-row"><span>Observed window</span><strong>${d.days[0].date}<br>${d.days.at(-1).date}</strong></div><div class="assumption-row"><span>Independently authenticated</span><strong>No</strong></div><div class="assumption-row"><span>Warm-up requirement</span><strong>250 prior RTH bars</strong></div><div class="assumption-row"><span>Out-of-sample validation</span><strong>Not completed</strong></div><div class="assumption-row"><span>Broker / live orders</span><strong>Not connected</strong></div>${btn("Open external vendor chart", "vendor", "light wide", "external")}<p class="assumptions-foot">Separate TradingView viewer. Never ingested into these test results.</p></div></aside></div>
 <section class="card"><div class="card-head"><div><h2>Price-data test · ORB-30R 0.1a</h2><p class="card-subtitle">Frozen 30-minute range · 5-minute decisions · prior-bar EMA20/50 · Wilder ATR14 · fixed 1.2 / 2 ATR bracket</p></div>${tag(m.eligible_sessions < 20 ? "SMOKE TEST ONLY" : "EXPLORATORY", "warning")}</div><div class="card-body">${inputs()}${m.trades === 0 ? `<div class="market-no-trades"><span class="validation-icon">0</span><div><h3>No orders filled under these assumptions.</h3><p>That is a test result, not a broken chart. We do not force a fractional futures contract or relax the rules to manufacture activity.</p></div></div>` : ""}${
   r.rejected_triggers.length
     ? `<div class="notice-box section-gap"><h3>Why an observed trigger was skipped</h3>${r.rejected_triggers
         .slice(0, 3)
         .map(
           (t) =>
             `<p>${et(t.bar)} ET · ${t.side}: one ${state.asset} needed <strong>${cash(t.required_per_unit)}</strong> including fees/reserve, above the <strong>${cash(t.budget)}</strong> risk allowance. No fractional unit was forced.</p>`,
         )
         .join("")}</div>`
     : ""
 }<div class="market-test-metrics">${[
   ["Trade win rate", m.trades ? num(m.win_rate) + "%" : "—", "winrate"],
   ["Net expectancy", m.trades ? num(m.expectancy_r) + "R" : "—", "expectancy"],
   ["Profit factor", num(m.profit_factor), "pf"],
   ["Closing-trade DD", m.trades ? num(m.max_closing_dd_pct) + "%" : "—", "drawdown"],
   ["Ambiguous fills", num(m.ambiguous_trades, 0), ""],
   ["Diagnostic Sharpe", num(m.sharpe_diagnostic), "sharpe"],
 ]
   .map(
     ([label, value, metric]) =>
       `<div><span>${label}${metric ? metricHelp(metric) : ""}</span><strong>${value}</strong></div>`,
   )
   .join(
     "",
   )}</div><p class="field-help">${m.trades < 20 ? "This sample is far too small to infer an edge. " : ""}Sharpe requires at least 20 eligible sessions here and remains descriptive. Intrabar drawdown and firm pass probability are not established.</p></div>${m.trades ? '<div class="chart-host" id="market-equity"></div>' : ""}</section>
 <div class="two-grid section-gap"><section class="card"><div class="card-head"><div><h2>Data quality, with the exceptions left in</h2><p class="card-subtitle">Passing structural checks is not a guarantee of price accuracy.</p></div></div><div class="card-body"><div class="market-quality-grid">${[
   ["Source rows", q.source_rows],
   ["Outside cash session", q.outside_rth],
   ["Conflicting duplicates", q.conflicting_duplicates],
   ["Zero-volume bars", q.zero_volume],
 ]
   .map(([k, v]) => `<div><span>${k}</span><strong>${v}</strong></div>`)
   .join(
     "",
   )}</div><ul class="market-limit-list">${q.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></div></section><section class="card"><div class="card-head"><div><h2>Decision-gate audit</h2><p class="card-subtitle">Counts are bar checks—not distinct trades or a signal win rate.</p></div></div><div class="card-body">${Object.entries(
   r.skip_counts,
 )
   .map(
     ([key, n]) =>
       `<div class="market-gate"><span>${esc({ warmup: "Still warming indicators", unaffordable: "Integer unit unaffordable", already_crossed: "Price already beyond trigger", trend_gate: "EMA alignment absent", range_gate: "Range wider than 5 ATR", incomplete_session: "Incomplete session", etf_long_only: "ETF short side disabled", gap_buying_power: "Opening gap exceeds the cash cap" }[key] || key)}</span><strong>${num(n, 0)}</strong></div>`,
   )
   .join(
     "",
   )}<p class="field-help">Approved filters use only the prior completed bar. Current-bar prices may execute an order, never retroactively approve it.</p></div></section></div>
 <section class="card table-card"><div class="card-head"><div><h2>Modeled trade ledger</h2><p class="card-subtitle">Bar timestamps are time windows, not claimed broker fill timestamps.</p></div>${btn("Export test JSON", "export", "small", "download")}</div><div class="table-wrap"><table class="data-table"><thead><tr><th>ENTRY BAR · ET</th><th>SIDE / UNITS</th><th class="num">ENTRY / EXIT</th><th class="num">NET P&L</th><th class="num">NET R</th><th>EXIT / UNCERTAINTY</th></tr></thead><tbody>${r.trades.map((t) => `<tr><td>${et(t.entry_bar)}<small>Exit bar ${et(t.exit_bar)}</small></td><td>${t.side} · ${t.quantity} ${state.asset}</td><td class="num">${num(t.entry_price)}<small>${num(t.exit_price)}</small></td><td class="num ${t.net_pnl < 0 ? "negative" : "positive"}">${cash(t.net_pnl)}</td><td class="num">${num(t.r_multiple)}R</td><td>${tag(t.exit_reason, t.ambiguous ? "warning" : "model")}<small>${t.ambiguous ? "Conservative OHLC ambiguity" : "Fill still assumed, not observed"}</small></td></tr>`).join("") || '<tr><td colspan="6">No modeled fills in this snapshot under the displayed rules and risk allowance.</td></tr>'}</tbody></table></div></section>
 <details class="card section-gap market-method"><summary>Full execution assumptions & reproducibility ${icon("chevron")}</summary><div class="card-body"><ul class="market-limit-list">${r.limitations.map((l) => `<li>${esc(l)}</li>`).join("")}</ul><p class="field-help">Normalized price SHA-256 <code>${q.clean_sha256}</code><br>Source artifact SHA-256 <code>${esc(d.provenance.raw_sha256)}</code><br>${esc(d.provenance.method || "Source input preserved privately in data/market/. No raw prices are committed to Git.")}</p>${(d.provenance.source_urls || []).map((u, i) => `<a class="text-link market-source-link" href="${esc(u)}" target="_blank" rel="noopener noreferrer">Source request ${i + 1} ↗</a>`).join("")}</div></details>`
     : `<section class="card empty-ledger"><div class="empty-illustration">${icon("layers")}</div><h2>Load ${state.asset} prices before testing ${state.asset}.</h2><p>There is no verified ${state.asset} history in this workspace yet. The collector or import tool can load native five-minute data; the engine will not replace it with synthetic bars or another instrument.</p><div class="button-group">${btn("Try Yahoo collector", "refresh", "primary", "refresh", state.loading ? "disabled" : "")}${btn("Import price snapshot", "import", "", "upload")}${btn("External vendor chart", "vendor", "", "external")}</div></section>`
 }
 ${connectionBox()}${sourceFallback()}${alternatives()}
 <div class="market-auto-row"><label><input type="checkbox" id="market-auto" ${state.auto ? "checked" : ""}> Try a new snapshot every 5 minutes while this view is visible</label><span>Stops automatically on a connection error. No background orders.</span></div>`;
  draw();
}
function draw() {
  if (!$("#market-root") || !state.payload?.dataset) return;
  candles();
  if ($("#market-equity") && state.result?.metrics.trades)
    ledgerChart(
      $("#market-equity"),
      {
        curve: state.result.curve,
        evidence: "PRICE-DATA RESEARCH / ASSUMED FILLS",
      },
      "equity",
    );
}
function candles() {
  const host = $("#market-candles"),
    d = state.payload.dataset,
    day = d.days.find((x) => x.date === state.day);
  if (!host || !day) return;
  const bars = d.bars.filter(
    (b) => b.timestamp >= day.open && b.timestamp < day.close,
  );
  if (!bars.length) return;
  const W = Math.max(275, host.clientWidth - 24),
    H = 320,
    L = 59,
    R = 18,
    T = 25,
    B = 34,
    pw = W - L - R,
    ph = H - T - B;
  const low = Math.min(...bars.map((b) => b.low)),
    high = Math.max(...bars.map((b) => b.high)),
    pad = Math.max((high - low) * 0.13, 1),
    min = low - pad,
    max = high + pad;
  const x = (t) => L + (((t - day.open) / 300 + 0.5) / day.expected_bars) * pw,
    y = (v) => T + ((max - v) / (max - min)) * ph;
  let svg = "";
  for (let i = 0; i < 5; i++) {
    const v = max - ((max - min) * i) / 4,
      yy = y(v);
    svg += `<line x1="${L}" x2="${W - R}" y1="${yy}" y2="${yy}" stroke="#e6eded" stroke-dasharray="3 4"/><text x="${L - 9}" y="${yy + 3}" font-size="9" text-anchor="end" fill="#5d727d">${num(v, 2)}</text>`;
  }
  const rx = L + (6 / day.expected_bars) * pw;
  svg += `<rect x="${L}" y="${T}" width="${rx - L}" height="${ph}" fill="#dceee5" opacity=".45"/><line x1="${rx}" x2="${rx}" y1="${T}" y2="${H - B}" stroke="#a6c6b8" stroke-dasharray="3 3"/>`;
  if (day.or_high !== null)
    for (const [label, val] of [
      ["OR high", day.or_high],
      ["OR low", day.or_low],
    ])
      svg += `<line x1="${rx}" x2="${W - R}" y1="${y(val)}" y2="${y(val)}" stroke="#729c8e" stroke-dasharray="4 4"/><text x="${W - R - 4}" y="${y(val) - 5}" text-anchor="end" font-size="9" fill="#486f60">${label} ${num(val)}</text>`;
  const bw = Math.max(1.3, (pw / day.expected_bars) * 0.62);
  for (const b of bars) {
    const xx = x(b.timestamp),
      color = b.close >= b.open ? "#187f6a" : "#bd6c55";
    svg += `<line x1="${xx}" x2="${xx}" y1="${y(b.high)}" y2="${y(b.low)}" stroke="${color}" stroke-width="1"/><rect x="${xx - bw / 2}" y="${y(Math.max(b.open, b.close))}" width="${bw}" height="${Math.max(1, Math.abs(y(b.open) - y(b.close)))}" fill="${color}" rx=".5"/>`;
  }
  for (const t of state.result?.trades.filter((t) => t.date === day.date) ||
    []) {
    const xx = x(t.entry_bar),
      yy = y(t.entry_price);
    svg += `<circle cx="${xx}" cy="${yy}" r="5" fill="white" stroke="#233d46" stroke-width="1.5"/><text x="${xx + 7}" y="${yy - 7}" font-size="9" fill="#233d46">#${t.id}</text>`;
  }
  const step = W < 440 ? 18 : 12;
  for (let i = 0; i < day.expected_bars; i += step) {
    const t = day.open + i * 300;
    svg += `<text x="${x(t)}" y="${H - 13}" text-anchor="middle" font-size="9" fill="#5d727d">${new Date(t * 1000).toLocaleTimeString("en-GB", { timeZone: "America/New_York", hour: "2-digit", minute: "2-digit" })}</text>`;
  }
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Historical ${state.asset} source candles for ${day.date}, not live prices">${svg}</svg><div class="chart-tooltip" hidden></div>`;
  const tip = $(".chart-tooltip", host),
    element = $("svg", host);
  const show = (e) => {
    const rect = element.getBoundingClientRect(),
      index = Math.max(
        0,
        Math.min(
          day.expected_bars - 1,
          Math.floor(
            ((((e.clientX - rect.left) * W) / rect.width - L) / pw) *
              day.expected_bars,
          ),
        ),
      ),
      t = day.open + index * 300,
      b = bars.find((b) => b.timestamp === t);
    if (!b) {
      tip.hidden = true;
      return;
    }
    tip.innerHTML = `<strong>${et(t)} ET · source bar</strong><span>Open / close <b>${num(b.open)} / ${num(b.close)}</b></span><span>High / low <b>${num(b.high)} / ${num(b.low)}</b></span><span>Reported volume <b>${num(b.volume, 0)}</b></span>`;
    tip.hidden = false;
    tip.style.left =
      Math.max(4, Math.min(x(t) + 16, host.clientWidth - tip.offsetWidth - 7)) +
      "px";
    tip.style.top = "12px";
  };
  host.onpointermove = show;
  host.onpointerdown = show;
  host.onpointerleave = (e) => {
    if (e.pointerType !== "touch") tip.hidden = true;
  };
}
async function refresh() {
  if (state.loading) return;
  state.loading = true;
  state.error = "";
  paint();
  try {
    const j = await request("refresh", { asset: state.asset, days: 59 });
    state.payload.connection = j.connection;
    if (!j.connection.connected) {
      state.error =
        j.connection.error ||
        "Collector is cooling down. Existing snapshot retained.";
      stopAuto();
    } else {
      state.payload = await request("overview?asset=" + state.asset);
      state.result = state.payload.backtest;
      state.params = { ...state.result.params };
      state.day = state.payload.dataset.days
        .filter((d) => d.observed_bars)
        .at(-1)?.date;
      state.dirty = false;
    }
  } catch (e) {
    state.error = e.message;
    stopAuto();
  } finally {
    state.loading = false;
    paint();
  }
}
async function importFile(file) {
  if (!file || state.loading) return;
  if (file.size > 4000000) {
    state.error = "Maximum price-file size is 4 MB.";
    paint();
    return;
  }
  state.loading = true;
  state.error = "";
  paint();
  try {
    state.payload = await request("import", {
      asset: state.asset,
      text: await file.text(),
    });
    state.result = state.payload.backtest;
    state.params = { ...state.result.params };
    state.day = state.payload.dataset.days
      .filter((d) => d.observed_bars)
      .at(-1)?.date;
    state.dirty = false;
  } catch (e) {
    state.error = e.message;
  } finally {
    state.loading = false;
    paint();
  }
}
function stopAuto() {
  state.auto = false;
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
}
function exportTest() {
  const r = state.result;
  if (!r) return;
  const a = document.createElement("a"),
    blob = new Blob(
      [
        JSON.stringify(
          {
            ...r,
            source: state.payload.dataset.provenance,
            quality: state.payload.dataset.quality,
          },
          null,
          2,
        ),
      ],
      { type: "application/json" },
    ),
    url = URL.createObjectURL(blob);
  a.href = url;
  a.download = `orb-${state.asset}-price-research-not-live.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
function vendorChart() {
  let dialog = $("#market-vendor");
  if (dialog) dialog.remove();
  dialog = document.createElement("dialog");
  dialog.id = "market-vendor";
  dialog.className = "detail-dialog reader";
  const a = state.payload.assets[state.asset];
  dialog.innerHTML = `<div class="dialog-head"><div><h2>External vendor chart · ${state.asset}</h2><p>TradingView’s terms and delays apply. This is NOT the data behind our backtest.</p></div><button class="icon-button" data-market-action="close-vendor" aria-label="Close vendor chart">${icon("close")}</button></div><div class="dialog-body"><div class="notice-box">Loads directly from TradingView in your browser. Availability is not guaranteed; this chart supplies no bars or orders to Range Lab. CME data may be delayed.</div><div class="tradingview-widget-container market-vendor-widget"><div class="tradingview-widget-container__widget"></div><div class="tradingview-widget-copyright"><a href="https://www.tradingview.com/chart/?symbol=${encodeURIComponent(a.tv)}" target="_blank" rel="noopener noreferrer">View ${state.asset} on TradingView</a></div></div></div>`;
  document.body.append(dialog);
  dialog.showModal();
  const config = {
    autosize: true,
    width: "100%",
    height: "100%",
    symbol: a.tv,
    interval: "5",
    timezone: "America/New_York",
    theme: "light",
    style: "1",
    allow_symbol_change: false,
    support_host: "https://www.tradingview.com",
    utm_source: location.hostname,
    utm_medium: "widget_new",
    utm_campaign: "advanced-chart",
    "page-uri": location.host + location.pathname,
  };
  const frame = document.createElement("iframe");
  frame.title = "External TradingView chart for " + state.asset;
  frame.className = "market-vendor-iframe";
  frame.referrerPolicy = "strict-origin-when-cross-origin";
  frame.setAttribute(
    "sandbox",
    "allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox",
  );
  frame.src =
    "https://www.tradingview-widget.com/embed-widget/advanced-chart/?locale=en#" +
    encodeURIComponent(JSON.stringify(config));
  $(".tradingview-widget-container__widget", dialog).replaceWith(frame);
  // Provider scripts stay on the provider's origin; they cannot read our notes or imported ledgers.
}

document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-market-action]");
  if (!b || b.disabled) return;
  const a = b.dataset.marketAction;
  e.preventDefault();
  if (a === "refresh") refresh();
  if (a === "reload") load();
  if (a === "import") $("#market-file").click();
  if (a === "export") exportTest();
  if (a === "vendor") vendorChart();
  if (a === "close-vendor") $("#market-vendor")?.close();
});
document.addEventListener("change", async (e) => {
  const el = e.target;
  if (el.id === "market-asset") {
    if (state.loading) {
      el.value = state.asset;
      return;
    }
    el.disabled = true;
    stopAuto();
    state.asset = el.value;
    state.payload = null;
    state.error = "";
    state.params = null;
    await load();
  }
  if (el.id === "market-day") {
    state.day = el.value;
    candles();
  }
  if (el.id === "market-file") importFile(el.files[0]);
  if (el.id === "market-auto") {
    state.auto = el.checked;
    if (state.auto) {
      state.timer = setInterval(() => {
        if (document.visibilityState === "visible" && $("#market-root"))
          refresh();
      }, 300000);
      refresh();
    } else stopAuto();
  }
});
document.addEventListener("input", (e) => {
  if (e.target.dataset.marketParam) {
    state.params[e.target.dataset.marketParam] = Number(e.target.value);
    state.dirty = true;
    $("#market-draft").textContent =
      "Edited assumptions · run the test to apply them. The displayed output is still the previous run.";
  }
});
document.addEventListener("submit", async (e) => {
  if (e.target.id !== "market-test-form") return;
  e.preventDefault();
  if (state.loading || !e.target.reportValidity()) return;
  const params = { ...state.params };
  state.loading = true;
  state.error = "";
  paint();
  try {
    state.result = await request("backtest", params);
    state.params = { ...state.result.params };
    state.dirty = false;
  } catch (err) {
    state.error = err.message;
  } finally {
    state.loading = false;
    paint();
  }
});
let resize;
window.addEventListener("resize", () => {
  clearTimeout(resize);
  resize = setTimeout(draw, 100);
});
window.addEventListener("hashchange", () => {
  if (location.hash !== "#market") stopAuto();
});
