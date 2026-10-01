/* UI for the paycheck calculators. All math is in engine.js. */
(function () {
  'use strict';
  var E = window.ENGINE;
  if (!E) return;
  var body = document.body;
  var mode = body.getAttribute('data-mode') || 'state';
  var WEEKS = 52;

  var $ = function (id) { return document.getElementById(id); };
  function num(v, d) { var n = parseFloat(v); return isNaN(n) ? d : n; }
  function annualize(amount, freq, hours) {
    switch (freq) {
      case 'annual': return amount;
      case 'monthly': return amount * 12;
      case 'semimonthly': return amount * 24;
      case 'biweekly': return amount * 26;
      case 'weekly': return amount * 52;
      case 'hourly': return amount * hours * WEEKS;
      default: return amount;
    }
  }
  var DIVISOR = { annual: 1, monthly: 12, semimonthly: 24, biweekly: 26, weekly: 52 };
  var NOUN = { annual: 'per year', monthly: 'per month', semimonthly: 'per semi-monthly check',
               biweekly: 'per 2-week check', weekly: 'per week', hourly: 'per hour' };

  function cell(v, divisor) {
    var n = v / divisor;
    var abs = Math.round(Math.abs(n)) < 1 ? 0 : Math.abs(n);
    return (n < 0 && abs > 0 ? '\u2212' : '') + E.money(abs);
  }

  function fillStateSelect(sel, selected) {
    if (!sel) return;
    var html = E.stateList().map(function (slug) {
      var s = E.STATES[slug];
      return '<option value="' + slug + '"' + (slug === selected ? ' selected' : '') + '>' + s.name + '</option>';
    }).join('');
    sel.innerHTML = html;
  }

  function currentState() {
    var sel = $('state');
    if (sel) return sel.value;
    return body.getAttribute('data-state') || null;
  }

  function renderSingle() {
    var amount = num($('amount').value, 0);
    var freq = $('freq').value;
    var hours = num($('hours') && $('hours').value, 40);
    var status = $('status').value;
    var pretax = num($('pretax').value, 0);
    var localPct = num($('local') && $('local').value, 0);
    var slug = currentState();

    var grossAnnual = annualize(amount, freq, hours);
    var r = E.takeHome({
      grossAnnual: grossAnnual, filingStatus: status, preTaxAnnual: pretax,
      stateSlug: slug, localRate: localPct / 100
    });

    var divisor = freq === 'hourly' ? (hours * WEEKS) : (DIVISOR[freq] || 26);
    var perCheck = r.netAnnual / divisor;

    $('netAnnual').textContent = E.money(r.netAnnual);
    $('netPeriod').textContent = freq === 'hourly' ? E.money2(perCheck) : E.money(perCheck);
    $('netPeriodSub').textContent = NOUN[freq];
    $('netAnnualSub').textContent = 'per year, after ' + E.money(r.totalTax) + ' of tax';

    var rows = [['Gross pay', r.grossAnnual],
                ['Pre-tax deductions', -r.preTaxAnnual],
                ['Federal income tax', -r.federalTax],
                ['Social Security (6.2%)', -r.fica.socialSecurity],
                ['Medicare (1.45%)', -r.fica.medicare]];
    if (r.fica.additionalMedicare > 0) rows.push(['Additional Medicare (0.9%)', -r.fica.additionalMedicare]);
    rows.push([E.STATES[slug] ? E.STATES[slug].name + ' income tax' : 'State income tax', -r.stateTax]);
    (r.statePayrollItems || []).forEach(function (item) { rows.push([item.label, -item.amount]); });
    if (r.localRate > 0) rows.push(['Local income tax (' + r.localRate.toFixed(3).replace(/0+$/, '').replace(/\.$/, '') + '%)', -r.localTax]);

    $('rows').innerHTML = rows.map(function (row) {
      return '<tr><td>' + row[0] + '</td><td>' + cell(row[1], 1) + '</td><td>' + cell(row[1], divisor) + '</td></tr>';
    }).join('');
    $('footNet').textContent = E.money(r.netAnnual);
    $('footNetPeriod').textContent = E.money(perCheck);

    var st = E.STATES[slug];
    $('effLine').innerHTML = 'Effective total rate <strong>' + E.pct(r.effectiveTotalRate) + '</strong> · ' +
      'marginal federal rate ' + E.pct(r.marginalRate) + ' · ' +
      'state taxable income ' + E.money(r.stateTaxable) + ' after a ' + E.money(r.stateStandardDeduction) + ' state standard deduction' +
      (st && st.local ? ' · <span class="warn">local taxes not included</span>' : '') + '.';

    var bands = r.federalBands.map(function (b) {
      return '<li><strong>' + (b.rate * 100).toFixed(0) + '% federal</strong> on ' +
        (b.to ? E.money(b.from) + ' – ' + E.money(b.to) : 'over ' + E.money(b.from)) +
        ' → ' + E.money(b.tax) + '</li>';
    }).join('');
    var sbands = r.stateBands.map(function (b) {
      var rate = (b.rate * 100).toFixed(b.rate * 100 < 1 ? 2 : 1).replace(/\.0$/, '');
      return '<li><strong>' + rate + '% ' + (st ? st.name : 'state') + '</strong> on ' +
        (b.to ? E.money(b.from) + ' – ' + E.money(b.to) : 'over ' + E.money(b.from)) +
        ' → ' + E.money(b.tax) + '</li>';
    }).join('');
    $('bands').innerHTML = bands + (sbands || '<li>No state income tax on wages.</li>');
  }

  function renderCompare() {
    var amount = num($('c-amount').value, 0);
    var status = $('c-status').value;
    var a = $('c-a').value, b = $('c-b').value;
    var ra = E.takeHome({ grossAnnual: amount, filingStatus: status, stateSlug: a });
    var rb = E.takeHome({ grossAnnual: amount, filingStatus: status, stateSlug: b });
    var diff = rb.netAnnual - ra.netAnnual;

    $('c-name-a').textContent = E.STATES[a].name;
    $('c-name-b').textContent = E.STATES[b].name;
    $('c-net-a').textContent = E.money(ra.netAnnual);
    $('c-net-b').textContent = E.money(rb.netAnnual);
    $('c-tax-a').textContent = E.money(ra.stateTax);
    $('c-tax-b').textContent = E.money(rb.stateTax);
    $('c-month-a').textContent = E.money(ra.netPerPeriod.monthly);
    $('c-month-b').textContent = E.money(rb.netPerPeriod.monthly);
    $('c-verdict').innerHTML = diff === 0
      ? 'These two states leave you with the same take-home pay on ' + E.money(amount) + '.'
      : 'Living in <strong>' + E.STATES[diff > 0 ? b : a].name + '</strong> leaves you <strong>' +
        E.money(Math.abs(diff)) + ' more per year</strong> (' + E.money(Math.abs(diff) / 12) +
        ' per month) than ' + E.STATES[diff > 0 ? a : b].name + ' on a ' + E.money(amount) + ' salary.';
    $('c-table').innerHTML = [[E.STATES[a].name, ra], [E.STATES[b].name, rb]].map(function (pair) {
      var r = pair[1];
      return '<tr><td data-label="State">' + pair[0] + '</td><td data-label="Federal">' + E.money(r.federalTax) +
        '</td><td data-label="FICA">' + E.money(r.fica.total) + '</td><td data-label="State tax">' +
        E.money(r.stateTax) + '</td><td data-label="Take-home">' + E.money(r.netAnnual) +
        '</td><td data-label="Effective rate">' + E.pct(r.effectiveTotalRate) + '</td></tr>';
    }).join('');
  }

  var form = $('calc') || $('compare');
  if (form) {
    if (mode === 'compare') {
      fillStateSelect($('c-a'), 'california');
      fillStateSelect($('c-b'), 'texas');
      form.addEventListener('input', renderCompare);
      form.addEventListener('change', renderCompare);
      form.addEventListener('submit', function (e) { e.preventDefault(); renderCompare(); });
      renderCompare();
    } else {
      if ($('state')) fillStateSelect($('state'), body.getAttribute('data-state') || 'texas');
      var lastFreq = $('freq').value;
      $('freq').addEventListener('change', function () {
        // Keep the same annual pay when the period changes, so switching to "two weeks"
        // turns 60000 a year into 2308 per check instead of 1.56M a year.
        var prevHours = num($('hours') && $('hours').value, 40);
        var annual = annualize(num($('amount').value, 0), lastFreq, prevHours);
        var next = $('freq').value;
        var nextHours = num($('hours') && $('hours').value, 40);
        var divisor = next === 'hourly' ? nextHours * WEEKS : (DIVISOR[next] || 1);
        if (divisor > 0) $('amount').value = Math.round(annual / divisor * 100) / 100;
        lastFreq = next;
        $('hoursField').hidden = next !== 'hourly';
        renderSingle();
      });
      $('hoursField').hidden = $('freq').value !== 'hourly';
      form.addEventListener('input', renderSingle);
      form.addEventListener('change', renderSingle);
      form.addEventListener('submit', function (e) { e.preventDefault(); renderSingle(); });
      renderSingle();
    }
  }
})();
