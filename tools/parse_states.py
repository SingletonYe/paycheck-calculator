"""Parse the Tax Foundation 2026 state income tax workbook into states.json.
Source file: https://taxfoundation.org/wp-content/uploads/2026/02/2026-State-Individual-Income-Tax-Rates-Brackets.xlsx
Layout: A=state, B/C/D = single rate/'>'/bracket, E/F/G = MFJ rate/'>'/bracket, H=SD single, I=SD couple."""
import zipfile, json, re, xml.etree.ElementTree as ET

XLSX = 'paycalc_data/tf2026.xlsx'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

NAMES = {
 "Ala.":"Alabama","Alaska":"Alaska","Ariz.":"Arizona","Ark.":"Arkansas","Calif.":"California","Colo.":"Colorado",
 "Conn.":"Connecticut","Del.":"Delaware","D.C.":"District of Columbia","Fla.":"Florida","Ga.":"Georgia",
 "Hawaii":"Hawaii","Idaho":"Idaho","Ill.":"Illinois","Ind.":"Indiana","Iowa":"Iowa","Kans.":"Kansas",
 "Ky.":"Kentucky","La.":"Louisiana","Maine":"Maine","Md.":"Maryland","Mass.":"Massachusetts","Mich.":"Michigan",
 "Minn.":"Minnesota","Miss.":"Mississippi","Mo.":"Missouri","Mont.":"Montana","Nebr.":"Nebraska","Nev.":"Nevada",
 "N.H.":"New Hampshire","N.J.":"New Jersey","N.M.":"New Mexico","N.Y.":"New York","N.C.":"North Carolina",
 "N.D.":"North Dakota","Ohio":"Ohio","Okla.":"Oklahoma","Ore.":"Oregon","Pa.":"Pennsylvania","R.I.":"Rhode Island",
 "S.C.":"South Carolina","S.D.":"South Dakota","Tenn.":"Tennessee","Tex.":"Texas","Utah":"Utah","Vt.":"Vermont",
 "Va.":"Virginia","Wash.":"Washington","W.Va.":"West Virginia","Wis.":"Wisconsin","Wyo.":"Wyoming",
}
NO_TAX = ["Alaska","Florida","Nevada","New Hampshire","South Dakota","Tennessee","Texas","Washington","Wyoming"]


def read_rows(sheet='xl/worksheets/sheet1.xml'):
    z = zipfile.ZipFile(XLSX)
    strings = [''.join(t.text or '' for t in si.iter(NS + 't'))
               for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(NS + 'si')]
    sh = ET.fromstring(z.read(sheet))
    for r in sh.find(NS + 'sheetData'):
        row = {}
        for c in r.findall(NS + 'c'):
            col = re.match(r'[A-Z]+', c.get('r')).group(0)
            v = c.find(NS + 'v'); t = c.get('t')
            val = v.text if v is not None else None
            if t == 's' and val is not None:
                val = strings[int(val)]
            row[col] = val
        yield row


def num(x):
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f


def parse():
    states = {}
    cur = None
    for row in read_rows():
        label = (row.get('A') or '').strip()
        if label and not label.startswith('('):
            for key, name in NAMES.items():
                if label == key or label.startswith(key + ' ') or label.startswith(key + '('):
                    cur = name
                    states.setdefault(name, {"single": [], "mfj": [], "sd_single": None, "sd_mfj": None,
                                             "capital_gains_only": False})
                    break
            else:
                if 'Capital gains' in label:      # Washington capital-gains excise, not a wage tax
                    if cur: states[cur]["capital_gains_only"] = True
                    continue
                if re.match(r'^[A-Z][a-z]+$', label) or label in NAMES.values():
                    cur = None                     # left the table (footnotes etc.)
        if cur is None:
            continue
        for rate_col, br_col, key in (('B', 'D', 'single'), ('E', 'G', 'mfj')):
            rate = num(row.get(rate_col))
            if rate is None or rate <= 0:
                continue
            if rate > 1:
                rate /= 100.0
            over = num(row.get(br_col)) or 0.0
            entry = {"rate": round(rate, 5), "over": over}
            if entry not in states[cur][key]:
                states[cur][key].append(entry)
        if states[cur]["sd_single"] is None:
            v = num(row.get('H'))
            if v is not None and v > 0:
                states[cur]["sd_single"] = v
        if states[cur]["sd_mfj"] is None:
            v = num(row.get('I'))
            if v is not None and v > 0:
                states[cur]["sd_mfj"] = v
    for d in states.values():
        for k in ("single", "mfj"):
            d[k].sort(key=lambda b: b["over"])
    return states


if __name__ == "__main__":
    st = parse()
    for s in NO_TAX:                       # wage income is not taxed in these states
        st.setdefault(s, {"single": [], "mfj": [], "sd_single": None, "sd_mfj": None, "capital_gains_only": False})
        st[s]["single"] = []; st[s]["mfj"] = []
    json.dump(st, open('paycalc_data/states.json', 'w'), indent=1, sort_keys=True)
    print(len(st), "jurisdictions")
    for n in sorted(st):
        d = st[n]
        print(f"{n:22} sd={str(d['sd_single']):>7} n_single={len(d['single']):>2} n_mfj={len(d['mfj']):>2} top={d['single'][-1]['rate'] if d['single'] else 0}")
