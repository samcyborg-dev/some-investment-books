import { renderMarket, mountMarket } from "./orb-market.js";
import {
  equityChart,
  ledgerChart,
  histogramChart,
  donutMarkup,
} from "./orb-charts.js";

const $ = (q, root = document) => root.querySelector(q);
const $$ = (q, root = document) => [...root.querySelectorAll(q)];
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const icon = (name) =>
  `<svg class="icon" aria-hidden="true"><use href="/static/orb-icons.svg#${name}"/></svg>`;
const number = (v, d = 2) =>
  Number.isFinite(v)
    ? new Intl.NumberFormat("en-US", {
        minimumFractionDigits: d,
        maximumFractionDigits: d,
      }).format(v)
    : "—";
const money = (v, d = 0) =>
  Number.isFinite(v) ? (v < 0 ? "−" : "") + "$" + number(Math.abs(v), d) : "—";
const signed = (v, d = 2) =>
  Number.isFinite(v)
    ? (v > 1e-10 ? "+" : v < -1e-10 ? "−" : "") + number(Math.abs(v), d)
    : "—";
const pct = (v, d = 2) => number(v, d) + "%";
const tag = (text, kind = "") => `<span class="tag ${kind}">${text}</span>`;
const info = (id) =>
  `<button class="metric-help" data-action="metric" data-id="${id}" aria-label="Explain ${id}">${icon("info")}</button>`;
const button = (label, action, style = "", ico = "", extra = "") =>
  `<button type="button" class="button ${style}" data-action="${action}" ${extra}>${ico ? icon(ico) : ""}${label}</button>`;
const blank = '<span class="loader" aria-label="Loading"></span>';
const readableColor = (rgb) => {
  const lum = (c) =>
    c
      .map((v) => {
        v /= 255;
        return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
      })
      .reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0);
  const bg = lum(rgb);
  return (bg + 0.05) / (lum([28, 55, 46]) + 0.05) >= 4.5
    ? "#1c372e"
    : 1.05 / (bg + 0.05) >= 4.5
      ? "#ffffff"
      : "#000000";
};
const state = {
  data: null,
  result: null,
  draft: null,
  route: "overview",
  chartMode: "equity",
  ledgerMode: "equity",
  running: false,
  dirty: false,
  activePreset: "base",
  heatMetric: "pass_pct",
  researchFilter: "all",
  sourceQuery: "",
  sortKey: null,
  sortDesc: true,
  ledger: null,
  ledgerQuery: "",
  ledgerSide: "all",
  ledgerPage: 0,
  initialEquity: 100000,
  filename: "",
  importing: false,
  notes: null,
  noteQuery: "",
  report: null,
  reportIndex: 0,
  lastRun: null,
};
const PRESETS = {
  base: { label: "Base case · independent", patch: {} },
  clustered: { label: "Clustered losses", patch: { loss_persistence: 0.75 } },
  costs: { label: "Higher transaction costs", patch: { cost_r: 0.2 } },
  trailing: { label: "Trailing dollar floor", patch: { floor: "trailing" } },
  gaps: { label: "Rare 3R loss", patch: { gap_probability_pct: 2 } },
  activity: { label: "Fewer signals", patch: { activity_pct: 30 } },
  combined: {
    label: "Combined adverse",
    patch: {
      loss_persistence: 0.75,
      cost_r: 0.2,
      gap_probability_pct: 2,
      floor: "trailing",
    },
  },
};
const presetIds = Object.keys(PRESETS);
let defaults, resizeTimer;

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch("/api/orb/" + path, {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error(
      "The research server could not be reached. Check the connection and try again.",
    );
  }
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    const detail = data.detail;
    throw new Error(
      Array.isArray(detail)
        ? detail.map((e) => `${e.loc?.at(-1) || "Input"}: ${e.msg}`).join(" · ")
        : detail || "The request could not be completed.",
    );
  }
  return data;
}

function toast(message, error = false) {
  const region = $("#toasts");
  $$(".toast", region)
    .filter((n) => n.dataset.message === message)
    .forEach((n) => n.remove());
  while (region.children.length >= 2) region.firstElementChild.remove();
  const node = document.createElement("div");
  node.className = "toast" + (error ? " error" : "");
  node.dataset.message = message;
  node.innerHTML =
    icon(error ? "warning" : "check") +
    `<span>${esc(message)}</span><button class="icon-button" aria-label="Dismiss notification">${icon("close")}</button>`;
  node.querySelector("button").onclick = () => node.remove();
  $("#toasts").append(node);
  setTimeout(() => node.remove(), error ? 9000 : 3500);
}

function exportMenu() {
  return `<div class="export-wrap">${button("Export results", "export-menu", "", "download", 'aria-expanded="false" aria-haspopup="true" id="export-button"')}<div class="export-menu" id="export-menu" hidden>${button("Copy result summary", "copy-summary", "", "copy")}${button("Scenario JSON", "export-json", "", "file")}${button("Equity-band CSV", "export-csv", "", "download")}<a href="/api/orb/download/dossier.pdf" download>${icon("book")}Forensic dossier · PDF</a></div></div>`;
}

function pageHead(eyebrow, title, subtitle, actions = "") {
  return `<div class="page-head"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p class="page-description">${subtitle}</p></div><div class="head-actions">${actions}</div></div>`;
}
function warning() {
  return `<div class="callout">${icon("shield")}<div><strong>Research, not live performance.</strong> This model is not a historical ES/MES backtest. Actual strategy results remain unverified.</div><button class="text-link" data-action="audit">Why this matters ${icon("arrow")}</button></div>`;
}
function stat(label, value, unit, foot, metric = "", tone = "", small = false) {
  return `<article class="stat-card"><div class="stat-heading"><span>${label}</span>${metric ? info(metric) : ""}</div><div class="stat-value ${tone} ${small ? "small-value" : ""}">${value}${unit ? `<span class="unit">${unit}</span>` : ""}</div><div class="stat-foot"><span class="mini-dot ${tone === "negative" ? "coral" : tone ? "" : "gray"}"></span>${foot}</div></article>`;
}
function statCards(result, compact = false) {
  const m = result.metrics;
  return `<div class="stat-grid">${stat("Net expectancy", signed(m.net_expectancy_r), "R", "Per trade · after modeled costs", "expectancy", m.net_expectancy_r > 1e-10 ? "positive" : m.net_expectancy_r < -1e-10 ? "negative" : "")}${stat("Target-hit rate", number(m.pass_pct), "%", `${number(m.passed, 0)} of ${number(result.n_paths, 0)} paths`, "target", "positive")}${stat("Floor-breach rate", number(m.breach_pct), "%", `${number(m.breached, 0)} paths reached the floor`, "breach", "negative")}${compact ? "" : stat("95th-percentile drawdown", number(m.dd95_pct), "%", "Closing equity · stopped paths", "dd95")}</div>`;
}
function modelChartCard(result, compact = false) {
  const m = result.metrics,
    mode = state.chartMode;
  return `<section class="card"><div class="card-head"><div><h2>${mode === "equity" ? "Simulated equity paths" : "Simulated drawdown paths"}</h2><p class="card-subtitle">Pointwise percentiles · ${number(result.n_paths, 0)} hypothetical accounts</p></div><div class="segmented" aria-label="Chart measure"><button class="${mode === "equity" ? "active" : ""}" data-action="chart-mode" data-mode="equity" aria-pressed="${mode === "equity"}">Equity</button><button class="${mode === "drawdown" ? "active" : ""}" data-action="chart-mode" data-mode="drawdown" aria-pressed="${mode === "drawdown"}">Drawdown</button></div></div><div class="chart-meta"><strong>${mode === "equity" ? money(m.median_ending_equity) : pct(m.median_max_dd_pct)}</strong><span class="${mode === "equity" && m.median_return_pct < 0 ? "negative" : ""}">${mode === "equity" ? signed(m.median_return_pct) + "%" : ""}</span><span class="muted">${mode === "equity" ? "median ending equity" : "median maximum drawdown"}</span></div><div class="chart-host" data-chart="model"></div><div class="chart-legend"><span class="legend-item"><span class="legend-line" ${mode === "drawdown" ? 'style="background:#d97e67"' : ""}></span>Pointwise median</span><span class="legend-item"><span class="legend-band" ${mode === "drawdown" ? 'style="background:#fae8e2;border-color:#edcbbf"' : ""}></span>5th–95th percentile</span>${mode === "equity" ? '<span class="legend-item"><span class="legend-dashed"></span>Account boundaries</span>' : ""}</div><div class="card-note">${icon("info")}Hypothetical, pointwise bands—not a historical equity curve or simultaneous confidence region. Paths stop at the boundaries; future drawdown is censored.</div></section>`;
}
function assumptionsCard(result) {
  const s = result.params,
    m = result.metrics;
  return `<aside class="card assumptions-card"><div class="card-head"><div><h2>Inside the model</h2><p class="card-subtitle">The assumptions behind every result</p></div>${tag("ILLUSTRATIVE", "dark-tag")}</div><div class="card-body"><div class="assumption-row"><span>Assumed win probability</span><strong>${pct(s.win_rate, 0)}</strong></div><div class="assumption-row"><span>Risk per modeled trade</span><strong>${pct(s.risk_pct)}</strong></div><div class="assumption-row"><span>Trade activity</span><strong>${pct(s.activity_pct, 0)} of sessions</strong></div><div class="assumption-row"><span>Stop / target distance</span><strong>${number(s.stop_atr, 1)} / ${number(s.target_atr, 1)} ATR</strong></div><div class="assumption-row"><span>Round-trip costs</span><strong>${number(s.cost_r)}R</strong></div><div class="assumption-row"><span>Starting equity · horizon</span><strong>${money(s.initial_equity)} · ${s.sessions}d</strong></div><div class="payoff-strip"><span></span><span style="flex:${m.gross_win_r}"></span></div><div class="payoff-labels"><span>Gross loss <strong>−1R</strong></span><span>Gross target <strong>+${number(m.gross_win_r)}R</strong></span></div><div class="break-even-line"><span>Net break-even win rate</span><strong>${pct(m.breakeven_pct)}</strong>${info("breakeven")}</div>${button("Edit assumptions", "go-lab", "light wide", "settings")}<p class="assumptions-foot">Chosen inputs. Not fitted from ES/MES trades.</p></div></aside>`;
}
function outcomeCard(result) {
  const m = result.metrics;
  return `<section class="card"><div class="card-head"><div><h2>Every account outcome counts</h2><p class="card-subtitle">What happened within ${result.params.sessions} modeled sessions</p></div>${tag("MODEL", "model")}</div><div class="outcome-body"><div class="donut">${donutMarkup(result)}</div><div class="outcome-list">${[
    ["Target reached", m.pass_pct, m.passed, "#168b76"],
    ["Floor breached", m.breach_pct, m.breached, "#d97e67"],
    ["Still unresolved", m.unresolved_pct, m.unresolved, "#cdd9df"],
  ]
    .map(
      ([label, v, count, color]) =>
        `<div class="outcome-item"><span class="dot" style="background:${color}"></span><span>${label}</span><strong>${pct(v)}</strong><small>${number(count, 0)} paths</small></div>`,
    )
    .join(
      "",
    )}<p class="outcome-note">Unresolved is not failed. Low risk can mean a longer time to the target.</p></div></div></section>`;
}
function validationCard() {
  return `<section class="card"><div class="card-head"><div><h2>The evidence checkpoint</h2><p class="card-subtitle">What stands between research and execution</p></div>${tag("NOT LIVE-VALIDATED", "warning")}</div><div class="validation-rows">${state.data.validation.map((v) => `<div class="validation-row"><span class="validation-icon ${v.done ? "complete" : ""}">${v.done ? icon("check") : "·"}</span><span>${esc(v.title)}</span>${tag(esc(v.status), v.done ? "model" : v.status === "Blocked" ? "critical" : "")}</div>`).join("")}</div><div class="validation-footer"><button class="text-link" data-action="audit">Explore the execution audit ${icon("arrow")}</button></div></section>`;
}
function publishedTable(rows, sortable = false) {
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>STUDY / IMPLEMENTATION</th><th>ASSET</th><th class="num">${sortable ? `<button class="sort-button" data-action="sort" data-key="annual">ANNUAL RETURN ${icon("chevron")}</button>` : "ANNUAL RETURN"}</th><th class="num">${sortable ? `<button class="sort-button" data-action="sort" data-key="sharpe">SHARPE ${icon("chevron")}</button>` : "SHARPE"}</th><th class="num">${sortable ? `<button class="sort-button" data-action="sort" data-key="mdd">MAX DD ${icon("chevron")}</button>` : "MAX DD"}</th><th>SOURCE</th></tr></thead><tbody>${rows.map((r) => `<tr><td><div class="strategy-name"><span class="asset-square ${r.source === 2 ? "violet" : ""}">${r.source === 1 ? "SIP" : r.instrument}</span><span>${esc(r.name)}<small>${r.sample} · ${esc(r.family)}</small></span></div></td><td>${esc(r.instrument)}</td><td class="num"><span>${pct(r.annual, 1)}</span><small>Author’s ${r.annual_label}</small></td><td class="num">${number(r.sharpe)}</td><td class="num negative">${pct(r.mdd, 0)}</td><td><button class="text-link" data-action="source" data-id="${r.source}">[${r.source}] SSRN ${icon("external")}</button></td></tr>`).join("")}</tbody></table></div>`;
}
function renderOverview() {
  const r = state.result,
    s = r.params;
  return `${pageHead('STRATEGY 01 <span class="tag">ORB-30R v0.1</span>', "Opening Range Breakout", "A clear view of the setup, the evidence, and the risk.", button("Research dossier", "report", "", "book") + exportMenu())}${warning()}<div class="market-overview-link"><span>New: inspect actual source candles separately from the scenario model.</span><a class="text-link" href="#market">Market data & replay →</a></div><div class="section-label"><span>SCENARIO SNAPSHOT ${tag("ILLUSTRATIVE", "model")}</span><span class="fine">${number(r.n_paths, 0)} paths <span>·</span> ${s.sessions} sessions <span>·</span> Seed ${s.seed}</span></div>${statCards(r)}<div class="analysis-grid">${modelChartCard(r)}${assumptionsCard(r)}</div><div class="two-grid">${outcomeCard(r)}${validationCard()}</div><section class="card table-card"><div class="card-head"><div><h2>What published research reports</h2><p class="card-subtitle">Different instruments and rules. These are not results for our ES/MES prototype.</p></div><button class="text-link" data-action="go-research">Explore the evidence ${icon("arrow")}</button></div>${publishedTable(state.data.published.filter((_, i) => [1, 2, 3, 6].includes(i)))}<div class="card-note">${icon("info")}Author-reported, not independently replicated. Annual-return labels and samples differ; QQQ prose/table discrepancies are retained in the research notes.</div></section>`;
}
function rangeControl(key, label, min, max, step, unit = "", digits = 0) {
  return `<div class="control"><div class="control-top"><label for="param-${key}">${label}</label><output class="control-value" id="value-${key}">${number(state.draft[key], digits)}${unit}</output></div><input type="range" id="param-${key}" data-param="${key}" data-unit="${unit}" data-digits="${digits}" min="${min}" max="${max}" step="${step}" value="${state.draft[key]}"><div class="range-ends"><span>${min}${unit}</span><span>${max}${unit}</span></div></div>`;
}
function numberControl(key, label, min, max, step = 1) {
  return `<div><label class="field-label" for="param-${key}">${label}</label><input class="input" id="param-${key}" data-param="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${state.draft[key]}" required></div>`;
}
function selectControl(key, label, options) {
  return `<div><label class="field-label" for="param-${key}">${label}</label><select class="select" id="param-${key}" data-param="${key}">${options.map(([value, text]) => `<option value="${value}" ${String(state.draft[key]) === String(value) ? "selected" : ""}>${text}</option>`).join("")}</select></div>`;
}
function heatmapCard() {
  const metric = state.heatMetric,
    max = Math.max(...state.data.saved.grid.map((g) => g[metric]));
  const baseGeometry = Object.keys(defaults)
    .filter((k) => !["win_rate", "risk_pct"].includes(k))
    .every((k) => state.result.params[k] === defaults[k]);
  return `<section class="card"><div class="card-head"><div><h2>Risk sensitivity</h2><p class="card-subtitle">Saved baseline grid · select a cell to run it</p></div><select class="small-select" id="heat-metric" aria-label="Sensitivity measure"><option value="pass_pct" ${metric === "pass_pct" ? "selected" : ""}>Target hit</option><option value="breach_pct" ${metric === "breach_pct" ? "selected" : ""}>Breach</option><option value="unresolved_pct" ${metric === "unresolved_pct" ? "selected" : ""}>Unresolved</option></select></div><div class="card-body"><div class="heatmap"><span>Win p.</span><span>0.25% risk</span><span>0.50% risk</span><span>0.75% risk</span>${[
    35, 40, 45, 50,
  ]
    .map(
      (p) =>
        `<span class="heat-row-label">${p}%</span>${[0.25, 0.5, 0.75]
          .map((f) => {
            const g = state.data.saved.grid.find(
                (g) =>
                  Math.abs(g.win_probability * 100 - p) < 0.01 &&
                  Math.abs(g.risk_fraction * 100 - f) < 0.001,
              ),
              v = g[metric],
              ratio = v / max;
            const rgb =
              metric === "breach_pct" ? [188, 104, 81] : [30, 127, 107];
            const bg = rgb.map((c) => Math.round(243 + (c - 243) * ratio));
            return `<button class="heat-cell ${baseGeometry && Math.abs(state.result.params.win_rate - p) < 0.001 && Math.abs(state.result.params.risk_pct - f) < 0.001 ? "selected" : ""}" data-action="heat-cell" data-p="${p}" data-f="${f}" style="background:rgb(${bg.join(",")});color:${readableColor(bg)}" title="Assumed ${p}% wins, ${f}% risk: ${pct(v)} ${metric.replaceAll("_", " ")}">${pct(v, 1)}</button>`;
          })
          .join("")}`,
    )
    .join(
      "",
    )}</div><div class="heat-key"><span>Lower</span><span></span><span>Higher</span></div><p class="field-help">Fixed 60 sessions, 0.10R costs, 60% activity and a static 8% floor. Not a live sizing recommendation.</p></div></section>`;
}
function stressCard() {
  return `<section class="card"><div class="card-head"><div><h2>Stress the same starting assumptions</h2><p class="card-subtitle">Saved dossier scenarios · 45% assumed wins, 0.50% risk, 60 sessions</p></div><a class="text-link" href="/api/orb/download/stress.csv" download>CSV ${icon("download")}</a></div><div class="stress-chart">${state.data.saved.stress.map((s, i) => `<button class="stress-row" data-action="stress-preset" data-preset="${presetIds[i]}" title="Load ${esc(s.name)} and run the scenario"><span>${["Independent base", "Clustered losses", "Higher costs", "Trailing floor", "Rare 3R loss", "Fewer signals", "Combined adverse"][i]}</span><span class="stacked-bar"><span style="width:${s.pass_pct}%;background:#168b76"></span><span style="width:${s.breach_pct}%;background:#d97e67"></span><span style="width:${s.unresolved_pct}%;background:#dfe7eb"></span></span><strong>${pct(s.pass_pct, 1)}</strong></button>`).join("")}</div><div class="chart-legend"><span class="legend-item"><span class="mini-dot"></span>Target hit</span><span class="legend-item"><span class="mini-dot coral"></span>Floor breach</span><span class="legend-item"><span class="mini-dot gray"></span>Unresolved</span></div><div class="card-note">Clustering can increase both passes and breaches. Optimizing pass rate alone hides the cost of failure.</div></section>`;
}
function renderLab() {
  const r = state.result,
    m = r.metrics;
  return `${pageHead("THE ASSUMPTION LAB", "Stress-test the possibilities", "Change an input. Watch both sides of the outcome—not just the chance of a pass.", exportMenu())}${warning()}<div class="lab-layout"><form class="card lab-controls" id="lab-form"><div class="card-head"><h2>Model inputs</h2>${button("Reset", "reset-scenario", "ghost small", "refresh")}</div><div class="card-body"><div class="control preset-control"><label class="field-label" for="lab-preset">Start from a stress preset</label><select class="select" id="lab-preset">${Object.entries(
    PRESETS,
  )
    .map(
      ([key, p]) =>
        `<option value="${key}" ${state.activePreset === key ? "selected" : ""}>${p.label}</option>`,
    )
    .join(
      "",
    )}${state.activePreset === "custom" ? '<option value="custom" selected>Custom assumptions</option>' : ""}</select></div>${rangeControl("win_rate", "Assumed gross win rate", 25, 75, 1, "%", 0)}${rangeControl("risk_pct", "Equity risk per trade", 0.05, 2, 0.05, "%", 2)}${rangeControl("cost_r", "Round-trip cost per trade", 0, 0.5, 0.01, "R", 2)}${rangeControl("activity_pct", "Sessions with one trade", 10, 100, 5, "%", 0)}<div class="form-divider"></div><div class="field-row">${numberControl("stop_atr", "Stop (× ATR)", 0.5, 4, 0.1)}${numberControl("target_atr", "Target (× ATR)", 0.5, 8, 0.1)}</div><div class="field-row">${selectControl(
    "sessions",
    "Session horizon",
    [
      [30, "30 sessions"],
      [60, "60 sessions"],
      [90, "90 sessions"],
      [120, "120 sessions"],
    ],
  )}${selectControl("floor", "Loss floor", [
    ["static", "Static floor"],
    ["trailing", "Trailing dollars"],
  ])}</div><details class="control-disclosure"><summary>Account & stress details</summary><div><div class="field-row">${numberControl("target_pct", "Target (%)", 1, 20, 0.5)}${numberControl("loss_limit_pct", "Loss allowance (%)", 1, 20, 0.5)}</div><div class="control">${numberControl("initial_equity", "Starting equity ($)", 1000, 10000000, 1000)}</div><div class="field-row">${numberControl("gap_probability_pct", "Gaps (% of losers)", 0, 5, 0.5)}${numberControl("gap_loss_r", "Gap loss (R)", 1, 10, 0.5)}</div><p class="field-help">Loss after a loss: ${state.draft.loss_persistence === null ? "independent" : pct(state.draft.loss_persistence * 100, 0)}. Choose the clustering preset to model dependence. Seed ${state.draft.seed}; 20,000 paths.</p></div></details><p class="draft-status ${state.dirty ? "changed" : ""}" id="draft-status">${state.dirty ? "Changed inputs · run to update the results" : "Results match these inputs"}</p><button class="button primary wide" type="submit" id="run-scenario" ${state.running ? "disabled" : ""}>${state.running ? blank : icon("lab")}${state.running ? "Running scenario…" : "Run scenario"}</button><p class="run-meta">${state.lastRun ? "Computed in " + state.lastRun.toFixed(2) + "s · " : ""}No market data. No orders. No optimization.</p></div></form><div class="lab-results"><div class="section-label"><span>LAST COMPLETED SCENARIO ${tag("ILLUSTRATIVE", "model")}</span><span class="fine">${r.params.sessions} sessions · ${number(r.n_paths, 0)} paths</span></div>${statCards(r, true)}${modelChartCard(r, true)}<div class="two-grid">${heatmapCard()}<section class="card"><div class="card-head"><div><h2>Where accounts finish</h2><p class="card-subtitle">All stopped paths, not just the winners</p></div></div><div class="chart-host chart-inset" data-chart="histogram"></div><div class="card-note">Median ${money(m.median_ending_equity)} · ${pct(m.unresolved_pct)} unresolved.</div></section></div><section class="card"><div class="mini-stats"><div class="mini-stat"><span>Pass time · conditional</span><strong>${m.median_days_if_pass === null ? "Not observed" : number(m.median_days_if_pass, 0) + " sessions"}</strong></div><div class="mini-stat"><span>95th pct. max drawdown</span><strong>${pct(m.dd95_pct)}</strong></div><div class="mini-stat"><span>Pass-rate MC interval</span><strong>${pct(m.pass_ci[0])}–${pct(m.pass_ci[1])}</strong></div><div class="mini-stat"><span>Net break-even win rate</span><strong>${pct(m.breakeven_pct)}</strong></div><div class="mini-stat"><span>Net win / ordinary loss</span><strong>${signed(m.net_win_r)}R / ${signed(m.net_ordinary_loss_r)}R</strong></div><div class="mini-stat"><span>Median modeled trade count</span><strong>${number(m.median_trades, 0)} trades</strong></div></div><div class="card-note">Intervals measure simulation sampling error only—not model uncertainty. Real win probability can change when stop/target geometry changes.</div></section></div></div>${stressCard()}`;
}
function timeframeCard() {
  const key = state.timeframeMetric || "sharpe_reported";
  const rows = state.data.registry.sources[0].facts.timeframes,
    max = Math.max(...rows.map((r) => r[key]));
  return `<section class="card"><div class="card-head"><div><h2>Timing changes the result</h2><p class="card-subtitle">Stocks-in-Play selection · source [1], Table 3</p></div><select id="timeframe-metric" class="small-select" aria-label="Published timeframe metric"><option value="sharpe_reported" ${key === "sharpe_reported" ? "selected" : ""}>Sharpe</option><option value="irr_pct" ${key === "irr_pct" ? "selected" : ""}>IRR</option><option value="mdd_pct" ${key === "mdd_pct" ? "selected" : ""}>Max drawdown</option></select></div><div class="card-body">${rows.map((r) => `<div class="timeframe-row"><span>${r.minutes} min</span><span class="timeframe-track"><span style="width:${(r[key] / max) * 100}%;background:${r.minutes === 30 ? "#d49179" : "#68b5a0"}"></span></span><strong>${number(r[key], key === "sharpe_reported" ? 2 : 1)}${key === "sharpe_reported" ? "" : "%"}</strong></div>`).join("")}<div class="method-note">The 30-minute stock variant reported Sharpe <strong>0.21</strong> and <strong>35% maximum drawdown</strong>. That is a warning against treating all opening windows as equivalent—not a result for ES.</div></div></section>`;
}
function sourceCards() {
  const query = state.sourceQuery.toLowerCase();
  const list = state.data.registry.sources.filter((s) =>
    [s.title, s.authors, s.ssrn || "", s.id]
      .join(" ")
      .toLowerCase()
      .includes(query),
  );
  return list.length
    ? list
        .map(
          (s) =>
            `<article class="card source-card"><div class="source-number"><span>SOURCE ${String(s.id).padStart(2, "0")}</span>${tag(s.ssrn ? "SSRN " + s.ssrn : s.id === 12 ? "SUPPLEMENTARY" : "OFFICIAL", s.ssrn ? "reported" : "")}</div><h3>${esc(s.title)}</h3><p>${esc(s.authors)}<br>${esc(s.year)}</p><button class="text-link" data-action="source" data-id="${s.id}">Methods & limitations ${icon("arrow")}</button></article>`,
        )
        .join("")
    : `<div class="method-note">No sources match “${esc(state.sourceQuery)}”. Try an author, title, or SSRN number.</div>`;
}
function renderResearch() {
  let rows = state.data.published.filter(
    (r) =>
      state.researchFilter === "all" ||
      r.source === Number(state.researchFilter),
  );
  if (state.sortKey)
    rows = [...rows].sort(
      (a, b) =>
        (a[state.sortKey] - b[state.sortKey]) * (state.sortDesc ? -1 : 1),
    );
  return `${pageHead("THE EVIDENCE, IN CONTEXT", "Research & evidence", "Published findings are a starting point for replication, not a substitute for it.", button("Read the full dossier", "report", "", "book"))}<div class="callout blue">${icon("book")}<div><strong>Author-reported results.</strong> Instruments, samples, leverage, costs and return labels differ. None validates the proposed ES/MES strategy.</div></div><div class="research-tabs" aria-label="Filter published studies">${[
    ["all", "All studies"],
    ["1", "Stocks in Play"],
    ["2", "QQQ / TQQQ"],
    ["3", "SPY momentum"],
  ]
    .map(
      ([id, label]) =>
        `<button class="filter-pill ${state.researchFilter === id ? "active" : ""}" data-action="research-filter" data-id="${id}" aria-pressed="${state.researchFilter === id}">${label}</button>`,
    )
    .join(
      "",
    )}<span style="margin-left:auto">${tag("REPORTED · NOT REPLICATED", "reported")}</span></div><section class="card table-card"><div class="card-head"><div><h2>Published strategy results</h2><p class="card-subtitle">Retained under each paper’s labels · click a source to inspect its method</p></div></div>${publishedTable(rows, true)}<div class="card-note">QQQ Table 2 says “Yearly Return” 33%; its prose says annualized 31%. Exact drawdown dates are unavailable. Do not silently compare unlike measures.</div></section><div class="research-grid">${timeframeCard()}<section class="card"><div class="card-head"><div><h2>A headline worth checking</h2><p class="card-subtitle">QQQ optimized variant · source [2], Section 4</p></div>${tag("ARITHMETIC AUDIT", "warning")}</div><div class="card-body"><div class="inline-stat-row"><div>Reported return<strong>9,350%</strong></div><div>Reported ending value<strong>$6.4m</strong></div></div><div class="notice-box"><h3>These figures do not reconcile.</h3><p>$25,000 × (1 + 93.50) = <strong>$2,362,500</strong>, not $6.4 million. Growing $25,000 to $6.4 million implies <strong>25,500%</strong>.</p><p>This may be an editing or calculation issue. The zero-slippage optimized headline is not a planning input until reconciled.</p></div><button class="text-link section-gap" data-action="source" data-id="2">Read the source notes ${icon("arrow")}</button></div></section></div><div class="sources-toolbar"><div><h2>The source library <span class="muted">/ 15</span></h2><p class="card-subtitle">Access depth and transfer limits are documented for every reference.</p></div><div class="search-input-wrap">${icon("search")}<input class="input" id="source-search" aria-label="Search sources" placeholder="Search sources or authors" value="${esc(state.sourceQuery)}"></div></div><div class="source-list" id="source-list">${sourceCards()}</div><section class="card section-gap" id="execution-audit"><div class="card-head"><div><h2>Why the legacy results were withdrawn</h2><p class="card-subtitle">Audit of the 08 Sep 2026 snapshot. These defects have not been repaired by building this dashboard.</p></div>${tag("EXECUTION AUDIT", "critical")}</div><div class="card-body">${state.data.audit.map((a) => `<details class="audit-item"><summary>${tag(a.severity, a.severity === "Critical" ? "critical" : "warning")}<span>${esc(a.title)}</span>${icon("chevron")}</summary><p>${esc(a.detail)}</p><code>${esc(a.file)}</code></details>`).join("")}</div></section>`;
}
function missingMetrics() {
  return `<div class="available-metrics">${[
    ["Historical Sharpe", "Needs a complete daily equity series"],
    ["Intraday drawdown", "Needs floating-equity marks"],
    ["Firm pass probability", "Needs exact rules and calibrated data"],
    ["Live win rate", "No verified broker connection"],
  ]
    .map(
      ([label, note]) =>
        `<div class="unavailable-card"><div>${label}</div><strong>—</strong><small>${note}</small></div>`,
    )
    .join("")}</div>`;
}
function entryDate(value) {
  return new Date(value).toLocaleString("en-GB", {
    timeZone: "America/New_York",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}
function ledgerTable() {
  const all = state.ledger.trades.filter(
    (t) =>
      (state.ledgerSide === "all" || t.side === state.ledgerSide) &&
      [t.symbol, t.side, t.entry_time, t.exit_time]
        .join(" ")
        .toLowerCase()
        .includes(state.ledgerQuery.toLowerCase()),
  );
  const pages = Math.ceil(all.length / 20);
  state.ledgerPage = Math.min(state.ledgerPage, Math.max(0, pages - 1));
  const start = state.ledgerPage * 20,
    rows = all.slice(start, start + 20);
  return `<div class="table-wrap"><table class="data-table"><thead><tr><th>TRADE</th><th>ENTRY · NEW YORK</th><th>SIDE</th><th class="num">QTY</th><th class="num">ENTRY / EXIT</th><th class="num">FEES</th><th class="num">NET P&L</th><th class="num">NET R</th></tr></thead><tbody>${rows.map((t) => `<tr><td><strong>#${String(t.id).padStart(3, "0")}</strong><small>${esc(t.symbol)}</small></td><td>${entryDate(t.entry_time)}</td><td>${tag(t.side, t.side === "LONG" ? "model" : "reported")}</td><td class="num">${t.quantity}</td><td class="num">${number(t.entry_price)}<small>${number(t.exit_price)}</small></td><td class="num">${money(t.fees, 2)}</td><td class="num ${t.net_pnl >= 0 ? "positive" : "negative"}">${t.net_pnl > 0 ? "+" : ""}${money(t.net_pnl, 2)}</td><td class="num ${t.r_multiple >= 0 ? "positive" : "negative"}">${signed(t.r_multiple)}R</td></tr>`).join("") || '<tr><td colspan="8">No trades match this filter.</td></tr>'}</tbody></table></div><div class="pager"><span>Showing ${all.length ? start + 1 : 0}–${Math.min(start + 20, all.length)} of ${all.length} trades</span><div>${button("Previous", "prev-trades", "small", "left", state.ledgerPage === 0 ? "disabled" : "")}${button("Next", "next-trades", "small", "right", state.ledgerPage + 1 >= pages ? "disabled" : "")}</div></div>`;
}
function drawdownTable() {
  const l = state.ledger;
  const label = (i) =>
    i === 0 ? "Initial equity" : entryDate(l.trades[i - 1].exit_time);
  return `<section class="card table-card section-gap"><div class="card-head"><div><h2>Drawdown episodes</h2><p class="card-subtitle">Trade-close marks only. Unrecovered episodes are retained, not excluded.</p></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>PEAK</th><th>TROUGH</th><th>RECOVERY</th><th class="num">DEPTH</th><th class="num">DURATION</th></tr></thead><tbody>${l.episodes.map((e) => `<tr><td>${label(e.peak)}</td><td>${label(e.trough)}</td><td>${e.recovery === null ? tag("Unrecovered", "warning") : label(e.recovery)}</td><td class="num negative">${pct(e.depth_pct)}</td><td class="num">${e.recovery === null ? "≥ " : ""}${e.duration} closed trades</td></tr>`).join("") || '<tr><td colspan="5">No closing-trade drawdown observed in this file. This does not establish zero intraday loss.</td></tr>'}</tbody></table></div></section>`;
}
function renderTrades() {
  const l = state.ledger;
  const hiddenInput =
    '<input type="file" id="trade-file" accept=".csv,text/csv" hidden>';
  if (!l)
    return `${pageHead("YOUR DATA, NOT A DEMO BACKTEST", "Trade analytics", "Bring your closed trades. Calculate the metrics that your records actually support.", button("CSV template", "template", "", "download"))}${hiddenInput}<div class="callout blue">${icon("info")}<div><strong>No trade records connected.</strong> Historical performance is unavailable until you supply a ledger. Imported files are processed in memory, not saved to the server.</div></div><section class="card empty-ledger"><div class="empty-illustration">${icon("trades")}</div><h2>What does your ORB actually return?</h2><p>Import an ES/MES trade CSV to calculate net P&L, win rate, profit factor, R expectancy and closing-trade drawdowns. No invented live statistics.</p><div class="button-group">${button(state.importing ? "Analyzing…" : "Import trade CSV", "import", "primary", "upload", state.importing ? "disabled" : "")}${button("Try a fictional sample", "sample", "", "layers", state.importing ? "disabled" : "")}</div><div class="drop-zone" id="drop-zone">${icon("upload")}<div>Or drop your CSV here</div><p>Up to 1 MB / 5,000 trades · ES or MES · timestamps with UTC offsets</p></div><button class="text-link" data-action="template">Download the required CSV template ${icon("download")}</button><div class="import-equity"><label class="field-label" for="import-equity">Starting account equity ($)</label><input class="input" id="import-equity" type="number" min="1000" max="10000000" step="1000" value="${state.initialEquity}" required><p class="field-help">Used to reconstruct equity. Assumes no deposits or withdrawals.</p></div></section>${missingMetrics()}`;
  const m = l.metrics,
    example = l.evidence === "ILLUSTRATIVE";
  return `${pageHead(example ? "FICTIONAL EXAMPLE LEDGER" : "USER-SUPPLIED TRADE RECORDS", "Your results, reconciled", `${esc(state.filename)} · ${m.count} closed trades · starting equity ${money(l.initial_equity)}`, button("Replace CSV", "import", "", "upload") + button("Export ledger", "export-ledger", "", "download") + button("Clear", "clear-ledger", "ghost"))}${hiddenInput}<div class="callout ${example ? "" : "blue"}">${icon(example ? "warning" : "info")}<div><strong>${example ? "Fictional sample—not actual market trades." : "User-supplied—not independently verified."}</strong> Closing-trade analysis does not validate ORB signals, intraday compliance or broker execution.</div></div><div class="stat-grid">${stat("Net P&L", (m.net_pnl > 0 ? "+" : "") + money(m.net_pnl, 2), "", `${signed(m.total_return_pct)}% · fees included`, "pnl", m.net_pnl >= 0 ? "positive" : "negative", true)}${stat("Trade win rate", number(m.win_rate), "%", `${m.wins} wins · ${m.losses} losses · ${m.scratches} scratches`, "winrate")}${stat("Profit factor", number(m.profit_factor), "", m.profit_factor_note || "Net profits ÷ net losses", "pf")}${stat("Net expectancy", signed(m.expectancy_r), "R", "Fixed initial-risk denominator", "expectancy", m.expectancy_r >= 0 ? "positive" : "negative")}</div><section class="card"><div class="card-head"><div><h2>Closing-trade ${state.ledgerMode === "equity" ? "equity" : "drawdown"}</h2><p class="card-subtitle">${example ? "Fictional example" : "Imported records"} · actual CSV fills, fees counted once</p></div><div class="segmented"><button class="${state.ledgerMode === "equity" ? "active" : ""}" data-action="ledger-mode" data-mode="equity">Equity</button><button class="${state.ledgerMode === "drawdown" ? "active" : ""}" data-action="ledger-mode" data-mode="drawdown">Drawdown</button></div></div><div class="mini-stats"><div class="mini-stat"><span>Ending equity</span><strong>${money(m.ending_equity)}</strong></div><div class="mini-stat"><span>Max closing-trade DD</span><strong>${pct(m.max_closing_dd_pct)}</strong></div><div class="mini-stat"><span>Longest losing streak</span><strong>${m.longest_loss_streak} trades</strong></div></div><div class="chart-host" data-chart="ledger"></div><div class="card-note">This curve omits open P&L and external cash flows. It cannot certify intraday drawdown or account-rule compliance.</div></section><section class="card table-card section-gap"><div class="card-head"><div><h2>Closed trade ledger</h2><p class="card-subtitle">${money(m.fees, 2)} total fees · ${tag(example ? "ILLUSTRATIVE" : "USER-SUPPLIED", example ? "warning" : "user")}</p></div><div class="table-tools"><div class="search-input-wrap">${icon("search")}<input class="input" id="trade-search" placeholder="Search trades" aria-label="Search trades" value="${esc(state.ledgerQuery)}"></div><select id="trade-side" class="small-select" aria-label="Filter direction"><option value="all">All directions</option><option value="LONG" ${state.ledgerSide === "LONG" ? "selected" : ""}>Long</option><option value="SHORT" ${state.ledgerSide === "SHORT" ? "selected" : ""}>Short</option></select></div></div><div id="ledger-table">${ledgerTable()}</div></section>${drawdownTable()}${missingMetrics()}`;
}
function renderRules() {
  return `${pageHead("A CAUSAL RESEARCH SPECIFICATION", "Strategy rulebook", "ORB-30R v0.1 · proposed, not optimized. The calculator below never places an order.", button("Read methodology", "report", "", "book"))}<div class="callout">${icon("shield")}<div><strong>Frozen is not optimal.</strong> The 30-minute window, EMA filter and 1.2 / 2.0 ATR bracket still require real-data validation.</div></div><div class="rules-grid"><section class="card"><div class="card-head"><div><h2>The baseline, without ambiguity</h2><p class="card-subtitle">Information first. Orders afterward.</p></div>${tag("PROPOSED", "model")}</div><div class="card-body">${state.data.rules.map(([label, value, detail], i) => `<div class="rule-row"><span class="rule-number">${String(i + 1).padStart(2, "0")}</span><div><h3>${label}<strong>${value}</strong></h3><p>${detail}</p></div></div>`).join("")}</div></section><div><section class="card"><div class="card-head"><div><h2>New York session, Nairobi clock</h2><p class="card-subtitle">Daylight-saving-aware clock conversion</p></div>${icon("clock")}</div><div class="card-body"><label class="field-label" for="session-date">Session date</label><input type="date" class="input" id="session-date" value="${state.sessionDate || "2026-09-08"}"><div id="session-plan" class="time-table">${blank}</div><p class="field-help">Clock conversion only. Verify exchange holidays, early closes and your broker’s daily-risk reset separately.</p></div></section><form class="card section-gap" id="sizing-form"><div class="card-head"><div><h2>Size for real contracts</h2><p class="card-subtitle">Floor-rounded ES / MES risk arithmetic</p></div>${tag("ILLUSTRATIVE INPUTS", "model")}</div><div class="card-body"><div class="field-row"><div><label class="field-label" for="size-instrument">Instrument</label><select class="select" id="size-instrument" name="instrument"><option value="MES">MES · $5 / point</option><option value="ES">ES · $50 / point</option></select></div><div><label class="field-label" for="size-budget">Risk budget ($)</label><input class="input" id="size-budget" name="budget" type="number" min="1" max="1000000" value="500" required></div></div><div class="field-row"><div><label class="field-label" for="size-atr">ATR (points)</label><input class="input" id="size-atr" name="atr" type="number" min=".01" max="1000" step=".01" value="5" required></div><div><label class="field-label" for="size-stop">Stop (× ATR)</label><input class="input" id="size-stop" name="stop_atr" type="number" min=".1" max="10" step=".1" value="1.2" required></div></div><div class="field-row"><div><label class="field-label" for="size-fees">Round-trip fees / contract ($)</label><input class="input" id="size-fees" name="fees" type="number" min="0" max="500" step=".01" value="2" required></div><div><label class="field-label" for="size-slippage">Slippage reserve (total ticks)</label><input class="input" id="size-slippage" name="slippage_ticks" type="number" min="0" max="100" step="1" value="2" required></div></div><button class="button primary wide" type="submit">${icon("settings")}Calculate position size</button><div id="sizing-result"></div><p class="field-help">Use a budget within your remaining daily and total cushion. Fees are editable examples; reserves do not cap gap losses.</p></div></form></div></div>`;
}
function notesMarkup() {
  if (state.notes === null)
    return `<div class="card note-empty">${blank}<p>Loading your saved research notes…</p></div>`;
  const notes = state.notes.filter((n) =>
    [n.title, n.body, n.category, n.session_date]
      .join(" ")
      .toLowerCase()
      .includes(state.noteQuery.toLowerCase()),
  );
  if (!notes.length)
    return `<div class="card note-empty">${icon("journal")}<h3>${state.noteQuery ? "No matching notes" : "A clean page for honest research"}</h3><p>${state.noteQuery ? "Try another title, date or keyword." : "Record an observation, an execution question or a validation decision. No fictional trades have been added to this journal."}</p></div>`;
  return notes
    .map(
      (n) =>
        `<article class="card note-card"><div class="note-card-head"><div>${tag(esc(n.category), n.category === "Risk" ? "warning" : "model")} <time datetime="${esc(n.session_date)}">${esc(n.session_date)}</time></div><button class="icon-button" data-action="delete-note" data-id="${n.id}" aria-label="Delete note ${esc(n.title)}">${icon("trash")}</button></div><h3>${esc(n.title)}</h3><p>${esc(n.body)}</p></article>`,
    )
    .join("");
}
function renderJournal() {
  return `${pageHead("THE RESEARCH RECORD", "Journal & review", "Capture what you observed, what you changed, and what still needs evidence.", button("Export notes", "export-notes", "", "download"))}<div class="callout neutral">${icon("journal")}<div><strong>Saved workspace notes, not broker records.</strong> The earlier journal’s account balances and trades were demonstrations. Actual capital and challenge progress remain unknown.</div></div><div class="journal-layout"><form class="card journal-form" id="note-form"><div class="card-head"><h2>New research note</h2>${icon("plus")}</div><div class="card-body"><div class="control"><label class="field-label" for="note-title">Title</label><input class="input" id="note-title" name="title" maxlength="120" placeholder="What did you investigate?" required></div><div class="field-row"><div><label class="field-label" for="note-category">Category</label><select class="select" id="note-category" name="category"><option>Research</option><option>Execution</option><option>Risk</option><option>Review</option></select></div><div><label class="field-label" for="note-date">Date</label><input class="input" type="date" id="note-date" name="session_date" value="2026-09-08" required></div></div><div class="control note-body-control"><label class="field-label" for="note-body">Observation & next step</label><textarea id="note-body" name="body" maxlength="4000" placeholder="Separate observations from assumptions. Record the source, the change, and how you will test it." required></textarea><p class="field-help">Saved to the workspace journal. Avoid account numbers or credentials.</p></div><button class="button primary wide" type="submit">${icon("plus")}Save research note</button></div></form><div><div class="row-between" style="margin-bottom:15px"><h2 style="font-size:13px">Your notes <span class="muted">${state.notes ? " / " + state.notes.length : ""}</span></h2><div class="search-input-wrap">${icon("search")}<input class="input" id="note-search" aria-label="Search notes" placeholder="Search your notes" value="${esc(state.noteQuery)}"></div></div><div class="note-list" id="note-list">${notesMarkup()}</div><section class="card section-gap"><div class="card-head"><div><h2>Before any future trade</h2><p class="card-subtitle">Personal checklist · stored in this browser, not independently verified</p></div></div><div class="card-body">${[
    ["instrument", "Confirm instrument, contract month and tick value"],
    ["limits", "Record actual equity, floors and reset timezone"],
    ["data", "Verify data, news policy and exchange schedule"],
    ["risk", "Fit risk plus costs inside remaining loss allowance"],
    ["protection", "Confirm broker-held protection and emergency flattening"],
    ["validation", "Complete real-data and paper-execution acceptance tests"],
  ]
    .map(
      ([id, label]) =>
        `<label class="checkpoint"><input type="checkbox" data-check="${id}" ${getCheck(id) ? "checked" : ""}><span>${label}</span></label>`,
    )
    .join(
      "",
    )}<p class="field-help">A checked box records your input. It is not a compliance certificate or an instruction to trade.</p></div></section></div></div>`;
}

function render() {
  if (!state.data) return;
  const views = {
    overview: renderOverview,
    lab: renderLab,
    research: renderResearch,
    trades: renderTrades,
    rules: renderRules,
    journal: renderJournal,
    market: renderMarket,
  };
  if (!views[state.route]) state.route = "overview";
  $("#main").innerHTML = `<div class="fade-in">${views[state.route]()}</div>`;
  $$(".nav-link[data-route]").forEach((n) => {
    const active = n.dataset.route === state.route;
    n.classList.toggle("active", active);
    if (active) n.setAttribute("aria-current", "page");
    else n.removeAttribute("aria-current");
  });
  document.title = `${{ overview: "Opening Range Breakout", lab: "Scenario lab", research: "Research & evidence", trades: "Trade analytics", rules: "Strategy rulebook", journal: "Research journal", market: "Market data & replay" }[state.route]} — Range Lab`;
  drawCharts();
  if (state.route === "market") mountMarket();
  if (state.route === "rules") {
    loadSession();
    calculateSize();
  }
  if (state.route === "journal" && state.notes === null) loadNotes();
  bindDropZone();
}
function drawCharts() {
  $$("[data-chart]").forEach((host) => {
    if (host.dataset.chart === "model")
      equityChart(host, state.result, state.chartMode);
    if (host.dataset.chart === "histogram") histogramChart(host, state.result);
    if (host.dataset.chart === "ledger" && state.ledger)
      ledgerChart(host, state.ledger, state.ledgerMode);
  });
}
function navigate(route) {
  if (location.hash === "#" + route) {
    state.route = route;
    render();
  } else location.hash = route;
  closeMenu();
}
function closeMenu() {
  $("#sidebar").classList.remove("open");
  $(".sidebar-shade").hidden = true;
  $(".mobile-menu").setAttribute("aria-expanded", "false");
}
function closeExport() {
  if ($("#export-menu")) $("#export-menu").hidden = true;
  if ($("#export-button"))
    $("#export-button").setAttribute("aria-expanded", "false");
}
function markDirty() {
  state.dirty =
    JSON.stringify(state.draft) !== JSON.stringify(state.result.params);
  state.activePreset = "custom";
  const n = $("#draft-status");
  if (n) {
    n.textContent = state.dirty
      ? "Changed inputs · run to update the results"
      : "Results match these inputs";
    n.classList.toggle("changed", state.dirty);
  }
}
async function runSimulation() {
  if (state.running) return;
  const form = $("#lab-form");
  if (form && !form.reportValidity()) return;
  const params = structuredClone(state.draft);
  state.running = true;
  render();
  const begin = performance.now();
  try {
    const result = await api("simulate", {
      method: "POST",
      body: JSON.stringify(params),
    });
    state.result = result;
    state.draft = structuredClone(result.params);
    state.dirty = false;
    state.lastRun = (performance.now() - begin) / 1000;
    toast("Scenario computed. All outcomes use the displayed assumptions.");
  } catch (e) {
    toast(e.message, true);
  } finally {
    state.running = false;
    render();
  }
}
function applyPreset(key, run = false) {
  if (!PRESETS[key] || state.running) return;
  state.activePreset = key;
  state.draft = { ...structuredClone(defaults), ...PRESETS[key].patch };
  state.dirty =
    JSON.stringify(state.draft) !== JSON.stringify(state.result.params);
  if (state.route !== "lab") navigate("lab");
  else render();
  if (run) runSimulation();
}

function openDialog(content, reader = false) {
  const dialog = $("#detail-dialog");
  dialog.classList.toggle("reader", reader);
  $("#dialog-content").innerHTML = content;
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
  return dialog;
}
function dialogHead(title, sub = "") {
  return `<div class="dialog-head"><div><h2>${title}</h2>${sub ? `<p>${sub}</p>` : ""}</div><button class="icon-button" data-action="close-dialog" aria-label="Close dialog">${icon("close")}</button></div>`;
}
function glossaryItems(query = "", activeId = "") {
  const list = state.data.glossary.filter((m) =>
    [m.name, m.group, m.description, m.id]
      .join(" ")
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    list
      .map(
        (m) =>
          `<article class="glossary-item ${m.id === activeId ? "glossary-item-active" : ""}" id="glossary-term-${esc(m.id)}" data-glossary-term="${esc(m.id)}">${tag(m.group)}<h3>${esc(m.name)}</h3><code>${esc(m.formula)}</code><p>${esc(m.description)}</p></article>`,
      )
      .join("") ||
    '<p class="muted">No metric matches. Try “drawdown”, “Sharpe” or “expectancy”.</p>'
  );
}
function glossaryQuickStart() {
  return `<div class="glossary-quick-start"><strong>How to read this dashboard</strong><p>Start with the evidence label before interpreting a number. A model result is an assumption-based scenario, not a historical backtest.</p><div class="glossary-evidence-key"><span><b class="glossary-key-dot model"></b><strong>Illustrative</strong><small>assumed paths</small></span><span><b class="glossary-key-dot reported"></b><strong>Reported</strong><small>copied from a study</small></span><span><b class="glossary-key-dot user"></b><strong>User-supplied</strong><small>your records</small></span></div><div class="glossary-primer"><div><b>R</b><span>one unit of initial risk; <strong>+2R</strong> means twice that risk</span></div><div><b>ATR</b><span>recent average movement, used to scale stops and targets</span></div><div><b>RTH</b><span>regular cash-session hours; this research view uses 09:30–16:00 ET</span></div><div><b>EMA</b><span>a moving average used as a past-data trend filter</span></div></div><p class="glossary-reading-note"><b>—</b> means the available data does not support that metric. It is not zero.</p></div>`;
}
function renderGlossarySidebar(query = "", activeId = "") {
  const aside = $("#glossary-sidebar");
  const content = $("#glossary-sidebar-content");
  if (!aside || !content) return;
  content.innerHTML = `<div class="glossary-sidebar-head"><div><div class="eyebrow">REFERENCE · PLAIN ENGLISH</div><h2>Metric glossary</h2><p>What each number means, how it is calculated, and what it cannot prove.</p></div><button class="icon-button" data-action="close-glossary" aria-label="Close metric glossary">${icon("close")}</button></div><div class="glossary-sidebar-body">${glossaryQuickStart()}<div class="search-input-wrap glossary-search">${icon("search")}<input class="input" id="glossary-search" aria-label="Find a metric" placeholder="Search metrics, formulas or concepts" value="${esc(query)}"></div><div id="glossary-items">${glossaryItems(query, activeId)}</div></div>`;
}
function closeGlossary() {
  const aside = $("#glossary-sidebar");
  const shade = $("#glossary-shade");
  if (!aside || aside.hidden) return;
  aside.classList.remove("open");
  aside.setAttribute("aria-hidden", "true");
  if (shade) shade.hidden = true;
  document.body.classList.remove("glossary-open");
  window.setTimeout(() => {
    if (!aside.classList.contains("open")) aside.hidden = true;
  }, 180);
}
function openGlossary(query = "", activeId = "") {
  if (!state.data) return;
  const aside = $("#glossary-sidebar");
  const shade = $("#glossary-shade");
  if (!aside) return;
  if ($("#detail-dialog")?.open) $("#detail-dialog").close();
  aside.hidden = false;
  if (shade) shade.hidden = false;
  renderGlossarySidebar(query, activeId);
  document.body.classList.add("glossary-open");
  aside.setAttribute("aria-hidden", "false");
  requestAnimationFrame(() => aside.classList.add("open"));
  requestAnimationFrame(() => {
    const search = $("#glossary-search");
    if (search) {
      search.focus();
      if (query) search.setSelectionRange(search.value.length, search.value.length);
    }
    const item = activeId ? document.getElementById("glossary-term-" + activeId) : null;
    if (item) item.scrollIntoView({ block: "nearest" });
  });
}
function openSource(id) {
  const s = state.data.registry.sources.find((s) => s.id === Number(id));
  if (!s) return;
  openDialog(
    dialogHead(
      `Source ${String(s.id).padStart(2, "0")} · ${s.ssrn ? "SSRN " + s.ssrn : "Supporting evidence"}`,
      s.year,
    ) +
      `<div class="dialog-body source-detail"><h2 style="font-size:21px;line-height:1.5;letter-spacing:-.5px">${esc(s.title)}</h2><p style="margin-top:10px">${esc(s.authors)}</p>${s.facts?.sample ? `<div class="detail-block"><h3>Historical sample</h3><p>${esc(s.facts.sample)}</p></div>` : ""}${s.facts?.rules ? `<div class="detail-block"><h3>What was actually tested</h3><p>${esc(s.facts.rules)}</p></div>` : ""}<div class="detail-block"><h3>Reviewed scope</h3><p>${esc(s.access)}</p></div>${s.version ? `<div class="detail-block"><h3>Version & dates</h3><p>${esc(s.version)}</p></div>` : ""}${s.locators ? `<div class="detail-block"><h3>Claim locators</h3><p>${esc(s.locators)}</p></div>` : ""}<div class="notice-box"><h3>What this cannot establish</h3><p>${esc(s.limits || "This reference does not independently validate our ES/MES implementation.")}</p></div><div class="button-group section-gap" style="justify-content:flex-start"><a class="button primary" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${icon("external")}Open original source</a>${s.pdf ? `<a class="button" href="${esc(s.pdf)}" target="_blank" rel="noopener noreferrer">Author-hosted paper ${icon("arrow")}</a>` : ""}</div></div>`,
  );
}
async function openReport() {
  openDialog(
    dialogHead(
      "The ORB forensic dossier",
      "49 pages of research, methodology and execution analysis.",
    ) + `<div class="dialog-body">${blank} Loading the manuscript…</div>`,
    true,
  );
  try {
    if (!state.report) state.report = await api("report");
    renderReader();
  } catch (e) {
    $("#dialog-content").innerHTML =
      dialogHead("Dossier unavailable") +
      `<div class="dialog-body"><p>${esc(e.message)}</p>${button("Try again", "report", "primary section-gap")}</div>`;
  }
}
function renderReader() {
  const sections = state.report.sections,
    chapter = sections[state.reportIndex];
  openDialog(
    dialogHead(
      "The ORB forensic dossier",
      "Research snapshot · 08 Sep 2026 · original 49-page report",
    ) +
      `<div class="reader-toolbar"><button class="icon-button" data-action="reader-prev" aria-label="Previous chapter" ${state.reportIndex === 0 ? "disabled" : ""}>${icon("left")}</button><select class="select" id="reader-chapter" aria-label="Choose a chapter">${sections.map((s, i) => `<option value="${i}" ${state.reportIndex === i ? "selected" : ""}>${String(s.number).padStart(2, "0")} · ${esc(s.title)}</option>`).join("")}</select><button class="icon-button" data-action="reader-next" aria-label="Next chapter" ${state.reportIndex === sections.length - 1 ? "disabled" : ""}>${icon("right")}</button></div><div class="dialog-body prose">${chapter.html}</div>`,
    true,
  );
  $$(".prose a").forEach((a) => {
    a.target = "_blank";
    a.rel = "noopener noreferrer";
  });
}

async function importText(text, filename, example = false) {
  if (state.importing) return;
  state.importing = true;
  render();
  try {
    const result = await api("ledger", {
      method: "POST",
      body: JSON.stringify({
        csv_text: text,
        initial_equity: state.initialEquity,
        example,
      }),
    });
    state.ledger = result;
    state.filename = filename;
    state.ledgerPage = 0;
    state.ledgerQuery = "";
    state.ledgerSide = "all";
    toast(
      example
        ? "Fictional sample loaded. These are not historical trades."
        : `${result.metrics.count} trade records analyzed. Not independently verified.`,
    );
  } catch (e) {
    toast(e.message, true);
  } finally {
    state.importing = false;
    render();
  }
}
async function importFile(file) {
  if (!file) return;
  if (file.size > 1000000) {
    toast("CSV is too large. The maximum is 1 MB.", true);
    return;
  }
  try {
    await importText(await file.text(), file.name, false);
  } catch (e) {
    toast("The selected file could not be read.", true);
  }
}
function bindDropZone() {
  const zone = $("#drop-zone");
  if (!zone) return;
  zone.ondragover = (e) => {
    e.preventDefault();
    zone.classList.add("dragging");
  };
  zone.ondragleave = () => zone.classList.remove("dragging");
  zone.ondrop = (e) => {
    e.preventDefault();
    zone.classList.remove("dragging");
    importFile(e.dataTransfer.files[0]);
  };
}
async function loadSession() {
  const day = $("#session-date")?.value;
  if (!day) return;
  state.sessionDate = day;
  try {
    const data = await api("session?day=" + encodeURIComponent(day));
    if ($("#session-date")?.value !== day) return;
    $("#session-plan").innerHTML =
      (data.weekend
        ? '<div class="notice-box">Weekend: this is a clock conversion, not an active cash-session schedule.</div>'
        : "") +
      data.events
        .map(
          (e) =>
            `<div class="time-event"><span class="status-dot"></span><div><strong>${e.new_york} ${e.offset}</strong><p>${e.label}</p></div><div class="nairobi-time">${e.nairobi}<small>Nairobi · UTC+3</small></div></div>`,
        )
        .join("");
  } catch (e) {
    if ($("#session-plan"))
      $("#session-plan").innerHTML =
        `<p class="input-error">${esc(e.message)}</p>`;
  }
}
async function calculateSize() {
  const form = $("#sizing-form");
  if (!form || !form.reportValidity()) return;
  const data = Object.fromEntries(new FormData(form));
  Object.keys(data).forEach((k) => {
    if (k !== "instrument") data[k] = Number(data[k]);
  });
  try {
    const r = await api("size", { method: "POST", body: JSON.stringify(data) });
    if (!$("#sizing-result")) return;
    $("#sizing-result").innerHTML =
      `<div class="sizing-result ${r.contracts === 0 ? "skip" : ""}"><div class="result-top"><strong>${r.contracts} ${r.instrument}</strong><span>${r.contracts ? "integer contracts" : "Skip trade · insufficient budget"}</span></div><dl><dt>Tick-rounded stop</dt><dd>${number(r.stop_points)} points</dd><dt>Risk + fees + reserve / contract</dt><dd>${money(r.cost_per_contract, 2)}</dd><dt>Total planned budget used</dt><dd>${money(r.budget_used, 2)}</dd><dt>Unused budget</dt><dd>${money(r.unused, 2)}</dd></dl></div>`;
  } catch (e) {
    toast(e.message, true);
  }
}
async function loadNotes() {
  try {
    const data = await api("journal");
    state.notes = data.entries;
    if (state.route === "journal") render();
  } catch (e) {
    toast(e.message, true);
    if ($("#note-list"))
      $("#note-list").innerHTML =
        `<div class="card note-empty"><h3>Notes could not be loaded</h3><p>${esc(e.message)}</p>${button("Retry", "reload-notes", "primary")}</div>`;
  }
}
async function saveNote(form) {
  if (!form.reportValidity()) return;
  const submit = $("button[type=submit]", form);
  submit.disabled = true;
  try {
    await api("journal", {
      method: "POST",
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    state.notes = (await api("journal")).entries;
    toast("Research note saved to your workspace.");
    render();
  } catch (e) {
    submit.disabled = false;
    toast(e.message, true);
  }
}
function getCheck(id) {
  try {
    return localStorage.getItem("orb-check-" + id) === "true";
  } catch {
    return false;
  }
}
function downloadText(text, filename, type = "text/plain") {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}
function csvCell(value) {
  let s = String(value ?? "");
  if (typeof value === "string" && /^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return '"' + s.replaceAll('"', '""') + '"';
}
function toCSV(rows) {
  return rows.map((r) => r.map(csvCell).join(",")).join("\r\n");
}
function summary() {
  const r = state.result,
    m = r.metrics,
    s = r.params;
  return `ORB-30R — ILLUSTRATIVE scenario, NOT historical ES/MES performance\n${r.n_paths} paths; ${s.sessions} sessions; seed ${s.seed}\nAssumed win rate ${s.win_rate}%; equity risk ${s.risk_pct}%; cost ${s.cost_r}R; activity ${s.activity_pct}%\nStarting equity ${money(s.initial_equity)}; target ${s.target_pct}%; ${s.floor} loss allowance ${s.loss_limit_pct}%\nStop ${s.stop_atr} ATR / target ${s.target_atr} ATR\nNet expected payoff ${signed(m.net_expectancy_r)}R\nTarget hit ${pct(m.pass_pct, 3)} (${m.passed}); floor breach ${pct(m.breach_pct, 3)} (${m.breached}); unresolved ${pct(m.unresolved_pct, 3)} (${m.unresolved})\n95th-percentile stopped-path closing drawdown ${pct(m.dd95_pct)}\nMedian sessions to target, CONDITIONAL on passing: ${m.median_days_if_pass ?? "not observed"}\nNo price feed, ORB signal backtest, integer contracts or intrabar compliance modeled.\n`;
}
async function copySummary() {
  const text = summary();
  try {
    await navigator.clipboard.writeText(text);
    toast("Labeled scenario summary copied.");
  } catch {
    openDialog(
      dialogHead(
        "Copy your scenario summary",
        "Select and copy the text below.",
      ) +
        `<div class="dialog-body"><textarea class="input" rows="14" readonly>${esc(text)}</textarea></div>`,
    );
    $("textarea", $("#detail-dialog")).select();
  }
}

// One event delegation layer survives view changes without accumulating handlers.
document.addEventListener("click", async (e) => {
  const target = e.target.closest("[data-action]");
  if (!target) {
    if (!e.target.closest(".export-wrap")) closeExport();
    return;
  }
  const a = target.dataset.action;
  if (target.disabled) return;
  if (a === "menu") {
    const open = !$("#sidebar").classList.contains("open");
    $("#sidebar").classList.toggle("open", open);
    $(".sidebar-shade").hidden = !open;
    $(".mobile-menu").setAttribute("aria-expanded", String(open));
    return;
  }
  if (a === "close-menu") {
    closeMenu();
    return;
  }
  if (a === "close-dialog") {
    $("#detail-dialog").close();
    return;
  }
  if (a === "close-glossary") {
    closeGlossary();
    return;
  }
  if (a === "report") {
    openReport();
    return;
  }
  if (a === "retry") {
    boot();
    return;
  }
  if (!state.data) return;
  const actions = {
    glossary: () => openGlossary(),
    metric: () => {
      const metric = state.data.glossary.find((m) => m.id === target.dataset.id);
      openGlossary(metric?.name || target.dataset.id, target.dataset.id);
    },
    "go-lab": () => navigate("lab"),
    "go-research": () => navigate("research"),
    audit: () => {
      navigate("research");
      setTimeout(
        () =>
          $("#execution-audit")?.scrollIntoView({
            behavior: "smooth",
            block: "start",
          }),
        80,
      );
    },
    "chart-mode": () => {
      state.chartMode = target.dataset.mode;
      render();
    },
    "ledger-mode": () => {
      state.ledgerMode = target.dataset.mode;
      render();
    },
    "reset-scenario": () => applyPreset("base"),
    "stress-preset": () => applyPreset(target.dataset.preset, true),
    "heat-cell": () => {
      if (state.running) return;
      state.draft = {
        ...structuredClone(defaults),
        win_rate: Number(target.dataset.p),
        risk_pct: Number(target.dataset.f),
      };
      state.activePreset = "custom";
      state.dirty = true;
      if (state.route !== "lab") navigate("lab");
      runSimulation();
    },
    "research-filter": () => {
      state.researchFilter = target.dataset.id;
      render();
    },
    sort: () => {
      state.sortDesc =
        state.sortKey === target.dataset.key ? !state.sortDesc : true;
      state.sortKey = target.dataset.key;
      render();
    },
    source: () => openSource(target.dataset.id),
    "reader-prev": () => {
      state.reportIndex = Math.max(0, state.reportIndex - 1);
      renderReader();
    },
    "reader-next": () => {
      state.reportIndex = Math.min(
        state.report.sections.length - 1,
        state.reportIndex + 1,
      );
      renderReader();
    },
    import: () => {
      if (state.importing) return;
      const input = $("#import-equity");
      if (input) {
        if (!input.reportValidity()) return;
        state.initialEquity = Number(input.value);
      }
      $("#trade-file").click();
    },
    sample: async () => {
      const input = $("#import-equity");
      if (input) {
        if (!input.reportValidity()) return;
        state.initialEquity = Number(input.value);
      }
      try {
        const response = await fetch("/api/orb/ledger-template?sample=true");
        if (!response.ok) throw Error("Example file unavailable.");
        await importText(
          await response.text(),
          "Fictional example · six teaching trades",
          true,
        );
      } catch (err) {
        toast(err.message, true);
      }
    },
    template: () => {
      const a = document.createElement("a");
      a.href = "/api/orb/ledger-template";
      a.download = "orb-trade-template.csv";
      a.click();
    },
    "clear-ledger": () => {
      if (confirm("Clear this in-memory ledger? Export it first if needed.")) {
        state.ledger = null;
        state.filename = "";
        render();
      }
    },
    "prev-trades": () => {
      state.ledgerPage = Math.max(0, state.ledgerPage - 1);
      $("#ledger-table").innerHTML = ledgerTable();
    },
    "next-trades": () => {
      state.ledgerPage++;
      $("#ledger-table").innerHTML = ledgerTable();
    },
    "export-ledger": () => {
      const keys = [
        "entry_time",
        "exit_time",
        "symbol",
        "side",
        "quantity",
        "entry_price",
        "exit_price",
        "fees",
        "initial_risk_usd",
        "net_pnl",
        "r_multiple",
        "equity",
      ];
      downloadText(
        toCSV([
          ["evidence", ...keys],
          ...state.ledger.trades.map((t) => [
            state.ledger.evidence,
            ...keys.map((k) => t[k]),
          ]),
        ]),
        `orb-${state.ledger.evidence === "ILLUSTRATIVE" ? "fictional" : "user-supplied"}-ledger.csv`,
        "text/csv",
      );
      toast("Ledger export prepared with its evidence label.");
    },
    "export-menu": () => {
      const menu = $("#export-menu");
      menu.hidden = !menu.hidden;
      target.setAttribute("aria-expanded", String(!menu.hidden));
    },
    "export-json": () => {
      downloadText(
        JSON.stringify(state.result, null, 2),
        "orb-illustrative-scenario.json",
        "application/json",
      );
      toast("Scenario JSON export prepared.");
    },
    "export-csv": () => {
      const r = state.result,
        keys = [
          "session",
          "low",
          "median",
          "high",
          "dd_low",
          "dd_median",
          "dd_high",
        ];
      downloadText(
        toCSV([
          [
            "evidence",
            "seed",
            "assumed_win_rate",
            "risk_pct",
            "cost_r",
            "activity_pct",
            "floor",
            ...keys,
          ],
          ...r.paths.map((p) => [
            "ILLUSTRATIVE",
            r.params.seed,
            r.params.win_rate,
            r.params.risk_pct,
            r.params.cost_r,
            r.params.activity_pct,
            r.params.floor,
            ...keys.map((k) => p[k]),
          ]),
        ]),
        "orb-illustrative-equity-bands.csv",
        "text/csv",
      );
      toast("Equity percentile export prepared—not historical prices.");
    },
    "copy-summary": copySummary,
    "reload-notes": loadNotes,
    "export-notes": async () => {
      try {
        const data = await api("journal");
        downloadText(
          JSON.stringify(data, null, 2),
          "orb-research-journal.json",
          "application/json",
        );
        toast("Research journal export prepared.");
      } catch (err) {
        toast(err.message, true);
      }
    },
    "delete-note": async () => {
      if (!confirm("Delete this research note from the workspace?")) return;
      try {
        await api("journal/" + target.dataset.id, { method: "DELETE" });
        await loadNotes();
        toast("Research note deleted.");
      } catch (err) {
        toast(err.message, true);
      }
    },
  };
  if (actions[a]) {
    e.preventDefault();
    await actions[a]();
  }
});

document.addEventListener("input", (e) => {
  const el = e.target;
  if (el.dataset.param) {
    const key = el.dataset.param;
    state.draft[key] = key === "floor" ? el.value : Number(el.value);
    const output = $("#value-" + key);
    if (output)
      output.textContent =
        number(Number(el.value), Number(el.dataset.digits || 0)) +
        (el.dataset.unit || "");
    markDirty();
  }
  if (el.id === "glossary-search")
    $("#glossary-items").innerHTML = glossaryItems(el.value);
  if (el.id === "source-search") {
    state.sourceQuery = el.value;
    $("#source-list").innerHTML = sourceCards();
  }
  if (el.id === "trade-search") {
    state.ledgerQuery = el.value;
    state.ledgerPage = 0;
    $("#ledger-table").innerHTML = ledgerTable();
  }
  if (el.id === "note-search") {
    state.noteQuery = el.value;
    $("#note-list").innerHTML = notesMarkup();
  }
  if (el.id === "import-equity") state.initialEquity = Number(el.value);
});
document.addEventListener("change", (e) => {
  const el = e.target;
  if (el.id === "lab-preset") applyPreset(el.value);
  if (el.id === "heat-metric") {
    state.heatMetric = el.value;
    render();
  }
  if (el.id === "timeframe-metric") {
    state.timeframeMetric = el.value;
    render();
  }
  if (el.id === "trade-file") importFile(el.files[0]);
  if (el.id === "trade-side") {
    state.ledgerSide = el.value;
    state.ledgerPage = 0;
    $("#ledger-table").innerHTML = ledgerTable();
  }
  if (el.id === "reader-chapter") {
    state.reportIndex = Number(el.value);
    renderReader();
  }
  if (el.id === "session-date") loadSession();
  if (el.id === "size-instrument") {
    $("#size-fees").value = el.value === "ES" ? 5 : 2;
    calculateSize();
  }
  if (el.dataset.check) {
    try {
      localStorage.setItem("orb-check-" + el.dataset.check, String(el.checked));
    } catch {
      toast(
        "Browser storage is unavailable. Checklist changes will not persist.",
        true,
      );
    }
  }
});
document.addEventListener("submit", (e) => {
  if (e.target.id === "lab-form") {
    e.preventDefault();
    runSimulation();
  }
  if (e.target.id === "sizing-form") {
    e.preventDefault();
    calculateSize();
  }
  if (e.target.id === "note-form") {
    e.preventDefault();
    saveNote(e.target);
  }
});
document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    openGlossary();
  }
  if (e.key === "Escape") {
    closeMenu();
    closeExport();
    closeGlossary();
  }
});
$("#detail-dialog").addEventListener("click", (e) => {
  if (e.target === $("#detail-dialog")) {
    const r = e.target.getBoundingClientRect();
    if (
      e.clientX < r.left ||
      e.clientX > r.right ||
      e.clientY < r.top ||
      e.clientY > r.bottom
    )
      e.target.close();
  }
});
window.addEventListener("hashchange", () => {
  state.route = location.hash.slice(1) || "overview";
  render();
  closeMenu();
  window.scrollTo({ top: 0, behavior: "instant" });
});
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(drawCharts, 100);
});

async function boot() {
  try {
    state.data = await api("bootstrap");
    state.result = state.data.base;
    defaults = structuredClone(state.result.params);
    state.draft = structuredClone(defaults);
    state.route = location.hash.slice(1) || "overview";
    render();
  } catch (e) {
    $("#main").innerHTML =
      `<div class="loading-screen">${icon("warning")}<h1>The workspace could not load</h1><p>${esc(e.message)}</p>${button("Try again", "retry", "primary", "refresh")}<a class="text-link" href="/api/orb/download/manuscript.md">Read the saved manuscript</a></div>`;
  }
}
boot();
