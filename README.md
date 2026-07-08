# roi-incremental-tracking

An [OpenClaw](https://openclaw.ai) skill that tracks your AI agent's **return on investment incrementally** — one lightweight ledger row whenever the agent delivers something valuable, and a monthly closeout that turns the ledger into hard numbers and a static HTML dashboard.

## Philosophy

- **Incremental, not reconstructed.** Logging value the moment it happens beats trying to remember a month of work at closeout.
- **Conservative by default.** Minutes saved are estimated low; cash only counts when it's confirmed and closed. An ROI number you can defend is worth more than a big one you can't.
- **Money and everything else stay separate.** Risks avoided and persistent assets (docs, automations, playbooks) are reported as narrative, never silently converted into currency.
- **Near-zero overhead.** No continuous collection, no daemons — just a CSV, a config file, and one stdlib-only Python script.

## Install

**Via ClawHub:**

```bash
openclaw skills install roi-incremental-tracking
```

**Manually:** copy this folder to `~/.openclaw/skills/roi-incremental-tracking/` (or `<workspace>/skills/`), then start a new session (`/new`).

Requires `python3` on PATH for the dashboard step.

## How it works

### 1. First-run setup

The first time you ask the agent to track ROI, it asks for your numbers and saves them to `<workspace>/reports/roi/config.json`:

| Key | Meaning |
| --- | --- |
| `monthly_cost` | What running the agent costs you per cycle (subscription + API + infra) |
| `currency` | Symbol or code used everywhere (`USD`, `EUR`, `R$`, ...) |
| `base_hourly_value` | Conservative rate used to price minutes saved |
| `alternative_hourly_scenarios` | Optional comparison rates (never used in the headline ROI) |
| `cycle_start_day` | Day of month the cycle starts (default 1) |

### 2. Log deliveries as they happen

When the agent completes something relevant, it appends one row to `ledger-current.csv`:

```
date,cycle_start,cycle_end,title,category,minutes_saved,cash_direct,confidence,evidence,include_in_closeout,notes
```

Uncertain estimates get `include_in_closeout=no` until you review them.

### 3. Monthly closeout

At the end of each cycle the agent summarizes the ledger into `monthly-summary.csv`, regenerates the dashboard, and reports:

- **Cash-only ROI** — confirmed cash ÷ monthly cost
- **Cash + hours ROI** — (cash + minutes priced at your base rate) ÷ monthly cost
- Comparison with the previous month
- Risks avoided and persistent assets, narrated separately from money

```bash
python3 <workspace>/reports/roi/render_roi_report.py
```

The dashboard (`index.html`) is fully self-contained — inline CSS and SVG, no external requests. Once two or more cycles are closed it includes a multi-month trend chart of total value vs. cost.

## Try the dashboard locally

```bash
mkdir /tmp/roi-demo
cp scripts/render_roi_report.py /tmp/roi-demo/
cp examples/config.example.json /tmp/roi-demo/config.json
cp examples/ledger.example.csv /tmp/roi-demo/ledger-current.csv
python3 /tmp/roi-demo/render_roi_report.py
# open /tmp/roi-demo/index.html
```

## Repository layout

```
SKILL.md                      # the skill (frontmatter + agent instructions)
scripts/render_roi_report.py  # dashboard generator (Python 3, stdlib only)
examples/config.example.json
examples/ledger.example.csv
```

## License

MIT — see [LICENSE](LICENSE).
