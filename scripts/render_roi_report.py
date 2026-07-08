#!/usr/bin/env python3
"""Render a static HTML ROI dashboard from the incremental ledger.

Reads, from the same directory as this script:
  - config.json          (monthly_cost, currency, base_hourly_value, ...)
  - ledger-current.csv   (incremental ledger of the current cycle)
  - monthly-summary.csv  (one row per closed cycle; optional)

Writes index.html next to them. Stdlib only — no dependencies.
"""

import csv
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_config():
    path = HERE / "config.json"
    if not path.exists():
        sys.exit(f"config.json not found in {HERE}. Run the skill's first-run setup.")
    with path.open(encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("currency", "USD")
    cfg.setdefault("alternative_hourly_scenarios", [])
    for key in ("monthly_cost", "base_hourly_value"):
        if key not in cfg:
            sys.exit(f"config.json is missing required key: {key}")
    return cfg


def load_rows(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return [row for row in csv.DictReader(f) if any(v.strip() for v in row.values() if v)]


def to_float(value):
    try:
        return float(str(value).replace(",", ".").strip() or 0)
    except ValueError:
        return 0.0


def summarize_ledger(rows, cfg):
    included = [r for r in rows if (r.get("include_in_closeout") or "").strip().lower() == "yes"]
    minutes = sum(to_float(r.get("minutes_saved")) for r in included)
    cash = sum(to_float(r.get("cash_direct")) for r in included)
    hours_value = minutes / 60.0 * cfg["base_hourly_value"]
    cost = cfg["monthly_cost"]
    return {
        "entries": len(included),
        "pending": len(rows) - len(included),
        "minutes": minutes,
        "cash": cash,
        "hours_value": hours_value,
        "total": cash + hours_value,
        "roi_cash": cash / cost if cost else 0.0,
        "roi_total": (cash + hours_value) / cost if cost else 0.0,
    }


def money(cfg, value):
    return f"{cfg['currency']} {value:,.2f}"


def card(label, value, hint=""):
    hint_html = f'<div class="hint">{html.escape(hint)}</div>' if hint else ""
    return (
        f'<div class="card"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(value)}</div>{hint_html}</div>'
    )


def trend_chart(months, cfg):
    """Inline SVG bar chart: total value per closed cycle, with the cost line."""
    if len(months) < 2:
        return ""
    width, height, pad = 640, 240, 40
    totals = [to_float(m.get("total_value")) for m in months]
    costs = [to_float(m.get("monthly_cost")) or cfg["monthly_cost"] for m in months]
    top = max(totals + costs) * 1.15 or 1.0
    n = len(months)
    slot = (width - 2 * pad) / n
    bar_w = min(48, slot * 0.6)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Total value per cycle vs monthly cost">'
    ]
    for frac in (0.25, 0.5, 0.75, 1.0):
        y = height - pad - (height - 2 * pad) * frac
        parts.append(
            f'<line x1="{pad}" y1="{y:.1f}" x2="{width - pad}" y2="{y:.1f}" class="grid"/>'
            f'<text x="{pad - 6}" y="{y + 4:.1f}" class="axis" text-anchor="end">'
            f"{top * frac:,.0f}</text>"
        )
    for i, m in enumerate(months):
        x = pad + slot * i + (slot - bar_w) / 2
        val = totals[i]
        h = (height - 2 * pad) * (val / top)
        y = height - pad - h
        over = val >= costs[i]
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
            f'class="bar {"over" if over else "under"}"/>'
            f'<text x="{x + bar_w / 2:.1f}" y="{height - pad + 16}" class="axis" '
            f'text-anchor="middle">{html.escape((m.get("cycle_start") or "")[:7])}</text>'
        )
    avg_cost = sum(costs) / n
    y_cost = height - pad - (height - 2 * pad) * (avg_cost / top)
    parts.append(
        f'<line x1="{pad}" y1="{y_cost:.1f}" x2="{width - pad}" y2="{y_cost:.1f}" class="cost"/>'
        f'<text x="{width - pad}" y="{y_cost - 6:.1f}" class="cost-label" text-anchor="end">'
        f"cost {avg_cost:,.0f}</text>"
    )
    parts.append("</svg>")
    return (
        '<h2>Multi-month trend</h2><div class="chart">' + "".join(parts) + "</div>"
        '<p class="hint">Bars: total value (cash + priced hours) per closed cycle. '
        "Line: monthly cost.</p>"
    )


def render(cfg, current, ledger_rows, months):
    scenarios = "".join(
        card(
            f"@ {money(cfg, rate)}/h",
            money(cfg, current["cash"] + current["minutes"] / 60.0 * rate),
            "comparison only",
        )
        for rate in cfg["alternative_hourly_scenarios"]
    )
    scenarios_html = (
        f'<h2>Alternative hourly scenarios</h2><div class="cards">{scenarios}</div>'
        if scenarios
        else ""
    )
    pending_hint = (
        f'{current["pending"]} row(s) excluded (include_in_closeout=no)'
        if current["pending"]
        else "all rows included"
    )
    cycle = ""
    if ledger_rows:
        cycle = (
            f'{ledger_rows[0].get("cycle_start", "?")} → '
            f'{ledger_rows[0].get("cycle_end", "?")}'
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent ROI</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 2rem auto;
         padding: 0 1rem; line-height: 1.5; }}
  h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.05rem; margin-top: 2rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: .75rem; }}
  .card {{ border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
           border-radius: 10px; padding: .75rem 1rem; }}
  .label {{ font-size: .75rem; opacity: .7; text-transform: uppercase;
            letter-spacing: .04em; }}
  .value {{ font-size: 1.3rem; font-weight: 600; margin-top: .15rem; }}
  .hint {{ font-size: .75rem; opacity: .6; margin-top: .25rem; }}
  .chart svg {{ width: 100%; height: auto; }}
  .grid {{ stroke: color-mix(in srgb, currentColor 15%, transparent); stroke-width: 1; }}
  .axis {{ font-size: 11px; fill: currentColor; opacity: .6; }}
  .bar.over {{ fill: #2e9e5b; }} .bar.under {{ fill: #c8933b; }}
  .cost {{ stroke: #c0392b; stroke-width: 2; stroke-dasharray: 6 4; }}
  .cost-label {{ font-size: 11px; fill: #c0392b; }}
</style>
</head>
<body>
<h1>Agent ROI — current cycle {html.escape(cycle)}</h1>
<div class="cards">
{card("Monthly cost", money(cfg, cfg["monthly_cost"]))}
{card("Confirmed cash", money(cfg, current["cash"]))}
{card("Time saved", f'{current["minutes"] / 60.0:,.1f} h', f'{current["minutes"]:,.0f} min')}
{card("Hours value", money(cfg, current["hours_value"]),
      f'@ {money(cfg, cfg["base_hourly_value"])}/h base')}
{card("Total value", money(cfg, current["total"]))}
{card("ROI cash-only", f'{current["roi_cash"]:.2f}x')}
{card("ROI cash + hours", f'{current["roi_total"]:.2f}x')}
{card("Ledger entries", str(current["entries"]), pending_hint)}
</div>
{scenarios_html}
{trend_chart(months, cfg)}
</body>
</html>
"""


def main():
    cfg = load_config()
    ledger_rows = load_rows(HERE / "ledger-current.csv")
    months = load_rows(HERE / "monthly-summary.csv")
    current = summarize_ledger(ledger_rows, cfg)
    out = HERE / "index.html"
    out.write_text(render(cfg, current, ledger_rows, months), encoding="utf-8")
    print(f"Wrote {out}")
    print(
        f"Cycle: {current['entries']} entries | cash {money(cfg, current['cash'])} | "
        f"total {money(cfg, current['total'])} | "
        f"ROI cash-only {current['roi_cash']:.2f}x | "
        f"ROI cash+hours {current['roi_total']:.2f}x"
    )


if __name__ == "__main__":
    main()
