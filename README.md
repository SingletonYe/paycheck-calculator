# Take-Home Pay 2026 — paycheck calculators

Static, data-driven paycheck calculators for the 2026 US tax year, covering all 50 states + DC.

- **Live site:** https://paycheck-calculator-2026.okou.app
- **Stack:** static HTML + vanilla JS, no backend, no build dependencies beyond Python 3 and Node.

## Layout

- `assets/engine.js` — the single source of truth for all math (federal 2026 brackets, FICA, state brackets).
  Runs unchanged in the browser and in Node, so generated tables can never drift from the live calculator.
- `assets/app.js` — UI for the calculator and the two-state comparison tool.
- `data/states.json` — 2026 state income tax brackets, standard deductions and local-tax notes.
- `paycalc_data/parse_states.py` (in the parent workspace) — parser for the Tax Foundation workbook.
- `build.py` — generates `site/` (56 pages): hub, 51 state pages, comparison tool, method, privacy, terms,
  sitemap and robots, with content-hashed asset filenames.

## Build and deploy

```bash
python3 build.py                       # writes ./site
okou host site --site paycheck-calculator-2026
```

## Data sources

- Federal: IRS Rev. Proc. 2025-32 (tax year 2026 brackets and standard deduction).
- Payroll: SSA 2026 Social Security wage base $184,500; 2026 401(k) elective deferral limit $24,500.
- State: Tax Foundation, "State Individual Income Tax Rates and Brackets, 2026".

## Not modelled

Local income taxes (an optional % input is provided), state disability/paid-leave programs, state credits and
personal exemptions, itemized deductions, capital gains.
