const GREEN = "#168b76",
  CORAL = "#d97e67",
  GRAY = "#dfe7eb";
const fmtMoney = (n) =>
  "$" + new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(n);
const compact = (n) =>
  Math.abs(n) >= 1000000
    ? "$" + (n / 1000000).toFixed(1) + "m"
    : "$" + (n / 1000).toFixed(Math.abs(n) < 10000 ? 1 : 0) + "k";
const linePath = (data, key, x, y) =>
  data
    .map(
      (d, i) => (i ? "L" : "M") + x(i).toFixed(2) + "," + y(d[key]).toFixed(2),
    )
    .join(" ");

function lineChart(host, data, options = {}) {
  if (!host || !data.length) return;
  const W = Math.max(250, host.clientWidth - 24),
    H = options.height || 265;
  const L = W < 420 ? 46 : 53,
    R = 17,
    T = 24,
    B = 40,
    pw = W - L - R,
    ph = H - T - B;
  const refs = options.refs || [];
  let lo = Math.min(...data.map((d) => d.low), ...refs.map((r) => r.value));
  let hi = Math.max(...data.map((d) => d.high), ...refs.map((r) => r.value));
  const padding = Math.max((hi - lo) * 0.08, options.percent ? 0.3 : 20);
  lo -= padding;
  hi += padding;
  if (options.percent) hi = 0;
  const x = (i) => L + (i / Math.max(1, data.length - 1)) * pw,
    y = (v) => T + ((hi - v) / (hi - lo)) * ph;
  const span = hi - lo;
  const format = options.percent
    ? (v) => (Math.abs(v) < 0.00001 ? "0" : v.toFixed(1)) + "%"
    : (v) =>
        span < 1000
          ? "$" + (v / 1000).toFixed(2) + "k"
          : span < 5000
            ? "$" + (v / 1000).toFixed(1) + "k"
            : compact(v);
  let grid = "",
    xticks = "";
  for (let i = 0; i < 5; i++) {
    const value = hi - ((hi - lo) * i) / 4,
      yy = y(value);
    grid += `<line x1="${L}" y1="${yy}" x2="${W - R}" y2="${yy}" stroke="#eaf0f1" stroke-dasharray="3 4"/><text x="${L - 10}" y="${yy + 3}" text-anchor="end" fill="#5d727d" font-size="9">${format(value)}</text>`;
  }
  const ticks = W < 440 ? 4 : 6;
  for (let i = 0; i <= ticks; i++) {
    const index = Math.round(((data.length - 1) * i) / ticks);
    xticks += `<text x="${x(index)}" y="${H - 21}" text-anchor="middle" fill="#5d727d" font-size="9">${data[index].index ?? index}</text>`;
  }
  const middle = linePath(data, "median", x, y);
  const top = linePath(data, "high", x, y);
  const bottom = [...data]
    .map(
      (d, j) =>
        "L" +
        x(data.length - 1 - j).toFixed(2) +
        "," +
        y(data[data.length - 1 - j].low).toFixed(2),
    )
    .join(" ");
  const fillPath = options.single
    ? `${middle} L${x(data.length - 1)},${H - B} L${x(0)},${H - B} Z`
    : `${top} ${bottom} Z`;
  const color = options.percent ? CORAL : GREEN;
  let reference = "";
  refs.forEach((ref) => {
    const yy = y(ref.value);
    reference += `<line x1="${L}" y1="${yy}" x2="${W - R}" y2="${yy}" stroke="${ref.color || "#aabbbd"}" stroke-width="1" stroke-dasharray="4 5" opacity=".75"/><rect x="${W - R - 113}" y="${yy - 15}" width="112" height="13" rx="2" fill="#ffffff" fill-opacity=".92"/><text x="${W - R - 3}" y="${yy - 5}" text-anchor="end" fill="${"#657b75"}" font-size="8">${ref.label}</text>`;
  });
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${options.label || "Illustrative model equity percentile chart"}"><title>${options.label || "Illustrative account paths"}</title>${grid}<path d="${fillPath}" fill="${color}" fill-opacity="${options.single ? ".045" : ".09"}"/>${!options.single ? `<path d="${top}" fill="none" stroke="${color}" stroke-width=".9" opacity=".2"/>` : ""}${reference}<path d="${middle}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>${xticks}<text x="${L + pw / 2}" y="${H - 3}" text-anchor="middle" fill="#5d727d" font-size="8">${options.xLabel || "Trading session (modeled)"}</text><g class="chart-cursor" visibility="hidden"><line y1="${T}" y2="${H - B}" stroke="#7a9e92" stroke-dasharray="3 3"/><circle r="3.5" stroke="${color}" stroke-width="2" fill="white"/></g></svg><div class="chart-tooltip" hidden></div>`;
  const svg = host.querySelector("svg"),
    tooltip = host.querySelector(".chart-tooltip"),
    cursor = host.querySelector(".chart-cursor");
  host.onpointermove = (event) => {
    const box = svg.getBoundingClientRect(),
      px = ((event.clientX - box.left) * W) / box.width;
    const index = Math.max(
      0,
      Math.min(
        data.length - 1,
        Math.round(((px - L) / pw) * (data.length - 1)),
      ),
    );
    const d = data[index],
      xx = x(index),
      yy = y(d.median);
    cursor.setAttribute("visibility", "visible");
    cursor.querySelector("line").setAttribute("x1", xx);
    cursor.querySelector("line").setAttribute("x2", xx);
    cursor.querySelector("circle").setAttribute("cx", xx);
    cursor.querySelector("circle").setAttribute("cy", yy);
    tooltip.innerHTML = options.tooltip
      ? options.tooltip(d, index)
      : `<strong>Session ${d.index ?? index}</strong><span>Median equity <b>${fmtMoney(d.median)}</b></span><span>5th percentile <b>${fmtMoney(d.low)}</b></span><span>95th percentile <b>${fmtMoney(d.high)}</b></span>`;
    tooltip.hidden = false;
    tooltip.style.left =
      Math.min(
        Math.max(8, xx + 24),
        host.clientWidth - tooltip.offsetWidth - 8,
      ) + "px";
    tooltip.style.top = "12px";
  };
  host.onpointerdown = host.onpointermove;
  host.onpointerleave = (event) => {
    if (event.pointerType === "touch") return;
    tooltip.hidden = true;
    cursor.setAttribute("visibility", "hidden");
  };
}

export function equityChart(host, result, mode = "equity") {
  const { params: s, paths } = result;
  if (mode === "drawdown") {
    const data = paths.map((p) => ({
      index: p.session,
      low: -p.dd_high,
      median: -p.dd_median,
      high: -p.dd_low,
      raw: p,
    }));
    lineChart(host, data, {
      percent: true,
      label: "Illustrative drawdown percentiles, not historical losses",
      tooltip: (d) =>
        `<strong>Session ${d.index} · drawdown</strong><span>Median <b>${d.raw.dd_median.toFixed(2)}%</b></span><span>95th percentile <b>${d.raw.dd_high.toFixed(2)}%</b></span><span>Closing equity only</span>`,
    });
  } else {
    lineChart(host, paths, {
      refs: [
        {
          value: s.initial_equity * (1 + s.target_pct / 100),
          label: `Target +${s.target_pct}%`,
          color: "#76a496",
        },
        {
          value: s.initial_equity * (1 - s.loss_limit_pct / 100),
          label: `${s.floor === "trailing" ? "Initial floor" : "Static floor"} −${s.loss_limit_pct}%`,
          color: "#bd9685",
        },
      ],
    });
  }
}

export function ledgerChart(host, ledger, mode = "equity") {
  const data = ledger.curve.map((p) => ({
    index: p.index,
    low: mode === "equity" ? p.equity : -p.drawdown,
    median: mode === "equity" ? p.equity : -p.drawdown,
    high: mode === "equity" ? p.equity : -p.drawdown,
    raw: p,
  }));
  lineChart(host, data, {
    single: true,
    percent: mode !== "equity",
    label: `${ledger.evidence} closing-trade ${mode}; not intraday equity`,
    xLabel: "Closed trade index",
    tooltip: (d) =>
      `<strong>${d.index ? "Closed trade " + d.index : "Starting equity"}</strong><span>Equity <b>${fmtMoney(d.raw.equity)}</b></span><span>Closing drawdown <b>${d.raw.drawdown.toFixed(2)}%</b></span>`,
  });
}

export function histogramChart(host, result) {
  if (!host) return;
  const W = Math.max(230, host.clientWidth - 24),
    H = 185,
    L = 32,
    R = 10,
    T = 14,
    B = 34,
    pw = W - L - R,
    ph = H - T - B;
  const bins = result.histogram,
    rawMax = Math.max(...bins.map((b) => b.count)),
    max = Math.ceil(rawMax / 500) * 500,
    bw = pw / bins.length;
  let bars = "";
  bins.forEach((b, i) => {
    const height = (b.count / max) * ph;
    bars += `<rect x="${L + i * bw + 1}" y="${H - B - height}" width="${Math.max(1, bw - 2)}" height="${height}" rx="1.4" fill="${(b.low + b.high) / 2 < 0 ? CORAL : GREEN}" opacity=".72"><title>${b.low.toFixed(2)}% to ${b.high.toFixed(2)}%: ${b.count.toLocaleString()} paths</title></rect>`;
  });
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="Distribution of illustrative terminal account returns"><line x1="${L}" y1="${H - B}" x2="${W - R}" y2="${H - B}" stroke="#dde7e8"/><line x1="${L}" y1="${T}" x2="${W - R}" y2="${T}" stroke="#edf1f2" stroke-dasharray="3 3"/><text x="${L - 5}" y="${T + 3}" text-anchor="end" font-size="8" fill="#5d727d">${(max / 1000).toFixed(max % 1000 ? 1 : 0)}k</text>${bars}<text x="${L}" y="${H - 16}" fill="#5d727d" font-size="9">${bins[0].low.toFixed(1)}%</text><text x="${W - R}" y="${H - 16}" text-anchor="end" fill="#5d727d" font-size="9">${bins.at(-1).high.toFixed(1)}%</text><text x="${W / 2}" y="${H - 1}" text-anchor="middle" fill="#5d727d" font-size="8">Terminal return · stopped paths</text></svg>`;
}

export function donutMarkup(result) {
  const m = result.metrics,
    values = [m.pass_pct, m.breach_pct, m.unresolved_pct],
    colors = [GREEN, CORAL, GRAY],
    circumference = 2 * Math.PI * 59;
  let offset = 0;
  const arcs = values
    .map((value, i) => {
      const length = (circumference * value) / 100;
      const svg = `<circle cx="80" cy="80" r="59" fill="none" stroke="${colors[i]}" stroke-width="13" stroke-dasharray="${length} ${circumference - length}" stroke-dashoffset="${-offset}" transform="rotate(-90 80 80)"/>`;
      offset += length;
      return svg;
    })
    .join("");
  return `<svg viewBox="0 0 160 160" role="img" aria-label="${m.pass_pct.toFixed(2)} percent target hit, ${m.breach_pct.toFixed(2)} percent floor breach, ${m.unresolved_pct.toFixed(2)} percent unresolved">${arcs}<text x="80" y="78" text-anchor="middle" fill="#2b4b56" font-size="24" font-weight="550" letter-spacing="-1">20,000</text><text x="80" y="96" text-anchor="middle" fill="#5d727d" font-size="9">modeled paths</text></svg>`;
}
