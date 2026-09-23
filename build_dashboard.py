"""
Build the interactive dashboard (index.html) from the CSV files in data/.

The page is a single self-contained HTML file: the data is embedded as JSON,
and all calculations and charts run in the browser with plain JavaScript.
No server and no external libraries, so it can be published with GitHub Pages.

Run:  python build_dashboard.py
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
REPORT_DATE = "2025-12-31"


def rows(df: pd.DataFrame, cols: list[str]) -> list[list]:
    return df[cols].fillna("").values.tolist()


def main() -> None:
    ins = pd.read_csv(DATA_DIR / "inspections.csv")
    nc = pd.read_csv(DATA_DIR / "nonconformities.csv", keep_default_na=False)
    capa = pd.read_csv(DATA_DIR / "capa.csv", keep_default_na=False)
    fnd = pd.read_csv(DATA_DIR / "audit_findings.csv", keep_default_na=False)

    data = {
        "reportDate": REPORT_DATE,
        "inspections": rows(ins, ["week_start", "units_tested", "units_failed"]),
        "nc": rows(nc, ["nc_date", "defect_description", "supplier_id", "severity", "cost_eur"]),
        "capa": rows(capa, ["opened_date", "due_date", "closed_date", "root_cause_category", "effective"]),
        "findings": rows(fnd, ["audit_id", "audit_date", "clause", "clause_title", "finding_type"]),
    }
    payload = json.dumps(data, separators=(",", ":"))
    html = TEMPLATE.replace("/*__DATA__*/null", payload)
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    print(f"index.html written ({len(html) / 1024:.0f} KB)")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QMS Analytics</title>
<meta name="description" content="Interactive quality management dashboard on synthetic ISO 13485 data: p-chart, Pareto, CAPA effectiveness and audit findings.">
<style>
  :root {
    color-scheme: light;
    --surface-0: #f4f3f0;
    --surface-1: #fcfcfb;
    --border: #e4e3df;
    --grid: #e9e8e4;
    --text-primary: #0b0b0b;
    --text-secondary: #52514e;
    --text-muted: #7a7974;
    --series-1: #2a78d6;
    --series-2: #eb6834;
    --series-3: #1baf7a;
    --muted-bar: #c9c8c2;
    --limit: #9a9993;
    --critical: #d03b3b;
    --good: #0b7a0b;
    --bad: #b8322f;
    --tooltip-bg: #0b0b0b;
    --tooltip-text: #ffffff;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --surface-0: #121211;
      --surface-1: #1a1a19;
      --border: #33322f;
      --grid: #2a2a28;
      --text-primary: #ffffff;
      --text-secondary: #c3c2b7;
      --text-muted: #8f8e87;
      --series-1: #3987e5;
      --series-2: #d95926;
      --series-3: #199e70;
      --muted-bar: #4a4945;
      --limit: #77766f;
      --critical: #e25555;
      --good: #4cc24c;
      --bad: #ef7a77;
      --tooltip-bg: #f4f3f0;
      --tooltip-text: #0b0b0b;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--surface-0);
    color: var(--text-primary);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 28px 16px 48px; }
  header h1 { font-size: 26px; margin: 0 0 4px; letter-spacing: -0.01em; }
  header p { margin: 0; color: var(--text-secondary); }
  header a { color: var(--series-1); }
  .controls {
    display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
    margin: 22px 0 18px;
  }
  .controls label { color: var(--text-secondary); font-size: 14px; }
  .seg { display: inline-flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface-1); }
  .seg button {
    border: 0; background: transparent; color: var(--text-secondary);
    padding: 7px 14px; font: inherit; font-size: 14px; cursor: pointer;
  }
  .seg button + button { border-left: 1px solid var(--border); }
  .seg button[aria-pressed="true"] { background: var(--text-primary); color: var(--surface-1); }
  .seg button:focus-visible { outline: 2px solid var(--series-1); outline-offset: -2px; }
  .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .kpi { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }
  .kpi .label { font-size: 13px; color: var(--text-secondary); }
  .kpi .value { font-size: 26px; font-weight: 650; margin-top: 2px; font-variant-numeric: tabular-nums; }
  .kpi .delta { font-size: 13px; margin-top: 2px; color: var(--text-muted); font-variant-numeric: tabular-nums; }
  .kpi .delta.good { color: var(--good); }
  .kpi .delta.bad { color: var(--bad); }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 18px 18px 12px; min-width: 0; }
  .card.wide { grid-column: 1 / -1; }
  .card h2 { font-size: 17px; margin: 0 0 2px; }
  .card .sub { color: var(--text-secondary); font-size: 13.5px; margin: 0 0 10px; }
  .card .head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
  .chart { width: 100%; position: relative; }
  .chart svg { display: block; width: 100%; height: auto; overflow: visible; }
  .legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; color: var(--text-secondary); margin: 2px 0 8px; }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .legend i { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
  .tooltip {
    position: fixed; pointer-events: none; z-index: 10; opacity: 0;
    background: var(--tooltip-bg); color: var(--tooltip-text);
    font-size: 13px; line-height: 1.45; padding: 8px 10px; border-radius: 8px;
    max-width: 280px; transition: opacity .08s;
  }
  .tooltip b { font-weight: 650; }
  .note { font-size: 13px; color: var(--text-muted); margin: 6px 0 0; }
  footer { margin-top: 26px; font-size: 13.5px; color: var(--text-secondary); }
  footer a { color: var(--series-1); }
  svg text { font-family: inherit; }
  @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>QMS Analytics</h1>
    <p>Quality data of a fictional medical device manufacturer, 2024–2025. All data is synthetic.
       <a href="https://github.com/mastropasquamatteo/qms-analytics">Code and method on GitHub</a>.</p>
  </header>

  <div class="controls">
    <label id="yearLabel">Period</label>
    <div class="seg" role="group" aria-labelledby="yearLabel" id="yearSeg">
      <button type="button" data-year="all" aria-pressed="true">2024–2025</button>
      <button type="button" data-year="2024" aria-pressed="false">2024</button>
      <button type="button" data-year="2025" aria-pressed="false">2025</button>
    </div>
  </div>

  <section class="kpis" id="kpis" aria-label="Key figures"></section>

  <div class="grid">
    <div class="card wide">
      <h2>Final-test failure rate, weekly p-chart</h2>
      <p class="sub">Control limits come from 2024; 2025 is monitored against them. Red points are outside the limits. Always shows both years.</p>
      <div class="chart" id="pchart"></div>
    </div>

    <div class="card">
      <div class="head">
        <div>
          <h2>Pareto of nonconformities</h2>
          <p class="sub" id="paretoSub"></p>
        </div>
        <div class="seg" role="group" aria-label="Pareto measure" id="metricSeg">
          <button type="button" data-metric="cost" aria-pressed="true">Cost</button>
          <button type="button" data-metric="count" aria-pressed="false">Count</button>
        </div>
      </div>
      <div class="chart" id="pareto"></div>
      <p class="note">Blue: the defects that make up the first 80%. Switch to Count to see how the priorities change.</p>
    </div>

    <div class="card">
      <h2>CAPA effective at the 90-day check</h2>
      <p class="sub">By root cause, for CAPA opened in the period. Checks still pending are excluded.</p>
      <div class="chart" id="capa"></div>
    </div>

    <div class="card wide">
      <h2>Audit findings by ISO 13485:2016 clause</h2>
      <p class="sub" id="auditSub"></p>
      <div class="legend" id="auditLegend"></div>
      <div class="chart" id="audit"></div>
    </div>
  </div>

  <footer>
    Figures are computed in your browser from the raw records. The same KPIs are calculated in SQL in the repository
    (<a href="https://github.com/mastropasquamatteo/qms-analytics/tree/main/sql">sql/</a>).
  </footer>
</div>
<div class="tooltip" id="tip" role="status" aria-live="polite"></div>

<script>
const DATA = /*__DATA__*/null;
const NS = "http://www.w3.org/2000/svg";
const state = { year: "all", metric: "cost" };

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const fmtInt = n => n.toLocaleString("en-US", { maximumFractionDigits: 0 });
const fmtEur = n => "€" + (n >= 1000 ? (n / 1000).toLocaleString("en-US", { maximumFractionDigits: 0 }) + "k" : fmtInt(n));
const fmtPct = (n, d = 1) => (n == null || isNaN(n)) ? "–" : n.toFixed(d) + "%";
const inYear = (d, y) => y === "all" || d.slice(0, 4) === y;

function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

// ---------- tooltip ----------
const tip = document.getElementById("tip");
function showTip(html, ev) {
  tip.innerHTML = html;
  tip.style.opacity = 1;
  const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
  let x = ev.clientX + pad, y = ev.clientY + pad;
  if (x + w > window.innerWidth - 8) x = ev.clientX - w - pad;
  if (y + h > window.innerHeight - 8) y = ev.clientY - h - pad;
  tip.style.left = x + "px";
  tip.style.top = y + "px";
}
function hideTip() { tip.style.opacity = 0; }

// ---------- calculations ----------
function kpis(y) {
  const nc = DATA.nc.filter(r => inYear(r[0], y));
  const ins = DATA.inspections.filter(r => inYear(r[0], y));
  const capa = DATA.capa.filter(r => inYear(r[0], y));
  const fnd = DATA.findings.filter(r => inYear(r[1], y));
  const closed = capa.filter(r => r[2] !== "");
  const checked = capa.filter(r => r[4] === "Yes" || r[4] === "No");
  const tested = ins.reduce((s, r) => s + r[1], 0), failed = ins.reduce((s, r) => s + r[2], 0);
  return {
    ncCount: nc.length,
    ncCost: nc.reduce((s, r) => s + r[4], 0),
    failRate: 100 * failed / tested,
    onTime: 100 * closed.filter(r => r[2] <= r[1]).length / closed.length,
    effective: 100 * checked.filter(r => r[4] === "Yes").length / checked.length,
    findings: fnd.length,
  };
}

function pchartData() {
  const base = DATA.inspections.filter(r => r[0].startsWith("2024"));
  const pbar = base.reduce((s, r) => s + r[2], 0) / base.reduce((s, r) => s + r[1], 0);
  return {
    pbar,
    rows: DATA.inspections.map(([w, n, f]) => {
      const sd = Math.sqrt(pbar * (1 - pbar) / n);
      const p = f / n, ucl = pbar + 3 * sd, lcl = Math.max(0, pbar - 3 * sd);
      return { w, n, f, p, ucl, lcl, out: p > ucl || p < lcl };
    }),
  };
}

// ---------- KPI tiles ----------
function renderKpis() {
  const cur = kpis(state.year);
  const prev = state.year === "2025" ? kpis("2024") : null;
  const tiles = [
    { label: "Nonconformities", v: fmtInt(cur.ncCount), k: "ncCount", better: "down", unit: "" },
    { label: "NC cost", v: fmtEur(cur.ncCost), k: "ncCost", better: "down", unit: "pct" },
    { label: "Final-test failure rate", v: fmtPct(cur.failRate, 2), k: "failRate", better: "down", unit: "pp" },
    { label: "CAPA closed on time", v: fmtPct(cur.onTime), k: "onTime", better: "up", unit: "pp" },
    { label: "CAPA effective", v: fmtPct(cur.effective), k: "effective", better: "up", unit: "pp" },
    { label: "Audit findings", v: fmtInt(cur.findings), k: "findings", better: "down", unit: "" },
  ];
  const box = document.getElementById("kpis");
  box.innerHTML = "";
  for (const t of tiles) {
    let delta = "&nbsp;", cls = "";
    if (prev) {
      const d = cur[t.k] - prev[t.k];
      const txt = t.unit === "pp" ? `${d >= 0 ? "+" : "−"}${Math.abs(d).toFixed(t.k === "failRate" ? 2 : 1)} pp`
                : t.unit === "pct" ? `${d >= 0 ? "+" : "−"}${Math.abs(100 * d / prev[t.k]).toFixed(0)}%`
                : `${d >= 0 ? "+" : "−"}${fmtInt(Math.abs(d))}`;
      const good = (t.better === "up") === (d > 0);
      cls = Math.abs(d) < 1e-9 ? "" : good ? "good" : "bad";
      delta = `${txt} vs 2024`;
    } else if (state.year === "all") {
      delta = "2 years";
    } else {
      delta = "baseline year";
    }
    const div = document.createElement("div");
    div.className = "kpi";
    div.innerHTML = `<div class="label">${t.label}</div><div class="value">${t.v}</div><div class="delta ${cls}">${delta}</div>`;
    box.appendChild(div);
  }
}

// ---------- p-chart ----------
function renderPchart() {
  const host = document.getElementById("pchart");
  host.innerHTML = "";
  const { pbar, rows } = pchartData();
  const W = Math.max(host.clientWidth, 320), H = W < 560 ? 240 : 300;
  const m = { l: 44, r: 58, t: 14, b: 28 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const ymax = Math.ceil(Math.max(...rows.map(r => r.p)) * 100 * 1.15);
  const x = i => m.l + iw * i / (rows.length - 1);
  const yv = v => m.t + ih * (1 - v * 100 / ymax);
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Weekly p-chart of final-test failure rate" }, host);

  for (let t = 0; t <= ymax; t += (ymax > 8 ? 2 : 1)) {
    el("line", { x1: m.l, x2: W - m.r, y1: yv(t / 100), y2: yv(t / 100), stroke: css("--grid"), "stroke-width": 1 }, svg);
    el("text", { x: m.l - 8, y: yv(t / 100) + 4, "text-anchor": "end", "font-size": 11.5, fill: css("--text-muted") }, svg).textContent = t + "%";
  }
  const split = rows.findIndex(r => r.w >= "2025-01-01");
  el("line", { x1: x(split) - iw / (rows.length - 1) / 2, x2: x(split) - iw / (rows.length - 1) / 2, y1: m.t, y2: H - m.b, stroke: css("--border"), "stroke-width": 1.5 }, svg);
  [["2024", 0], ["2025", split]].forEach(([lab, i]) =>
    el("text", { x: x(i) + 4, y: H - 8, "font-size": 11.5, fill: css("--text-muted") }, svg).textContent = lab);

  const stepPath = key => rows.map((r, i) => {
    const x0 = i === 0 ? x(0) : (x(i - 1) + x(i)) / 2, x1 = i === rows.length - 1 ? x(i) : (x(i) + x(i + 1)) / 2;
    return `${i === 0 ? "M" : "L"}${x0},${yv(r[key])} L${x1},${yv(r[key])}`;
  }).join(" ");
  el("path", { d: stepPath("ucl"), fill: "none", stroke: css("--limit"), "stroke-width": 1 }, svg);
  el("path", { d: stepPath("lcl"), fill: "none", stroke: css("--limit"), "stroke-width": 1 }, svg);
  el("line", { x1: m.l, x2: W - m.r, y1: yv(pbar), y2: yv(pbar), stroke: css("--text-secondary"), "stroke-width": 1 }, svg);
  [["UCL", rows[rows.length - 1].ucl], [`CL ${(pbar * 100).toFixed(2)}%`, pbar], ["LCL", rows[rows.length - 1].lcl]].forEach(([t, v]) =>
    el("text", { x: W - m.r + 6, y: yv(v) + 4, "font-size": 11.5, fill: css("--text-secondary") }, svg).textContent = t);

  el("path", { d: rows.map((r, i) => `${i ? "L" : "M"}${x(i)},${yv(r.p)}`).join(" "), fill: "none", stroke: css("--series-1"), "stroke-width": 2, "stroke-linejoin": "round" }, svg);
  rows.forEach((r, i) => {
    if (r.out) el("circle", { cx: x(i), cy: yv(r.p), r: 5.5, fill: css("--critical"), stroke: css("--surface-1"), "stroke-width": 2 }, svg);
  });
  const outs = rows.map((r, i) => [r, i]).filter(([r]) => r.out);
  if (outs.length) {
    const [r, i] = outs[outs.length - 1];
    const top = Math.max(...outs.map(([o]) => o.p));
    const firstI = outs[0][1];
    const label = `● ${outs.length} weeks out of control`;
    const fits = x(i) + 12 + label.length * 6.8 < W;
    el("text", fits ? { x: x(i) + 12, y: yv(top) + 4, "font-size": 12, fill: css("--critical"), "font-weight": 600 }
                    : { x: x(firstI) - 10, y: yv(top) + 4, "text-anchor": "end", "font-size": 12, fill: css("--critical"), "font-weight": 600 }, svg).textContent = label;
  }

  const cross = el("line", { y1: m.t, y2: H - m.b, stroke: css("--text-muted"), "stroke-width": 1, opacity: 0 }, svg);
  const dot = el("circle", { r: 5, fill: css("--series-1"), stroke: css("--surface-1"), "stroke-width": 2, opacity: 0 }, svg);
  const hit = el("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent" }, svg);
  hit.addEventListener("mousemove", ev => {
    const bx = svg.getBoundingClientRect();
    const px = (ev.clientX - bx.left) * W / bx.width;
    const i = Math.max(0, Math.min(rows.length - 1, Math.round((px - m.l) / iw * (rows.length - 1))));
    const r = rows[i];
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("opacity", 1);
    dot.setAttribute("cx", x(i)); dot.setAttribute("cy", yv(r.p)); dot.setAttribute("opacity", 1);
    showTip(`<b>Week of ${r.w}</b><br>Failed ${r.f} of ${r.n} tested<br>Rate <b>${(r.p * 100).toFixed(2)}%</b> · UCL ${(r.ucl * 100).toFixed(2)}%` +
            (r.out ? `<br><b>● Out of control</b>` : ""), ev);
  });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); dot.setAttribute("opacity", 0); hideTip(); });
}

// ---------- horizontal bars (Pareto, CAPA) ----------
function hbars(host, items, opt) {
  host.innerHTML = "";
  const W = Math.max(host.clientWidth, 280);
  const narrow = W < 520;
  const labelW = narrow ? 0 : Math.min(opt.labelW, W * 0.46);
  const rowH = narrow ? 44 : 30, m = { t: 4, r: opt.right, b: 22 };
  const barY = narrow ? 20 : 5, barH = narrow ? 18 : rowH - 10, midY = narrow ? 33 : rowH / 2 + 4;
  const H = m.t + items.length * rowH + m.b;
  const iw = W - labelW - m.r;
  const max = opt.max ?? Math.max(...items.map(d => d.v));
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opt.aria }, host);
  (opt.ticks || []).filter(t => !narrow || t % 50 === 0).forEach(t => {
    const gx = labelW + iw * t / max;
    el("line", { x1: gx, x2: gx, y1: m.t, y2: H - m.b, stroke: css("--grid"), "stroke-width": 1 }, svg);
    el("text", { x: gx, y: H - 6, "text-anchor": "middle", "font-size": 11.5, fill: css("--text-muted") }, svg).textContent = opt.tickFmt(t);
  });
  items.forEach((d, i) => {
    const y = m.t + i * rowH;
    const g = el("g", {}, svg);
    el("text", narrow ? { x: 0, y: y + 14, "font-size": 12.5, fill: css("--text-secondary") }
                      : { x: labelW - 8, y: y + rowH / 2 + 4, "text-anchor": "end", "font-size": 12.5, fill: css("--text-secondary") }, g).textContent = d.label;
    const w = Math.max(1, iw * d.v / max);
    el("rect", { x: labelW, y: y + barY, width: w, height: barH, rx: 4, fill: d.color }, g);
    el("text", { x: labelW + w + 6, y: y + midY, "font-size": 12, fill: css("--text-secondary") }, g).textContent = d.text;
    el("rect", { x: 0, y, width: W, height: rowH, fill: "transparent" }, g);
    g.addEventListener("mousemove", ev => showTip(d.tip, ev));
    g.addEventListener("mouseleave", hideTip);
  });
}

function renderPareto() {
  const by = {};
  DATA.nc.filter(r => inYear(r[0], state.year)).forEach(r => {
    by[r[1]] = by[r[1]] || { cost: 0, count: 0 };
    by[r[1]].cost += r[4]; by[r[1]].count += 1;
  });
  const key = state.metric;
  const list = Object.entries(by).map(([k, v]) => ({ name: k, ...v })).sort((a, b) => b[key] - a[key]);
  const total = list.reduce((s, d) => s + d[key], 0);
  let cum = 0, nVital = 0, vitalPct = 0;
  const items = list.map(d => {
    const before = cum; cum += d[key];
    const vital = 100 * before / total < 80;
    if (vital) { nVital++; vitalPct = 100 * cum / total; }
    return {
      label: d.name, v: d[key],
      color: vital ? css("--series-1") : css("--muted-bar"),
      text: `${key === "cost" ? fmtEur(d.cost) : fmtInt(d.count)} · cum. ${(100 * cum / total).toFixed(0)}%`,
      tip: `<b>${d.name}</b><br>Cost ${fmtEur(d.cost)} · ${fmtInt(d.count)} NCs<br>Share ${(100 * d[key] / total).toFixed(1)}% · cumulative ${(100 * cum / total).toFixed(1)}%`,
    };
  });
  document.getElementById("paretoSub").textContent =
    `${nVital} of ${list.length} defects make up ${vitalPct.toFixed(0)}% of NC ${key === "cost" ? "cost" : "count"}.`;
  hbars(document.getElementById("pareto"), items, { labelW: 230, right: 108, aria: "Pareto of nonconformities" });
}

function renderCapa() {
  const by = {};
  DATA.capa.filter(r => inYear(r[0], state.year)).forEach(r => {
    by[r[3]] = by[r[3]] || { yes: 0, checked: 0 };
    if (r[4] === "Yes" || r[4] === "No") { by[r[3]].checked++; if (r[4] === "Yes") by[r[3]].yes++; }
  });
  const list = Object.entries(by).filter(([, v]) => v.checked > 0)
    .map(([k, v]) => ({ name: k, pct: 100 * v.yes / v.checked, ...v }))
    .sort((a, b) => b.pct - a.pct);
  const worst = Math.min(...list.map(d => d.pct));
  hbars(document.getElementById("capa"), list.map(d => ({
    label: d.name, v: d.pct,
    color: d.pct === worst ? css("--series-1") : css("--muted-bar"),
    text: `${d.pct.toFixed(0)}% (${d.yes} of ${d.checked})`,
    tip: `<b>${d.name}</b><br>${d.yes} effective out of ${d.checked} checked<br>${d.pct.toFixed(1)}%`,
  })), { labelW: 190, right: 96, max: 100, ticks: [0, 25, 50, 75, 100], tickFmt: t => t + "%", aria: "CAPA effectiveness by root cause" });
}

// ---------- audit (stacked) ----------
function renderAudit() {
  const host = document.getElementById("audit");
  host.innerHTML = "";
  const types = [["Major NC", "--series-1"], ["Minor NC", "--series-2"], ["Observation", "--series-3"]];
  document.getElementById("auditLegend").innerHTML =
    types.map(([t, c]) => `<span><i style="background:${css(c)}"></i>${t}</span>`).join("");
  const rowsF = DATA.findings.filter(r => inYear(r[1], state.year));
  const nAudits = new Set(rowsF.map(r => r[0])).size;
  const by = {};
  rowsF.forEach(r => {
    const k = r[2];
    by[k] = by[k] || { clause: k, title: r[3], audits: new Set(), "Major NC": 0, "Minor NC": 0, "Observation": 0, total: 0 };
    by[k][r[4]]++; by[k].total++; by[k].audits.add(r[0]);
  });
  const short = { "7.5.1": "Production and service provision", "7.5.6": "Process validation", "7.6": "Monitoring and measuring equipment" };
  const list = Object.values(by).sort((a, b) => b.total - a.total || a.clause.localeCompare(b.clause));
  document.getElementById("auditSub").textContent =
    `${rowsF.length} findings from ${nAudits} audits. Hover a bar for the detail; the number after each bar is total findings and audits where the clause came up.`;

  const W = Math.max(host.clientWidth, 280);
  const narrow = W < 520;
  const labelW = narrow ? 0 : Math.min(290, W * 0.5), rowH = narrow ? 44 : 28, m = { t: 2, r: 112, b: 6 };
  const barY = narrow ? 20 : 5, barH = narrow ? 18 : rowH - 10, midY = narrow ? 33 : rowH / 2 + 4;
  const H = m.t + list.length * rowH + m.b, iw = W - labelW - m.r;
  const max = Math.max(...list.map(d => d.total));
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Audit findings by clause" }, host);
  list.forEach((d, i) => {
    const y = m.t + i * rowH;
    const g = el("g", {}, svg);
    el("text", narrow ? { x: 0, y: y + 14, "font-size": 12.5, fill: css("--text-secondary") }
                      : { x: labelW - 8, y: y + rowH / 2 + 4, "text-anchor": "end", "font-size": 12.5, fill: css("--text-secondary") }, g)
      .textContent = `${d.clause}  ${short[d.clause] || d.title}`;
    let x0 = labelW;
    types.forEach(([t, c]) => {
      if (!d[t]) return;
      const w = iw * d[t] / max;
      el("rect", { x: x0, y: y + barY, width: Math.max(1, w - 2), height: barH, rx: 3, fill: css(c) }, g);
      if (w >= 20) el("text", { x: x0 + (w - 2) / 2, y: y + midY, "text-anchor": "middle", "font-size": 11, fill: "#ffffff", "font-weight": 600 }, g).textContent = d[t];
      x0 += w;
    });
    el("text", { x: x0 + 6, y: y + midY, "font-size": 12, fill: css("--text-secondary") }, g).textContent = `${d.total} · ${d.audits.size} audits`;
    el("rect", { x: 0, y, width: W, height: rowH, fill: "transparent" }, g);
    g.addEventListener("mousemove", ev => showTip(
      `<b>${d.clause} ${d.title}</b><br>Major NC ${d["Major NC"]} · Minor NC ${d["Minor NC"]} · Observations ${d["Observation"]}<br>Raised in ${d.audits.size} of ${nAudits} audits`, ev));
    g.addEventListener("mouseleave", hideTip);
  });
}

// ---------- wiring ----------
function renderAll() { renderKpis(); renderPchart(); renderPareto(); renderCapa(); renderAudit(); }

function bindSeg(id, attr, key) {
  document.getElementById(id).addEventListener("click", ev => {
    const b = ev.target.closest("button"); if (!b) return;
    state[key] = b.dataset[attr];
    document.querySelectorAll(`#${id} button`).forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    renderAll();
  });
}
bindSeg("yearSeg", "year", "year");
bindSeg("metricSeg", "metric", "metric");
let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(renderAll, 120); });
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", renderAll);
renderAll();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
