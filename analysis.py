"""
Run the QMS analysis.

Steps:
  1. load the CSV files from data/ into a SQLite database
  2. run the SQL scripts in sql/ in order (KPIs, Pareto, CAPA, audits)
  3. build a p-chart of weekly final-test failures and flag out-of-control signals
  4. export tables to output/ and charts to charts/

Run:  python analysis.py
"""

from pathlib import Path
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "output"
CHART_DIR = ROOT / "charts"

SOURCES = ["suppliers", "inspections", "nonconformities", "capa", "audit_findings"]

# p-chart: limits are calculated on 2024 (phase I) and used to monitor 2025 (phase II).
BASELINE_YEAR = "2024"
RUN_LENGTH = 8   # consecutive points on the same side of the centre line

# Chart styling
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"
MUTED = "#c9c8c2"
CRITICAL = "#d03b3b"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]

plt.rcParams.update(
    {
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": GRID,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def load_sources(con: sqlite3.Connection) -> None:
    for name in SOURCES:
        df = pd.read_csv(DATA_DIR / f"{name}.csv", dtype=str, keep_default_na=False)
        for col in ("units_tested", "units_failed", "qty_affected"):
            if col in df.columns:
                df[col] = df[col].astype(int)
        if "cost_eur" in df.columns:
            df["cost_eur"] = df["cost_eur"].astype(float)
        df.to_sql(name, con, index=False, if_exists="replace")


def run_sql(con: sqlite3.Connection) -> None:
    for script in sorted(SQL_DIR.glob("*.sql")):
        con.executescript(script.read_text(encoding="utf-8"))


def p_chart(inspections: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Weekly p-chart with limits from the baseline year and two signal rules."""
    df = inspections.copy()
    df["p"] = df["units_failed"] / df["units_tested"]
    base = df[df["week_start"].str.startswith(BASELINE_YEAR)]
    p_bar = base["units_failed"].sum() / base["units_tested"].sum()
    sigma = np.sqrt(p_bar * (1 - p_bar) / df["units_tested"])
    df["centre"] = p_bar
    df["ucl"] = p_bar + 3 * sigma
    df["lcl"] = (p_bar - 3 * sigma).clip(lower=0)

    df["beyond_limits"] = (df["p"] > df["ucl"]) | (df["p"] < df["lcl"])

    side = np.sign(df["p"] - p_bar)
    run = np.zeros(len(df), dtype=int)
    for i in range(len(df)):
        run[i] = run[i - 1] + 1 if i and side.iloc[i] == side.iloc[i - 1] and side.iloc[i] != 0 else 1
    in_run = np.zeros(len(df), dtype=bool)
    for i in range(len(df)):
        if run[i] >= RUN_LENGTH:
            in_run[i - RUN_LENGTH + 1 : i + 1] = True
    df["run_rule"] = in_run
    df["phase"] = np.where(df["week_start"].str.startswith(BASELINE_YEAR), "Baseline", "Monitoring")
    return df, p_bar


def to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        cells = []
        for v in row:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                cells.append("")
            elif isinstance(v, float):
                cells.append(f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.2f}".rstrip("0").rstrip("."))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---------- charts ----------

def chart_pareto(pareto: pd.DataFrame) -> None:
    df = pareto.iloc[::-1]
    vital = pareto["cumulative_pct"].shift(fill_value=0) < 80
    colors = [BLUE if v else MUTED for v in vital.iloc[::-1]]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.barh(df["defect_description"], df["cost_eur"] / 1000, color=colors, height=0.72, edgecolor=SURFACE, linewidth=2)
    for y, (cost, cum) in enumerate(zip(df["cost_eur"], df["cumulative_pct"])):
        ax.text(cost / 1000 + 1.5, y, f"€{cost/1000:,.0f}k · cum. {cum:.0f}%", va="center", fontsize=9, color=INK_2)
    ax.set_xlabel("Cost of nonconformities, 2024–2025 (EUR thousand)")
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, df["cost_eur"].max() / 1000 * 1.35)
    n_vital = int(vital.sum())
    ax.set_title(f"{n_vital} defects out of {len(pareto)} make up {pareto['cumulative_pct'].iloc[n_vital-1]:.0f}% of NC cost",
                 loc="left", fontsize=12, fontweight="bold", color=INK, pad=12)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "pareto_cost.png", dpi=160)
    plt.close(fig)


def chart_p(pc: pd.DataFrame, p_bar: float) -> None:
    x = pd.to_datetime(pc["week_start"])
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.step(x, pc["ucl"] * 100, where="mid", color="#9a9993", linewidth=0.9)
    ax.step(x, pc["lcl"] * 100, where="mid", color="#9a9993", linewidth=0.9)
    ax.axhline(p_bar * 100, color=INK_2, linewidth=1)
    ax.plot(x, pc["p"] * 100, color=BLUE, linewidth=1.6, marker="o", markersize=3.5)
    sig = pc[pc["beyond_limits"] | pc["run_rule"]]
    ax.plot(pd.to_datetime(sig["week_start"]), sig["p"] * 100, linestyle="none", marker="o",
            markersize=7, markerfacecolor=CRITICAL, markeredgecolor=SURFACE, markeredgewidth=1.5)

    last = x.iloc[-1] + pd.Timedelta(days=24)
    ax.text(last, pc["ucl"].iloc[-1] * 100, "UCL", va="center", fontsize=9, color=INK_2)
    ax.text(last, p_bar * 100, f"CL {p_bar*100:.2f}%", va="center", fontsize=9, color=INK_2)
    ax.text(last, pc["lcl"].iloc[-1] * 100, "LCL", va="center", fontsize=9, color=INK_2)

    split = pd.Timestamp("2025-01-01")
    ax.axvline(split, color=GRID, linewidth=1.2)
    ymax = pc["p"].max() * 100 * 1.18
    ax.text(pd.Timestamp("2024-01-08"), ymax * 0.97, "2024 · limits calculated", fontsize=9, color=INK_2, va="top")
    ax.text(pd.Timestamp("2025-01-13"), ymax * 0.97, "2025 · monitored against 2024 limits", fontsize=9, color=INK_2, va="top")
    if len(sig):
        last_sig = pd.to_datetime(sig["week_start"]).max()
        ax.text(last_sig + pd.Timedelta(days=12), sig["p"].max() * 100,
                f"● {len(sig)} weeks out of control", fontsize=9, color=CRITICAL, va="center")

    ax.set_ylim(0, ymax)
    ax.set_xlim(x.iloc[0] - pd.Timedelta(days=7), x.iloc[-1] + pd.Timedelta(days=95))
    ax.set_ylabel("Units failed at final test (%)")
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("Final-test failure rate, weekly p-chart", loc="left", fontsize=12, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "p_chart.png", dpi=160)
    plt.close(fig)


def chart_capa_effectiveness(eff: pd.DataFrame) -> None:
    df = eff.sort_values("effective_pct", ascending=False).iloc[::-1]
    worst = df["effective_pct"].min()
    colors = [BLUE if v == worst else MUTED for v in df["effective_pct"]]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.barh(df["root_cause_category"], df["effective_pct"], color=colors, height=0.68, edgecolor=SURFACE, linewidth=2)
    for y, (pct, n_eff, n_chk) in enumerate(zip(df["effective_pct"], df["n_effective"], df["n_checked"])):
        ax.text(pct + 1.2, y, f"{pct:.0f}%  ({n_eff} of {n_chk})", va="center", fontsize=9, color=INK_2)
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("CAPA effective at the 90-day check (%)")
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.set_title("Actions against human error work least often", loc="left", fontsize=12, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "capa_effectiveness.png", dpi=160)
    plt.close(fig)


def chart_audit(clauses: pd.DataFrame) -> None:
    df = clauses.sort_values(["n_findings", "clause"], ascending=[True, False])
    short = {
        "7.5.1": "Production and service provision",
        "7.5.6": "Process validation",
        "7.6": "Monitoring and measuring equipment",
    }
    labels = [f"{c}  {short.get(c, t)}" for c, t in zip(df["clause"], df["clause_title"])]
    parts = [("Major NC", "n_major"), ("Minor NC", "n_minor"), ("Observation", "n_observation")]
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    left = np.zeros(len(df))
    for (name, col), color in zip(parts, SERIES):
        ax.barh(labels, df[col], left=left, color=color, height=0.7, edgecolor=SURFACE, linewidth=2, label=name)
        left += df[col].to_numpy()
    for y, (tot, n_aud) in enumerate(zip(df["n_findings"], df["n_audits"])):
        ax.text(tot + 0.2, y, f"{tot}  ·  {n_aud} audits", va="center", fontsize=9, color=INK_2)
    ax.set_xlim(0, df["n_findings"].max() * 1.45)
    ax.set_xlabel("Audit findings, 2024–2025")
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    ax.set_title("Audit findings by ISO 13485:2016 clause", loc="left", fontsize=12, fontweight="bold", pad=12)
    fig.tight_layout()
    fig.savefig(CHART_DIR / "audit_clauses.png", dpi=160)
    plt.close(fig)


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    CHART_DIR.mkdir(exist_ok=True)
    db_path = OUT_DIR / "qms.db"
    db_path.unlink(missing_ok=True)

    with sqlite3.connect(db_path) as con:
        load_sources(con)
        run_sql(con)
        q = lambda sql: pd.read_sql(sql, con)
        pareto = q("SELECT * FROM pareto_cost")
        capa = q("SELECT * FROM capa_status ORDER BY capa_id")
        effectiveness = q("SELECT * FROM capa_effectiveness")
        clauses = q("SELECT * FROM findings_by_clause")
        repeat = q("SELECT * FROM repeat_clauses")
        review = q("SELECT kpi, y2024 AS '2024', y2025 AS '2025' FROM management_review ORDER BY ord")
        monthly = q("SELECT * FROM nc_monthly ORDER BY month")
        supplier_q = q("SELECT * FROM nc_supplier_quarter ORDER BY supplier_id, quarter")
        inspections = q("SELECT * FROM inspections ORDER BY week_start")

    pc, p_bar = p_chart(inspections)
    signals = pc[pc["beyond_limits"] | pc["run_rule"]]

    pareto.to_csv(OUT_DIR / "pareto_cost.csv", index=False)
    capa.to_csv(OUT_DIR / "capa_status.csv", index=False)
    effectiveness.to_csv(OUT_DIR / "capa_effectiveness.csv", index=False)
    clauses.to_csv(OUT_DIR / "findings_by_clause.csv", index=False)
    monthly.to_csv(OUT_DIR / "nc_monthly.csv", index=False)
    supplier_q.to_csv(OUT_DIR / "nc_supplier_quarter.csv", index=False)
    pc.round(5).to_csv(OUT_DIR / "p_chart.csv", index=False)

    chart_pareto(pareto)
    chart_p(pc, p_bar)
    chart_capa_effectiveness(effectiveness)
    chart_audit(clauses)

    sig_table = signals[["week_start", "units_tested", "units_failed", "p", "ucl", "beyond_limits", "run_rule"]].copy()
    sig_table["p"] = (sig_table["p"] * 100).round(2)
    sig_table["ucl"] = (sig_table["ucl"] * 100).round(2)
    sig_table = sig_table.rename(columns={"p": "fail_pct", "ucl": "ucl_pct"})

    report = [
        "# Management review pack",
        "",
        "## KPIs",
        "",
        to_markdown(review),
        "",
        "## p-chart signals",
        "",
        f"Centre line (2024): {p_bar*100:.2f}%. Signals: point beyond 3-sigma limits, or {RUN_LENGTH} consecutive points on one side of the centre line.",
        "",
        to_markdown(sig_table.astype(str)),
        "",
        "## Repeat audit findings (clause raised in 5 or more of the 14 audits)",
        "",
        to_markdown(repeat[["clause", "clause_title", "n_findings", "n_audits", "n_major", "n_open"]]),
        "",
        "## CAPA effectiveness by root cause",
        "",
        to_markdown(effectiveness),
        "",
    ]
    (OUT_DIR / "management_review.md").write_text("\n".join(report), encoding="utf-8")

    print(review.to_string(index=False))
    print(f"\np-chart centre: {p_bar*100:.2f}%   signals: {len(signals)}")
    print(sig_table.to_string(index=False))


if __name__ == "__main__":
    main()
