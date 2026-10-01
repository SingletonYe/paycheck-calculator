/* Take-home pay engine — tax year 2026.
   Federal: IRS Rev. Proc. 2025-32 (2026 brackets, standard deduction).
   Payroll: SSA 2026 Social Security wage base $184,500; 2026 401(k) limit $24,500.
   State: Tax Foundation, "State Individual Income Tax Rates and Brackets, 2026" (data/states.json).
   Pure functions; runs unchanged in the browser and in Node. */
(function (root) {
  'use strict';

  var YEAR = 2026;
  var STANDARD_DEDUCTION = { single: 16100, mfj: 32200, hoh: 24150 };

  var BRACKETS = {
    single: [12400, 50400, 105700, 201775, 256225, 640600, Infinity],
    mfj:    [24800, 100800, 211400, 403550, 512450, 768700, Infinity],
    hoh:    [17700, 67450, 105700, 201750, 256200, 640600, Infinity]
  };
  var RATES = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37];

  var FICA = {
    socialSecurityRate: 0.062,
    socialSecurityWageBase: 184500,
    medicareRate: 0.0145,
    additionalMedicareRate: 0.009,
    additionalMedicareThreshold: { single: 200000, hoh: 200000, mfj: 250000 }
  };

  var LIMITS = { k401: 24500, k401CatchUp: 8000 };
  var PAY_PERIODS = { annual: 1, monthly: 12, semimonthly: 24, biweekly: 26, weekly: 52 };
  var STATES = (root.STATE_DATA && root.STATE_DATA.states) || {};

  function stateInfo(slug) {
    if (!slug) return null;
    return STATES[slug] || null;
  }

  /* State brackets for a filing status. Head of household uses single-filer brackets
     unless the state publishes a separate schedule (most do not). */
  function stateBrackets(slug, filingStatus) {
    var s = stateInfo(slug);
    if (!s) return null;
    var key = filingStatus === 'mfj' ? 'mfj' : 'single';
    return s[key] && s[key].length ? s[key] : null;
  }

  function stateStandardDeduction(slug, filingStatus) {
    var s = stateInfo(slug);
    if (!s) return 0;
    return filingStatus === 'mfj' ? (s.sdMfj || 0) : (s.sdSingle || 0);
  }

  /* Employee-paid state payroll programs (SDI, paid family leave), separate from income tax. */
  function statePayrollTax(slug, gross) {
    var s = stateInfo(slug);
    var items = [], total = 0;
    if (!s || !s.payroll) return { items: items, total: 0 };
    for (var i = 0; i < s.payroll.length; i++) {
      var p = s.payroll[i], amount = 0;
      if (p.flat != null) amount = p.flat;
      else {
        var wages = p.base ? Math.min(gross, p.base) : gross;
        amount = wages * p.rate;
        if (p.cap != null) amount = Math.min(amount, p.cap);
      }
      items.push({ label: p.label, amount: amount });
      total += amount;
    }
    return { items: items, total: total };
  }

  function structure(slug) {
    var s = stateInfo(slug);
    if (!s || !(s.single || []).length) return 'none';
    return s.single.length === 1 ? 'flat' : 'graduated';
  }

  function topStateRate(slug) {
    var b = stateBrackets(slug, 'single');
    if (!b) return 0;
    return b[b.length - 1].rate;
  }

  function bracketTax(taxable, brackets) {
    if (!brackets || !brackets.length) return { tax: 0, bands: [] };
    var tax = 0, bands = [];
    for (var i = 0; i < brackets.length; i++) {
      var from = brackets[i].over;
      var to = brackets[i + 1] ? brackets[i + 1].over : Infinity;
      if (taxable <= from) break;
      var slice = Math.min(taxable, to) - from;
      var amount = slice * brackets[i].rate;
      tax += amount;
      bands.push({ rate: brackets[i].rate, from: from, to: to === Infinity ? null : to, taxed: slice, tax: amount });
    }
    return { tax: tax, bands: bands };
  }

  function federalTax(taxable, filingStatus) {
    var tops = BRACKETS[filingStatus] || BRACKETS.single;
    var tax = 0, bands = [], lower = 0;
    for (var i = 0; i < tops.length; i++) {
      if (taxable <= lower) break;
      var slice = Math.min(taxable, tops[i]) - lower;
      var amount = slice * RATES[i];
      tax += amount;
      bands.push({ rate: RATES[i], from: lower, to: tops[i] === Infinity ? null : tops[i], taxed: slice, tax: amount });
      lower = tops[i];
    }
    return { tax: tax, bands: bands };
  }

  function computeFica(gross, filingStatus) {
    var ss = Math.min(gross, FICA.socialSecurityWageBase) * FICA.socialSecurityRate;
    var medicare = gross * FICA.medicareRate;
    var threshold = FICA.additionalMedicareThreshold[filingStatus] || 200000;
    var addl = gross > threshold ? (gross - threshold) * FICA.additionalMedicareRate : 0;
    return { socialSecurity: ss, medicare: medicare, additionalMedicare: addl, total: ss + medicare + addl };
  }

  function takeHome(o) {
    var gross = Math.max(0, +o.grossAnnual || 0);
    var filing = BRACKETS[o.filingStatus] ? o.filingStatus : 'single';
    var preTax = Math.min(Math.max(0, +o.preTaxAnnual || 0), gross);
    var slug = o.stateSlug || null;

    var federalTaxable = Math.max(0, gross - preTax - STANDARD_DEDUCTION[filing]);
    var fed = federalTax(federalTaxable, filing);
    var fica = computeFica(gross, filing);   // pre-tax 401(k) deferrals do not reduce FICA

    var sdState = stateStandardDeduction(slug, filing);
    var stateTaxable = Math.max(0, gross - preTax - sdState);
    var sb = stateBrackets(slug, filing);
    var st = bracketTax(stateTaxable, sb);

    var localRate = Math.max(0, +o.localRate || 0);
    var localTax = (gross - preTax) * localRate;

    var statePayroll = statePayrollTax(slug, gross);
    var totalTax = fed.tax + fica.total + st.tax + localTax + statePayroll.total;
    var net = gross - preTax - totalTax;

    return {
      year: YEAR,
      stateSlug: slug,
      filingStatus: filing,
      grossAnnual: gross,
      preTaxAnnual: preTax,
      standardDeduction: STANDARD_DEDUCTION[filing],
      taxableIncome: federalTaxable,
      federalTax: fed.tax,
      federalBands: fed.bands,
      fica: fica,
      stateStandardDeduction: sdState,
      stateTaxable: stateTaxable,
      stateTax: st.tax,
      stateBands: st.bands,
      localRate: localRate,
      localTax: localTax,
      statePayrollItems: statePayroll.items,
      statePayrollTax: statePayroll.total,
      hasStateTax: !!sb,
      totalTax: totalTax,
      netAnnual: net,
      netPerPeriod: Object.keys(PAY_PERIODS).reduce(function (acc, k) {
        acc[k] = net / PAY_PERIODS[k]; return acc;
      }, {}),
      effectiveTotalRate: gross ? totalTax / gross : 0,
      effectiveFederalRate: gross ? fed.tax / gross : 0,
      marginalRate: marginalRate(federalTaxable, filing)
    };
  }

  function marginalRate(taxable, filing) {
    var tops = BRACKETS[filing] || BRACKETS.single;
    for (var i = 0; i < tops.length; i++) if (taxable <= tops[i]) return RATES[i];
    return RATES[RATES.length - 1];
  }

  function money(n) {
    return (Math.round(n * 100) / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
  }
  function money2(n) {
    return (Math.round(n * 100) / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function pct(n) { return (n * 100).toFixed(n < 0.01 ? 2 : 1) + '%'; }
  function stateList() {
    return Object.keys(STATES).sort(function (a, b) { return STATES[a].name < STATES[b].name ? -1 : 1; });
  }

  var api = {
    YEAR: YEAR, STANDARD_DEDUCTION: STANDARD_DEDUCTION, BRACKETS: BRACKETS, RATES: RATES,
    FICA: FICA, LIMITS: LIMITS, PAY_PERIODS: PAY_PERIODS, STATES: STATES,
    takeHome: takeHome, bracketTax: bracketTax, federalTax: federalTax, computeFica: computeFica,
    stateInfo: stateInfo, stateBrackets: stateBrackets, stateStandardDeduction: stateStandardDeduction,
    structure: structure, topStateRate: topStateRate, stateList: stateList, statePayrollTax: statePayrollTax,
    marginalRate: marginalRate, money: money, money2: money2, pct: pct
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.ENGINE = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
