#!/usr/bin/env python3
"""Static site generator — 2026 paycheck calculators for all 50 states + DC.
Math single source of truth: assets/engine.js (executed through Node at build time).
State data: data/states.json (parsed from the Tax Foundation 2026 workbook)."""
import datetime
import hashlib
import html
import json
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "site")
TODAY = datetime.date.today().isoformat()
BASE = "https://paycheck-calculator-2026.okou.app"
YEAR = 2026
ASSETS = {}

STATES = json.load(open(os.path.join(ROOT, "data", "states.json")))
ORDER = sorted(STATES, key=lambda s: STATES[s]["name"])
NO_TAX = [s for s in ORDER if not STATES[s]["single"]]
FLAT = [s for s in ORDER if len(STATES[s]["single"]) == 1]
GRAD = [s for s in ORDER if len(STATES[s]["single"]) > 1]
EXAMPLES_SINGLE = [50000, 75000, 100000, 150000]
EXAMPLES_MFJ = [100000]
REF_STATES = ["texas", "florida", "california", "new-york", "illinois"]
HOURLY_RATES = [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
                32, 33, 35, 36, 38, 40, 42, 45, 48, 50, 55, 60]
SALARIES = [40000, 45000, 50000, 55000, 60000, 65000, 70000, 75000, 80000,
            85000, 90000, 95000, 100000, 110000, 120000, 130000, 150000, 200000]
HOURS_PER_YEAR = 2080


def usd(n):
    return "${:,.0f}".format(round(n))


def pct(rate):
    v = rate * 100
    return ("{:.2f}%".format(v) if v < 1 else "{:.1f}%".format(v)).replace(".0%", "%")


def node_examples():
    """Compute every static table with the same engine the browser uses."""
    lines = ["globalThis.STATE_DATA = {states: require('%s')};" % os.path.join(ROOT, "data", "states-data.json"),
             "var E = require('%s');" % os.path.join(ROOT, "assets", "engine.js"),
             "var out = {};"]
    for slug in ORDER:
        for inc in EXAMPLES_SINGLE:
            lines.append("out['%s|%s|single']=E.takeHome({grossAnnual:%d,filingStatus:'single',stateSlug:'%s'});"
                         % (slug, inc, inc, slug))
        for inc in EXAMPLES_MFJ:
            lines.append("out['%s|%s|mfj']=E.takeHome({grossAnnual:%d,filingStatus:'mfj',stateSlug:'%s'});"
                         % (slug, inc, inc, slug))
    for inc in sorted(set([r * HOURS_PER_YEAR for r in HOURLY_RATES] + SALARIES)):
        for st in REF_STATES:
            lines.append("out['ref|%s|%s']=E.takeHome({grossAnnual:%d,filingStatus:'single',stateSlug:'%s'});"
                         % (inc, st, inc, st))
    lines.append("console.log(JSON.stringify(out));")
    script = "\n".join(lines)
    raw = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(raw)


def state_lede(slug):
    s = STATES[slug]
    name = s["name"]
    if not s["single"]:
        return ("{} does not tax wage income, so a paycheck there is reduced only by federal income tax, "
                "Social Security and Medicare.".format(name))
    if len(s["single"]) == 1:
        return ("{} taxes wages at a flat rate of {}, against a {} standard deduction for single filers "
                "({} for couples).".format(name, pct(s["single"][0]["rate"]), usd(s["sdSingle"]),
                                           usd(s["sdMfj"] or s["sdSingle"])))
    top = pct(s["single"][-1]["rate"])
    low = pct(s["single"][0]["rate"])
    return ("{} uses a graduated income tax: {} brackets running from {} to {}, with a {} standard deduction "
            "for single filers ({} for couples).".format(name, len(s["single"]), low, top,
                                                         usd(s["sdSingle"]), usd(s["sdMfj"] or s["sdSingle"])))


CALC = """
<section class="card">
  <form id="calc" class="calc-form" autocomplete="off">
    <div class="field">
      <label for="amount">Gross pay</label>
      <input type="number" id="amount" value="60000" min="0" step="100" inputmode="decimal">
    </div>
    <div class="field">
      <label for="freq">Per</label>
      <select id="freq">
        <option value="annual" selected>Year</option>
        <option value="monthly">Month</option>
        <option value="semimonthly">Semi-monthly</option>
        <option value="biweekly">Two weeks</option>
        <option value="weekly">Week</option>
        <option value="hourly">Hour</option>
      </select>
    </div>
    <div class="field" id="hoursField" hidden>
      <label for="hours">Hours / week</label>
      <input type="number" id="hours" value="40" min="1" max="80" step="1">
    </div>
    <div class="field">
      <label for="status">Filing status</label>
      <select id="status">
        <option value="single" selected>Single</option>
        <option value="mfj">Married filing jointly</option>
        <option value="hoh">Head of household</option>
      </select>
    </div>
    <div class="field">
      <label for="pretax">Pre-tax deductions (year)</label>
      <input type="number" id="pretax" value="0" min="0" step="100">
    </div>
    <div class="field">
      <label for="local">Local income tax %</label>
      <input type="number" id="local" value="0" min="0" max="10" step="0.05">
    </div>
    <div class="field" id="stateField" hidden>
      <label for="state">State</label>
      <select id="state"></select>
    </div>
  </form>

  <div class="results" id="results" aria-live="polite">
    <div class="headline">
      <div><span class="label">Estimated take-home</span><strong id="netAnnual">—</strong><span class="sub" id="netAnnualSub">per year</span></div>
      <div><span class="label">Per paycheck</span><strong id="netPeriod">—</strong><span class="sub" id="netPeriodSub">—</span></div>
    </div>
    <table class="breakdown">
      <thead><tr><th>Item</th><th>Annual</th><th>Per paycheck</th></tr></thead>
      <tbody id="rows"></tbody>
      <tfoot><tr><th>Take-home</th><td id="footNet">—</td><td id="footNetPeriod">—</td></tr></tfoot>
    </table>
    <p class="eff" id="effLine"></p>
    <details class="rates">
      <summary>Bracket detail</summary>
      <ul id="bands"></ul>
    </details>
  </div>
</section>
"""

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="{root}{css}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="website">
<script type="application/ld+json">{schema}</script>
</head>
<body data-mode="{mode}"{bodyattr}>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="{root}index.html">Take&#8209;Home&nbsp;Pay&nbsp;2026</a>
    <nav>
      <a href="{root}index.html">All states</a>
      <a href="{root}compare-take-home-pay-by-state.html">Compare</a>
      <a href="{root}method.html">Method</a>
    </nav>
  </div>
</header>
<main class="wrap">
"""

FOOT = """</main>
<footer class="site-footer">
  <div class="wrap">
    <p><strong>Take-Home Pay {year}</strong> — free paycheck calculators for all 50 states and DC.</p>
    <p>Estimates only. Federal figures use IRS Rev. Proc. 2025-32 (2026 brackets, {sd} standard deduction) and the
    $184,500 Social Security wage base. State income tax brackets come from the Tax Foundation's 2026 state tax
    compilation. Local taxes, state disability programs and credits are not modeled. Not tax advice.</p>
    <p><a href="{root}method.html">Method &amp; sources</a> · <a href="{root}compare-take-home-pay-by-state.html">Compare states</a> · <a href="{root}privacy.html">Privacy</a> · <a href="{root}terms.html">Terms</a></p>
    <p class="muted">Last updated {today}</p>
  </div>
</footer>
<script src="{root}{states_js}"></script>
<script src="{root}{engine}"></script>
<script src="{root}{app}"></script>
</body>
</html>
"""


def state_bracket_table(slug):
    s = STATES[slug]
    if not s["single"]:
        return ("<p>{} has no state income tax on wages, so there are no state brackets to show.</p>".format(s["name"]))
    def rows(brackets):
        out = []
        for i, b in enumerate(brackets):
            upper = brackets[i + 1]["over"] if i + 1 < len(brackets) else None
            rng = (usd(b["over"]) + " – " + usd(upper - 1)) if upper else ("over " + usd(b["over"]))
            out.append("<tr><td>{}</td><td>{}</td></tr>".format(pct(b["rate"]), rng))
        return "".join(out)
    return ("""<div class="two-col">
  <div><h3>Single filer</h3><table class="examples"><thead><tr><th>Rate</th><th>Taxable income</th></tr></thead>
  <tbody>{single}</tbody></table>
  <p class="muted">Standard deduction {sd}.</p></div>
  <div><h3>Married filing jointly</h3><table class="examples"><thead><tr><th>Rate</th><th>Taxable income</th></tr></thead>
  <tbody>{mfj}</tbody></table>
  <p class="muted">Standard deduction {sdm}.</p></div>
</div>""").format(single=rows(s["single"]), mfj=rows(s["mfj"] or s["single"]),
                 sd=usd(s["sdSingle"]), sdm=usd(s["sdMfj"] or s["sdSingle"]))


def example_table(slug):
    rows = []
    for inc in EXAMPLES_SINGLE:
        r = EX["{}|{}|single".format(slug, inc)]
        rows.append("<tr><td>{g}</td><td>{fed}</td><td>{fica}</td><td>{st}</td><td>{net}</td><td>{mo}</td><td>{bw}</td></tr>".format(
            g=usd(inc), fed=usd(r["federalTax"]), fica=usd(r["fica"]["total"]), st=usd(r["stateTax"]),
            net=usd(r["netAnnual"]), mo=usd(r["netPerPeriod"]["monthly"]), bw=usd(r["netPerPeriod"]["biweekly"])))
    for inc in EXAMPLES_MFJ:
        r = EX["{}|{}|mfj".format(slug, inc)]
        rows.append("<tr class='alt'><td>{g} (joint)</td><td>{fed}</td><td>{fica}</td><td>{st}</td><td>{net}</td><td>{mo}</td><td>{bw}</td></tr>".format(
            g=usd(inc), fed=usd(r["federalTax"]), fica=usd(r["fica"]["total"]), st=usd(r["stateTax"]),
            net=usd(r["netAnnual"]), mo=usd(r["netPerPeriod"]["monthly"]), bw=usd(r["netPerPeriod"]["biweekly"])))
    return "\n".join(rows)


def state_page(slug):
    s = STATES[slug]
    name = s["name"]
    canonical = "{}/{}-paycheck-calculator.html".format(BASE, slug)
    title = "{} Paycheck Calculator (2026) — Take-Home Pay After Tax".format(name)
    desc = ("Free {} paycheck calculator for 2026: enter your salary and see federal tax, FICA, {} state income tax "
            "and your exact take-home pay per paycheck.").format(name, name)
    schema = json.dumps({
        "@context": "https://schema.org", "@type": "WebApplication",
        "name": title, "applicationCategory": "FinanceApplication", "operatingSystem": "Web",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}})

    r50 = EX["{}|50000|single".format(slug)]
    r100 = EX["{}|100000|single".format(slug)]
    r100m = EX["{}|100000|mfj".format(slug)]
    top = s["single"][-1]["rate"] if s["single"] else 0

    facts = [
        ("State income tax on wages", "None" if not s["single"] else ("Flat {}".format(pct(top)) if len(s["single"]) == 1 else "Graduated, {} brackets up to {}".format(len(s["single"]), pct(top)))),
        ("Standard deduction (single / couple)", "n/a" if not s["single"] else "{} / {}".format(usd(s["sdSingle"]), usd(s["sdMfj"] or s["sdSingle"]))),
        ("Federal tax", "10%–37% progressive brackets, 2026 rates"),
        ("Social Security", "6.2% on the first $184,500 of wages"),
        ("Medicare", "1.45%, plus 0.9% above $200,000 (single)"),
    ]
    facts_html = "".join("<tr><th>{}</th><td>{}</td></tr>".format(k, v) for k, v in facts)
    local_html = "<p class=\"note\"><strong>Local income taxes:</strong> {}</p>".format(s["local"]) if s.get("local") else ""

    faq = [
        ("Does {} have a state income tax?".format(name),
         state_lede(slug)),
        ("What is the take-home pay on $50,000 in {}?".format(name),
         "A single filer in {} keeps about {} a year — {} a month, or {} every two weeks — after {} of federal tax, "
         "{} of FICA and {} of state income tax.".format(name, usd(r50["netAnnual"]), usd(r50["netPerPeriod"]["monthly"]),
                                                         usd(r50["netPerPeriod"]["biweekly"]), usd(r50["federalTax"]),
                                                         usd(r50["fica"]["total"]), usd(r50["stateTax"]))),
        ("What is the take-home pay on $100,000 in {}?".format(name),
         "A single filer keeps about {} a year ({} a month) and a married couple filing jointly keeps about {}. "
         "The difference is mostly federal bracket progression plus {}".format(
             usd(r100["netAnnual"]), usd(r100["netPerPeriod"]["monthly"]), usd(r100m["netAnnual"]),
             "the state's graduated brackets" if len(s["single"]) > 1 else "withholding on your W-4")),
        ("What else comes out of a {} paycheck?".format(name),
         "Social Security at 6.2% up to the $184,500 wage base, Medicare at 1.45% with an extra 0.9% above $200,000, "
         "and any employer benefit premiums. Pre-tax retirement contributions such as a 401(k) reduce federal "
         "taxable income (2026 limit $24,500) but not FICA."),
    ]
    faq_html = "\n".join('<details><summary>{}</summary><p>{}</p></details>'.format(html.escape(q), html.escape(a))
                         for q, a in faq)
    faq_schema = json.dumps({"@context": "https://schema.org", "@type": "FAQPage",
                             "mainEntity": [{"@type": "Question", "name": q,
                                             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]})

    other = [o for o in ORDER if o != slug][:8]
    links = " ".join('<a href="{}-paycheck-calculator.html">{}</a>'.format(o, STATES[o]["name"]) for o in other)
    fmt = "" if not s["single"] else ("flat" if len(s["single"]) == 1 else "graduated")

    body = """
<h1>{name} Paycheck Calculator (2026)</h1>
<p class="lede">Work out your {name} take-home pay for the 2026 tax year. {lede}</p>

{calc}

<section>
  <h2>What comes out of a {name} paycheck</h2>
  <table class="facts">{facts}</table>
  {local}
</section>

<section>
  <h2>{name} tax brackets for 2026</h2>
  {brackets}
</section>

<section>
  <h2>{name} take-home pay by salary</h2>
  <table class="examples">
    <thead><tr><th>Gross salary</th><th>Federal tax</th><th>FICA</th><th>{abbr} state tax</th><th>Take-home / year</th><th>/ month</th><th>/ 2 weeks</th></tr></thead>
    <tbody>
{examples}
    </tbody>
  </table>
  <p class="muted">No pre-tax deductions, no local income tax, 2026 figures.</p>
</section>

<section>
  <h2>How to raise your {name} take-home pay</h2>
  <ul class="tight">
    <li><strong>Contribute pre-tax.</strong> Every dollar into a 401(k) or HSA comes out of federal taxable income; the 2026 401(k) limit is $24,500.</li>
    <li><strong>Fix your W-4.</strong> Withholding is only as accurate as the form behind it — a mismatch shows up as a refund or a bill.</li>
    <li><strong>Know the FICA cap.</strong> Payroll tax on Social Security stops once year-to-date wages pass $184,500, so later paychecks jump.</li>
    <li><strong>Check the {fmt_word} state schedule.</strong> {state_tip}</li>
  </ul>
</section>

<section>
  <h2>{name} paycheck questions</h2>
  {faq}
</section>

<section>
  <h2>Compare {name} with other states</h2>
  <p class="statelinks">{links}</p>
  <p><a href="compare-take-home-pay-by-state.html">Run a side-by-side comparison for any two states →</a></p>
</section>
<script type="application/ld+json">{faq_schema}</script>
""".format(name=name, lede=state_lede(slug), calc=CALC, facts=facts_html, local=local_html,
           brackets=state_bracket_table(slug), abbr="".join(w[0] for w in name.split()[:2]) if len(name.split()) > 1 else name[:2].upper(),
           examples=example_table(slug), faq=faq_html, links=links,
           fmt_word=("flat-rate" if fmt == "flat" else "graduated" if fmt == "graduated" else "zero-tax"),
           state_tip=("{} brackets mean the top rate only applies to the last slice of income.".format(name)
                      if fmt == "graduated" else
                      "One flat rate applies from the first dollar, so the timing of bonuses barely changes the bill."
                      if fmt == "flat" else
                      "With no state wage tax, comparing offers comes down to federal brackets, FICA and local costs like property tax."),
           faq_schema=faq_schema)

    page = HEAD.format(title=title, desc=desc, canonical=canonical, root="", schema=schema,
                       mode="state", bodyattr=' data-state="{}"'.format(slug), **ASSETS)
    page += body + FOOT.format(root="", sd="$16,100", today=TODAY, year=YEAR, **ASSETS)
    with open(os.path.join(OUT, "{}-paycheck-calculator.html".format(slug)), "w") as f:
        f.write(page)
    return canonical


def index_page():
    def card(slug):
        s = STATES[slug]
        top = s["single"][-1]["rate"] if s["single"] else 0
        tag = "No state income tax" if not s["single"] else ("Flat {}".format(pct(top)) if len(s["single"]) == 1
                                                            else "Up to {}".format(pct(top)))
        return ('<a class="state-card" href="{slug}-paycheck-calculator.html"><span class="abbr">{abbr}</span>'
                '<span class="name">{name}</span><span class="tag">{tag}</span></a>').format(
                    slug=slug, name=s["name"], tag=tag,
                    abbr="".join(w[0] for w in s["name"].split()[:2]).upper() if len(s["name"].split()) > 1 else s["name"][:2].upper())
    groups = [("States with no income tax on wages", NO_TAX),
              ("Flat-rate states", FLAT),
              ("Graduated-rate states", [s for s in GRAD if s not in FLAT])]
    group_html = "\n".join(
        '<h2>{}</h2><div class="state-grid">{}</div>'.format(title, "".join(card(s) for s in slugs))
        for title, slugs in groups)
    title = "Paycheck Calculator 2026 — Take-Home Pay For All 50 States"
    desc = ("Free paycheck calculator for 2026 covering all 50 states and DC: federal tax, FICA, state income tax "
            "and take-home pay per paycheck, with the 2026 brackets behind every number.")
    schema = json.dumps({"@context": "https://schema.org", "@type": "WebSite", "name": "Take-Home Pay 2026"})
    body = """
<h1>Paycheck calculator for 2026</h1>
<p class="lede">Enter your pay, pick your state and see exactly what lands in your account: federal income tax,
Social Security, Medicare, state income tax and your take-home pay per year, per month and per paycheck.
Every state uses its own 2026 bracket schedule, and the numbers update when the IRS and states publish new ones.</p>

{calc}

<section><h2>Where the money goes in 2026</h2>
<ul class="tight">
  <li><strong>Federal:</strong> the standard deduction is $16,100 single, $32,200 married filing jointly, $24,150 head of household, with seven brackets from 10% to 37%.</li>
  <li><strong>Payroll:</strong> Social Security 6.2% up to $184,500, Medicare 1.45%, plus 0.9% additional Medicare above $200,000.</li>
  <li><strong>State:</strong> nine states tax no wage income, 15 use a flat rate and the rest use graduated brackets topping out anywhere from 2.5% to 13.3%.</li>
  <li><strong>Local:</strong> New York City, Philadelphia, Detroit, most Ohio cities and Maryland counties add their own tax — use the local rate box above.</li>
</ul></section>

<section>{groups}</section>

<section>
  <h2>Hourly to yearly conversions</h2>
  <p class="statelinks">{hourly_links}</p>
</section>

<section>
  <h2>Salary to hourly conversions</h2>
  <p class="statelinks">{salary_links}</p>
</section>
""".format(calc=CALC, groups=group_html,
           hourly_links=" ".join('<a href="{0}-an-hour-is-how-much-a-year.html">${0}/hour</a>'.format(r) for r in HOURLY_RATES),
           salary_links=" ".join('<a href="{0}-a-year-is-how-much-an-hour.html">{1}</a>'.format(a, usd(a)) for a in SALARIES))
    page = HEAD.format(title=title, desc=desc, canonical=BASE + "/", root="", schema=schema,
                       mode="state", bodyattr="", **ASSETS)
    page += body + FOOT.format(root="", sd="$16,100", today=TODAY, year=YEAR, **ASSETS)
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(page)
    return BASE + "/"


COMPARE_CALC = """
<section class="card">
  <form id="compare" class="calc-form" autocomplete="off">
    <div class="field"><label for="c-amount">Salary</label>
      <input type="number" id="c-amount" value="100000" min="0" step="1000"></div>
    <div class="field"><label for="c-status">Filing status</label>
      <select id="c-status"><option value="single" selected>Single</option><option value="mfj">Married filing jointly</option><option value="hoh">Head of household</option></select></div>
    <div class="field"><label for="c-a">State A</label><select id="c-a"></select></div>
    <div class="field"><label for="c-b">State B</label><select id="c-b"></select></div>
  </form>
  <div class="results">
    <div class="headline">
      <div><span class="label" id="c-name-a">—</span><strong id="c-net-a">—</strong><span class="sub" id="c-month-a">—</span></div>
      <div><span class="label" id="c-name-b">—</span><strong id="c-net-b">—</strong><span class="sub" id="c-month-b">—</span></div>
    </div>
    <p class="verdict" id="c-verdict"></p>
    <table class="examples">
      <thead><tr><th>State</th><th>Federal</th><th>FICA</th><th>State tax</th><th>Take-home</th><th>Effective rate</th></tr></thead>
      <tbody id="c-table"></tbody>
    </table>
    <p class="muted">No local income tax, no pre-tax deductions. State A state tax: <strong id="c-tax-a">—</strong>;
      State B state tax: <strong id="c-tax-b">—</strong>.</p>
  </div>
</section>
"""


def compare_page():
    title = "Compare Take-Home Pay By State (2026)"
    desc = ("Compare your take-home pay in any two states for 2026. See the state income tax, effective rate and "
            "monthly difference side by side before you take the offer or move.")
    schema = json.dumps({"@context": "https://schema.org", "@type": "WebApplication", "name": title,
                         "applicationCategory": "FinanceApplication", "offers": {"@type": "Offer", "price": "0"}})
    top = sorted(ORDER, key=lambda s: -(STATES[s]["single"][-1]["rate"] if STATES[s]["single"] else 0))[:5]
    bottom = NO_TAX
    body = """
<h1>Compare take-home pay by state</h1>
<p class="lede">Two offers in two states, or a move you are weighing? Pick both states and compare what actually
lands in your account after federal tax, FICA and state income tax.</p>

{calc}

<section>
  <h2>What usually decides it</h2>
  <ul class="tight">
    <li><strong>State income tax.</strong> {notax} tax no wage income. At the other end, {top} have the highest 2026 top rates.</li>
    <li><strong>FICA does not change.</strong> Social Security and Medicare are identical in every state, so they cancel out in a comparison.</li>
    <li><strong>Local tax can flip the answer.</strong> New York City, Philadelphia, Detroit, most Ohio cities and Maryland counties add 1%–4% on top of the state rate.</li>
    <li><strong>Look past income tax.</strong> States without wage tax often raise more from sales and property tax, so compare the whole bill, not just the paycheck.</li>
  </ul>
</section>
""".format(calc=COMPARE_CALC,
           notax=", ".join(STATES[s]["name"] for s in NO_TAX),
           top=", ".join(STATES[s]["name"] for s in top))
    page = HEAD.format(title=title, desc=desc, canonical=BASE + "/compare-take-home-pay-by-state.html",
                       root="", schema=schema, mode="compare", bodyattr="", **ASSETS)
    page += body + FOOT.format(root="", sd="$16,100", today=TODAY, year=YEAR, **ASSETS)
    with open(os.path.join(OUT, "compare-take-home-pay-by-state.html"), "w") as f:
        f.write(page)
    return BASE + "/compare-take-home-pay-by-state.html"


METHOD = """
<p>Every figure on this site comes from the calculator in <code>assets/engine.js</code>, which is also the calculator
that runs in your browser. The static tables on each state page are generated by executing that same file at build
time, so the tables and the interactive calculator can never drift apart.</p>

<h2>Sources</h2>
<ul class="tight">
  <li><strong>Federal brackets and standard deduction:</strong> IRS Revenue Procedure 2025-32 (tax year 2026) — $16,100 single, $32,200 married filing jointly, $24,150 head of household.</li>
  <li><strong>Payroll taxes:</strong> Social Security 6.2% on wages up to the 2026 wage base of $184,500; Medicare 1.45%; additional Medicare 0.9% above $200,000 single / $250,000 joint.</li>
  <li><strong>State brackets:</strong> Tax Foundation, "State Individual Income Tax Rates and Brackets, 2026" (January 2026), which reflects state law as of 1 January 2026.</li>
  <li><strong>Retirement limits:</strong> 401(k) elective deferral limit $24,500 for 2026, plus an $8,000 age-50 catch-up.</li>
</ul>

<h2>Notable 2026 changes built in</h2>
<ul class="tight">
  <li>Ohio moved to a flat 2.75% rate on nonbusiness income over $26,050, and Oklahoma collapsed six brackets into three with a 4.5% top rate.</li>
  <li>Indiana (2.95%), Kentucky (3.50%), Mississippi (4.00%), Montana (5.65%), Nebraska (4.55%) and North Carolina (3.99%) all cut rates for 2026.</li>
  <li>South Carolina's top rate is scheduled to revert to 6.2% on 1 July 2026; the pages here use the January 2026 schedule.</li>
</ul>

<h2>What the calculator does not model</h2>
<ul class="tight">
  <li><strong>Local income taxes.</strong> New York City, Yonkers, Philadelphia, Pittsburgh, Detroit and other Michigan cities, most Ohio cities, Indiana counties, Maryland counties and several Kentucky, Missouri, Alabama and West Virginia cities levy their own tax. Use the local rate box on the calculator.</li>
  <li><strong>State disability and paid-leave programs</strong> (California SDI, New York and New Jersey disability, Washington PFML and WA Cares, Massachusetts and Connecticut PFML, Oregon Paid Leave and others).</li>
  <li><strong>Credits and exemptions.</strong> State personal exemptions, earned income credits and child credits are ignored, which means states that use credits instead of a standard deduction (Connecticut, Illinois, Indiana, Massachusetts, Michigan, New Jersey, Ohio, Pennsylvania, Utah, West Virginia and others) are slightly overstated.</li>
  <li><strong>Head of household state schedules.</strong> Most states publish no separate HOH schedule, so HOH uses single-filer state brackets and the federal HOH standard deduction.</li>
  <li><strong>Itemized deductions, capital gains rates, alternative minimum tax and non-wage income.</strong></li>
</ul>

<h2>How positions are kept current</h2>
<p>The IRS publishes inflation adjustments each autumn and states change rates on 1 January. This site is rebuilt when
those changes land, and the "last updated" date in the footer moves with it. Found an error? Report it and it gets fixed.</p>
"""

PRIVACY = """
<p>Every calculation runs in your browser. Your salary, filing status, state and deductions are never sent to this
site, never logged and never stored in a database. There is no account and no login.</p>
<h2>Analytics and advertising</h2>
<p>This site may run analytics or advertising in future to cover hosting. When that happens those vendors may set
cookies or read a device identifier to measure traffic and select ads. The specific vendors and a plain opt-out will
be listed here before any such tag goes live.</p>
<h2>Contact</h2>
<p>Questions about this policy can be sent to the address on the site owner's profile page.</p>
"""

TERMS = """
<p>These calculators are free to use for general information and planning.</p>
<h2>Estimates, not advice</h2>
<p>The figures are estimates built from published 2026 federal and state schedules. They are not tax, legal or
financial advice, and your employer's withholding may differ. Verify anything that matters with the IRS, your state
revenue department or a qualified professional.</p>
<h2>Accuracy</h2>
<p>Federal and state schedules are reviewed when they change. Questions, corrections and bug reports are welcome.</p>
"""


def simple_page(slug, title, desc, body):
    canonical = "{}/{}.html".format(BASE, slug)
    page = HEAD.format(title=title, desc=desc, canonical=canonical, root="",
                       schema=json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": title}),
                       mode="state", bodyattr="", **ASSETS)
    page += "<h1>{}</h1>".format(title) + body
    page += FOOT.format(root="", sd="$16,100", today=TODAY, year=YEAR, **ASSETS)
    with open(os.path.join(OUT, slug + ".html"), "w") as f:
        f.write(page)
    return canonical


def copy_assets():
    import hashlib
    out = {}
    mapping = {"states-data.js": ("states_js", "js"), "engine.js": ("engine", "js"),
               "app.js": ("app", "js"), "styles.css": ("css", "css")}
    for logical, (key, ext) in mapping.items():
        data = open(os.path.join(ROOT, "assets", logical), "rb").read()
        name = logical.rsplit(".", 1)[0] + "-" + hashlib.md5(data).hexdigest()[:8] + "." + ext
        with open(os.path.join(OUT, "assets", name), "wb") as f:
            f.write(data)
        out[key] = "assets/" + name
    return out


def hourly_page(rate):
    gross = rate * HOURS_PER_YEAR
    title = "${} an Hour Is How Much a Year? (2026 Take-Home Pay)".format(rate)
    desc = ("At ${0} an hour you earn {1} a year before tax. See the monthly, biweekly and weekly figures, plus "
            "what actually lands in your account after federal tax and FICA in Texas, Florida, California, "
            "New York and Illinois.").format(rate, usd(gross))
    slug = "{}-an-hour-is-how-much-a-year".format(rate)
    canonical = "{}/{}.html".format(BASE, slug)
    rows = []
    for hours in (40, 35, 30, 25, 20):
        annual = rate * hours * 52
        rows.append("<tr><td>{} hours / week</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            hours, usd(annual), usd(annual / 12), usd(annual / 26)))
    ref_rows = []
    for st in REF_STATES:
        r = EX["ref|{}|{}".format(gross, st)]
        ref_rows.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            STATES[st]["name"], usd(r["federalTax"]), usd(r["fica"]["total"]), usd(r["stateTax"]),
            usd(r["netAnnual"])))
    r_tx = EX["ref|{}|texas".format(gross)]
    near = [x for x in HOURLY_RATES if x != rate][:6]
    schema = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": "How much is ${} an hour per year?".format(rate),
         "acceptedAnswer": {"@type": "Answer", "text": "At ${} an hour for 40 hours a week, 52 weeks a year, gross pay is {} before tax, or {} a month.".format(rate, usd(gross), usd(gross / 12))}},
        {"@type": "Question", "name": "What is ${} an hour after tax?".format(rate),
         "acceptedAnswer": {"@type": "Answer", "text": "For a single filer with no state income tax, {} a year gross leaves about {} after federal income tax and FICA.".format(usd(gross), usd(r_tx["netAnnual"]))}}]})
    body = """
<h1>${rate} an Hour Is How Much a Year?</h1>
<p class="lede">At <strong>${rate} an hour</strong>, a full-time schedule of 40 hours a week for 52 weeks pays
<strong>{gross}</strong> a year before tax — {monthly} a month, {biweekly} every two weeks. Below is the same rate at
other weekly hours, and what is left after tax in five different states.</p>

<section>
  <h2>${rate} an hour by hours worked</h2>
  <table class="examples">
    <thead><tr><th>Schedule</th><th>Per year</th><th>Per month</th><th>Every 2 weeks</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="muted">Assumes 52 paid weeks. Unpaid leave or overtime at 1.5x changes the total.</p>
</section>

<section>
  <h2>What ${rate} an hour is after tax</h2>
  <table class="examples">
    <thead><tr><th>State</th><th>Federal tax</th><th>FICA</th><th>State tax</th><th>Take-home / year</th></tr></thead>
    <tbody>{ref_rows}</tbody>
  </table>
  <p class="muted">Single filer, no pre-tax deductions, {year} rates. Local taxes are excluded — see each state page.</p>
</section>

{calc}

<section>
  <h2>Key figures at ${rate} an hour</h2>
  <table class="facts">
    <tr><th>Per hour</th><td>${rate}</td></tr>
    <tr><th>Per day (8 hours)</th><td>{daily}</td></tr>
    <tr><th>Per week (40 hours)</th><td>{weekly}</td></tr>
    <tr><th>Per month</th><td>{monthly}</td></tr>
    <tr><th>Per year (2,080 hours)</th><td>{gross}</td></tr>
    <tr><th>Take-home, no state income tax</th><td>{net_tx}</td></tr>
  </table>
</section>

<section>
  <h2>Nearby hourly rates</h2>
  <p class="statelinks">{near}</p>
  <p><a href="index.html">See take-home pay for all 50 states →</a></p>
</section>
<script type="application/ld+json">{schema}</script>
""".format(rate=rate, gross=usd(gross), monthly=usd(gross / 12), biweekly=usd(gross / 26),
           daily=usd(rate * 8), weekly=usd(rate * 40), rows="\n".join(rows), ref_rows="\n".join(ref_rows),
           calc=CALC, net_tx=usd(r_tx["netAnnual"]), year=YEAR,
           near=" ".join('<a href="{0}-an-hour-is-how-much-a-year.html">${0}/hour</a>'.format(x) for x in near),
           schema=schema)
    page = HEAD.format(title=title, desc=desc, canonical=canonical, root="",
                       schema=json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": title}),
                       mode="state", bodyattr="", **ASSETS) + body
    page += FOOT.format(root="", sd="$16,100", today=TODAY, year=YEAR, **ASSETS)
    with open(os.path.join(OUT, slug + ".html"), "w") as f:
        f.write(page)
    return canonical


def salary_page(amount):
    hourly = amount / HOURS_PER_YEAR
    title = "{} a Year Is How Much an Hour? (2026 Take-Home Pay)".format(usd(amount))
    desc = ("{} a year works out to {:.2f} an hour at 40 hours a week. See the monthly and biweekly figures and "
            "what is left after tax in Texas, Florida, California, New York and Illinois.").format(usd(amount), hourly)
    slug = "{}-a-year-is-how-much-an-hour".format(amount)
    canonical = "{}/{}.html".format(BASE, slug)
    rows = []
    for hours in (40, 35, 30, 25, 20):
        h = amount / (hours * 52)
        rows.append("<tr><td>{} hours / week</td><td>${:.2f}</td><td>{} per month</td></tr>".format(
            hours, h, usd(amount / 12)))
    ref_rows = []
    for st in REF_STATES:
        r = EX["ref|{}|{}".format(amount, st)]
        ref_rows.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            STATES[st]["name"], usd(r["federalTax"]), usd(r["fica"]["total"]), usd(r["stateTax"]),
            usd(r["netAnnual"]), usd(r["netPerPeriod"]["monthly"])))
    near = [x for x in SALARIES if x != amount][:6]
    body = """
<h1>{amount} a Year Is How Much an Hour?</h1>
<p class="lede"><strong>{amount} a year</strong> is <strong>${hourly:.2f} an hour</strong> on a 40-hour week
(2,080 hours a year), or {monthly} a month, {biweekly} every two weeks, {weekly} a week. After federal tax and FICA
a single filer keeps about {net_tx} of it in a state with no income tax.</p>

<section>
  <h2>{amount} a year at other schedules</h2>
  <table class="examples">
    <thead><tr><th>Hours / week</th><th>Hourly rate</th><th>Monthly gross</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</section>

<section>
  <h2>{amount} after tax, state by state</h2>
  <table class="examples">
    <thead><tr><th>State</th><th>Federal tax</th><th>FICA</th><th>State tax</th><th>Take-home / year</th><th>/ month</th></tr></thead>
    <tbody>{ref_rows}</tbody>
  </table>
  <p class="muted">Single filer, no pre-tax deductions, {year} rates, local taxes excluded.</p>
</section>

{calc}

<section>
  <h2>Breakdown of {amount} a year</h2>
  <table class="facts">
    <tr><th>Per hour (40-hour week)</th><td>${hourly:.2f}</td></tr>
    <tr><th>Per week</th><td>{weekly}</td></tr>
    <tr><th>Every two weeks</th><td>{biweekly}</td></tr>
    <tr><th>Per month</th><td>{monthly}</td></tr>
    <tr><th>Per year</th><td>{amount}</td></tr>
    <tr><th>Take-home, no state income tax</th><td>{net_tx}</td></tr>
  </table>
</section>

<section>
  <h2>Nearby salaries</h2>
  <p class="statelinks">{near}</p>
  <p><a href="compare-take-home-pay-by-state.html">Compare two states side by side →</a></p>
</section>
""".format(amount=usd(amount), hourly=hourly, monthly=usd(amount / 12), biweekly=usd(amount / 26),
           weekly=usd(amount / 52), rows="\n".join(rows), ref_rows="\n".join(ref_rows), calc=CALC,
           net_tx=usd(EX["ref|{}|texas".format(amount)]["netAnnual"]), year=YEAR,
           near=" ".join('<a href="{0}-a-year-is-how-much-an-hour.html">{1}</a>'.format(x, usd(x)) for x in near))
    page = HEAD.format(title=title, desc=desc, canonical=canonical, root="",
                       schema=json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": title}),
                       mode="state", bodyattr="", **ASSETS) + body
    page += FOOT.format(root="", sd="$16,100", today=TODAY, year=YEAR, **ASSETS)
    with open(os.path.join(OUT, slug + ".html"), "w") as f:
        f.write(page)
    return canonical


def main():
    global EX, ASSETS
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets"))
    # engine data as a browser script and as a JSON module for Node
    with open(os.path.join(ROOT, "assets", "states-data.js"), "w") as f:
        f.write("window.STATE_DATA = " + json.dumps({"states": STATES}) + ";\n")
    with open(os.path.join(ROOT, "data", "states-data.json"), "w") as f:
        json.dump(STATES, f)
    EX = node_examples()
    ASSETS = copy_assets()
    urls = [index_page(), compare_page()]
    for slug in ORDER:
        urls.append(state_page(slug))
    for rate in HOURLY_RATES:
        urls.append(hourly_page(rate))
    for amount in SALARIES:
        urls.append(salary_page(amount))
    urls.append(simple_page("method", "Method &amp; sources",
                            "Which IRS, SSA and state figures these paycheck estimates use, what is excluded and how the site is kept current.", METHOD))
    urls.append(simple_page("privacy", "Privacy policy",
                            "What this site collects (nothing you type leaves your browser) and how analytics and ads are handled.", PRIVACY))
    urls.append(simple_page("terms", "Terms of use",
                            "Plain-language terms for these free 2026 paycheck calculators.", TERMS))
    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write("User-agent: *\nAllow: /\n\nSitemap: {}/sitemap.xml\n".format(BASE))
    with open(os.path.join(OUT, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            f.write("  <url><loc>{}</loc><lastmod>{}</lastmod></url>\n".format(u, TODAY))
        f.write("</urlset>\n")
    print("generated {} pages".format(len(urls)))


if __name__ == "__main__":
    main()
