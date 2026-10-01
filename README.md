# Take-Home Pay 2026 — paycheck calculators

Static, data-driven paycheck calculators for the 2026 US tax year, covering all 50 states + DC.

- **Live site:** https://calc.offctrl.ai/ (GitHub Pages, custom domain, HTTPS)
- **Legacy URLs:** `https://singletonye.github.io/paycheck-calculator/*` 301-redirects to calc.offctrl.ai;
  `https://offctrl.ai/paycheck-calculator/` holds a one-page redirect.
- **Preview mirror (noindex artifact host):** https://paycheck-calculator-2026.okou.app
- **Preview mirror (noindex, artifact host):** https://paycheck-calculator-2026.okou.app
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
tools/deploy.sh                       # builds for https://calc.offctrl.ai and pushes docs/
tools/deploy.sh https://example.com   # switch base URL (canonical + sitemap + CNAME)

# Optional: preview build on the artifact host
python3 build.py && okou host site --site paycheck-calculator-2026

# Optional: Google Search Console verification token
GSC_VERIFICATION="<token>" SITE_BASE="..." python3 build.py   # writes google<token>.html + meta tag

# Optional: AdSense (once a pub id exists)
ADSENSE_CLIENT="ca-pub-XXXXXXXXXXXXXXXX" SITE_BASE="..." python3 build.py
```

## Tests and audits

- `SITE_BASE=<base> python3 tools/audit.py` — crawls every sitemap URL and reports status codes,
  `X-Robots-Tag`, canonical, title/description length, duplicate metadata, JSON-LD validity, thin pages.
- `bash mobile/test.sh` — device-emulated layout and interaction checks (iPhone 15, Pixel 9, Galaxy S25, iPad, 360x640).

## Data sources

- Federal: IRS Rev. Proc. 2025-32 (tax year 2026 brackets and standard deduction).
- Payroll: SSA 2026 Social Security wage base $184,500; 2026 401(k) elective deferral limit $24,500.
- State: Tax Foundation, "State Individual Income Tax Rates and Brackets, 2026".

## Hosting notes

The okou artifact host serves every page with `X-Robots-Tag: noindex`, so it can never be indexed. The indexable site is
GitHub Pages at `calc.offctrl.ai` (CNAME record `calc` -> `singletonye.github.io`, DNS only / grey cloud in Cloudflare,
so GitHub can provision TLS). `https_enforced` should be turned on once the certificate is issued.

## Not modelled

Local income taxes (an optional % input is provided), state disability/paid-leave programs, state credits and
personal exemptions, itemized deductions, capital gains.
