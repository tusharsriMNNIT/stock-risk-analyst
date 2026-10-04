"""Builds the single self-contained HTML report (2 pages) and a plain-text export."""
import json
import math
from datetime import datetime
from html import escape as esc

from analysis import label_for, tone

NA = '<span class="na">N/A</span>'
COL = {"pos": "var(--pos)", "warn": "var(--warn)", "neg": "var(--neg)", None: "var(--mut)"}


def indian(n, dec=0):
    if n is None:
        return None
    s = f"{abs(n):.{dec}f}"
    ip, _, fp = s.partition(".")
    if len(ip) > 3:
        head, tail = ip[:-3], ip[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        ip = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + ip + ("." + fp if fp else "")


def f(v, dec=1, pre="", suf=""):
    return NA if v is None else f"{pre}{v:,.{dec}f}{suf}"


def cr(v):
    return NA if v is None else f"₹{indian(v)} Cr"


def signed(v, dec=1, suf="%"):
    if v is None:
        return NA
    c = "pos" if v >= 0 else "neg"
    return f'<span class="{c}">{v:+.{dec}f}{suf}</span>'


def card(title, value, sub, t):
    return (f'<div class="card" style="--c:{COL[t]}"><div class="ct">{esc(title)}</div>'
            f'<div class="cv mono">{value}</div><div class="cs">{sub}</div></div>')


def gauge(score, label):
    cx, cy, r = 150, 140, 110
    def pt(p, rad=r):
        a = math.pi * (1 - p / 100)
        return cx + rad * math.cos(a), cy - rad * math.sin(a)
    zones = [(0, 25, "var(--pos)"), (25, 45, "#84cc16"), (45, 62, "var(--warn)"), (62, 80, "#f97316"), (80, 100, "var(--neg)")]
    arcs = ""
    for a, b, c in zones:
        x1, y1 = pt(a)
        x2, y2 = pt(b)
        arcs += f'<path d="M{x1:.1f},{y1:.1f} A{r},{r} 0 0 1 {x2:.1f},{y2:.1f}" stroke="{c}" stroke-width="16" fill="none" opacity=".9"/>'
    if score is None:
        return '<svg viewBox="0 0 300 190" class="gauge">' + arcs + '<text x="150" y="130" text-anchor="middle" class="mono" fill="var(--mut)" font-size="20">N/A</text></svg>'
    nx, ny = pt(score, 88)
    return (f'<svg viewBox="0 0 300 190" class="gauge">{arcs}'
            f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#e5e7eb" stroke-width="3" stroke-linecap="round"/>'
            f'<circle cx="{cx}" cy="{cy}" r="7" fill="#e5e7eb"/>'
            f'<text x="150" y="172" text-anchor="middle" class="mono" fill="#fff" font-size="30" font-weight="700">{score:.0f}</text>'
            f'<text x="150" y="188" text-anchor="middle" class="mono" fill="{COL[tone(score)]}" font-size="14" font-weight="700">{label}</text>'
            f'<text x="38" y="158" fill="var(--mut)" font-size="10" class="mono">0</text><text x="252" y="158" fill="var(--mut)" font-size="10" class="mono">100</text></svg>')


def price_chart(h):
    if h is None:
        return '<div class="na box">12-month price history unavailable from the market-data fetch.</div>'
    close = list(h["Close"])
    dates = list(h.index)
    n = len(close)
    W, H, L, Rr, T, B = 920, 330, 62, 24, 38, 34
    lo, hi = min(close), max(close)
    pad = (hi - lo) * 0.08 or 1
    lo, hi = lo - pad, hi + pad
    X = lambda i: L + i * (W - L - Rr) / (n - 1)
    Y = lambda v: T + (hi - v) / (hi - lo) * (H - T - B)
    line = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(close))
    area = f"{L},{H-B} {line} {X(n-1):.1f},{H-B}"
    s = [f'<svg viewBox="0 0 {W} {H}" class="chart"><defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">'
         '<stop offset="0" stop-color="#10b981" stop-opacity=".28"/><stop offset="1" stop-color="#10b981" stop-opacity="0"/></linearGradient></defs>']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        y = Y(v)
        s.append(f'<line x1="{L}" x2="{W-Rr}" y1="{y:.1f}" y2="{y:.1f}" stroke="#1c1f2b"/><text x="{L-8}" y="{y+4:.1f}" text-anchor="end" fill="var(--mut)" font-size="11" class="mono">{v:,.0f}</text>')
    last_m = None
    for i, d in enumerate(dates):
        if d.month != last_m:
            last_m = d.month
            s.append(f'<text x="{X(i):.1f}" y="{H-12}" fill="var(--mut)" font-size="11" class="mono">{d.strftime("%b %y")}</text>')
    s.append(f'<polygon points="{area}" fill="url(#ag)"/><polyline points="{line}" fill="none" stroke="#10b981" stroke-width="2" stroke-linejoin="round"/>')
    rets = [(close[i] / close[i - 1] - 1, i) for i in range(1, n)]
    marks = [("Closing high", close.index(max(close)), "var(--pos)", -1), ("Closing low", close.index(min(close)), "var(--neg)", 1),
             ("Biggest 1D drop %+.1f%%" % (min(rets)[0] * 100), min(rets)[1], "var(--neg)", 1),
             ("Biggest 1D gain %+.1f%%" % (max(rets)[0] * 100), max(rets)[1], "var(--pos)", -1), ("Latest", n - 1, "#e5e7eb", -1)]
    seen = []
    if marks[1][1] == n - 1:  # low is the latest close: merge labels
        marks[1] = ("Closing low = latest", n - 1, "var(--neg)", 1)
        marks.pop()
    for name, i, c, side in marks:
        if any(abs(i - j) < 6 and sd == side for j, sd in seen):
            side = -side
        seen.append((i, side))
        x, y = X(i), Y(close[i])
        txt = f"{name} · {close[i]:,.1f} · {dates[i].strftime('%d %b %y')}"
        anchor = "start" if x < 260 else "end" if x > W - 260 else "middle"
        ty = y + side * 26
        ty = min(max(ty, T - 6), H - B - 6)
        s.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{ty - side*8 + (4 if side>0 else 0):.1f}" stroke="{c}" stroke-dasharray="2 3"/>'
                 f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{c}" stroke="#08090d" stroke-width="2"/>'
                 f'<text x="{x:.1f}" y="{ty:.1f}" text-anchor="{anchor}" fill="{c}" font-size="11" class="mono" paint-order="stroke" stroke="#08090d" stroke-width="4">{esc(txt)}</text>')
    s.append("</svg>")
    return "".join(s)


def score_rows(items):
    out = ""
    for k, (v, sc) in items.items():
        vtxt = NA if v is None else f"{v:,.2f}"
        bar = ('<span class="na">not scored</span>' if sc is None else
               f'<div class="bar"><i style="width:{sc:.0f}%;background:{COL[tone(sc)]}"></i></div>')
        out += f'<div class="sr"><span>{esc(k)}</span><span class="mono">{vtxt}</span>{bar}<span class="mono" style="color:{COL[tone(sc)]}">{"–" if sc is None else f"{sc:.0f}"}</span></div>'
    return out


def build(d, peers, peer_src, R, mk, report_date):
    hist = mk.get("hist")
    q, qh = d["q"], d["q_heads"]
    sales_k = "Sales" if "Sales" in q else "Revenue"
    op_k = "Operating Profit" if "Operating Profit" in q else "Financing Profit"
    ticker = d["nse"] or d["slug"]
    sc, lab = R["score"], R["label"]
    t_de = tone(R["fh_items"][R["de_label"]][1])

    # ---------- stock bar / KPIs ----------
    basis_badge = ('<span class="badge ok">CONSOLIDATED</span>' if d["basis"] == "Consolidated"
                   else '<span class="badge bad">STANDALONE ONLY — not primary basis; treat with caution</span>')
    ret = R["ret_1y"]
    bar = (f'<div class="stockbar"><div><div class="tk mono">NSE: {esc(ticker)}</div><div class="nm">{esc(d["name"])}</div>{basis_badge}</div>'
           f'<div class="sb"><label>CMP</label><b class="mono">{f(d["cmp"],2,"₹")}</b></div>'
           f'<div class="sb"><label>1Y return (adj.)</label><b class="mono">{signed(ret)}</b></div>'
           f'<div class="sb"><label>Market cap</label><b class="mono">{cr(d["mcap"])}</b></div>'
           f'<div class="sb"><label>Sector</label><b>{esc(d["sector"] or "N/A")}<small>{esc(d["industry"])}</small></b></div>'
           f'<div class="sb"><label>Report date</label><b class="mono">{report_date}</b></div></div>')

    rng = f'{f(d["lo"],0,"₹")} – {f(d["hi"],0,"₹")}'
    kpis = [("P/E", f(d["pe"], 1, "", "x"), None), ("P/B", f(d["pb"], 2, "", "x"), None), ("52W range", rng, None),
            (R["de_label"].split(" (")[0], f(R["de_used"], 2, "", "x"), t_de),
            ("Revenue (TTM)", cr(R["rev_ttm"]), None), ("PAT (TTM, reported)", cr(R["pat_ttm"]), None),
            ("EBITDA margin", f(R["ebitda_m"], 1, "", "%") if not R["fin"] else "n/m (financial)", None)]
    kpi_html = "".join(f'<div class="kpi"><label>{a}</label><b class="mono" style="color:{COL[t] if t else "inherit"}">{b}</b></div>' for a, b, t in kpis)

    # ---------- cards ----------
    vi, fi = R["val_items"], R["fh_items"]
    vt = lambda k: tone(vi[k][1])
    ft = lambda k: tone(fi[k][1])
    pe_sub = (f'Peer median {R["peer_pe_med"]:.1f}x · {R["pe_rel"]:.2f}× peers' if R["pe_rel"] else "Peer median unavailable")
    pos = R["range_pos"]
    vcards = "".join([
        card("P/E (consolidated)", f(d["pe"], 1, "", "x"), pe_sub, vt("P/E")),
        card("P/B", f(d["pb"], 2, "", "x"), f'Book value {f(d["bv"],0,"₹")}', vt("P/B")),
        card("EV/EBITDA (TTM)", f(R["ev_ebitda"], 1, "", "x"), "n/m for financials" if R["fin"] else "Debt − cash per latest annual BS", vt("EV/EBITDA")),
        card("Price / Sales (TTM)", f(R["ps"], 2, "", "x"), "Market cap ÷ TTM revenue", None),
        card("Dividend yield", f(d["dy"], 2, "", "%"), "Per Screener.in", None),
        card("Position in 52W range", f(pos, 0, "", "%"), f'{signed(R["from_high"])} vs 52W high', vt("Price vs 52W high")),
    ])
    de_sub = (f'Borrowings {cr(R["de_hist"][-1]["borrow"])} · cash {cr(R["cash"])}' if R["de_hist"] and R["cash"] is not None
              else "Cash not fetched; gross debt ÷ equity shown" if R["de_hist"] else "")
    fcards = "".join([
        card(R["de_label"], f(R["de_used"], 2, "", "x"), de_sub if not R["fin"] else "n/m for financial company", ft(R["de_label"])),
        card("Interest coverage", f(R["int_cov"], 1, "", "x"), "TTM operating profit ÷ interest", ft("Interest coverage")),
        card("ROE", f(d["roe"], 1, "", "%"), "Screener.in, consolidated", ft("ROE")),
        card("ROCE", f(d["roce"], 1, "", "%"), "Screener.in, consolidated", ft("ROCE")),
        card("Revenue growth (TTM)", signed(R["rev_g"]), f'Latest qtr YoY {signed(R["q_rev_yoy"])}', ft("Revenue growth (TTM)")),
        card("PAT growth (TTM, reported)", signed(R["pat_g"]), f'Latest qtr YoY {signed(R["q_pat_yoy"])}', ft("PAT growth (TTM)")),
    ])

    breakdown = (f'<div class="two"><div><h4>Financial Health <span class="w">50% · score {f(R["fh_score"],0)}</span></h4>{score_rows(fi)}</div>'
                 f'<div><h4>Valuation <span class="w">50% · score {f(R["val_score"],0)}</span></h4>{score_rows(vi)}</div></div>'
                 f'<div class="formula mono">Risk score = 0.5 × {f(R["fh_score"],1)} + 0.5 × {f(R["val_score"],1)} = <b style="color:{COL[tone(sc)]}">{f(sc,1)}</b> '
                 f'→ {lab} &nbsp;|&nbsp; 0 = lowest risk, 100 = highest. Each metric is banded by fixed thresholds (see Method note); unavailable metrics are skipped, not guessed.</div>')

    # ---------- peers ----------
    def prow(c, me=False):
        rq = c["q"]
        sk = "Sales" if "Sales" in rq else "Revenue"
        ok = "Operating Profit" if "Operating Profit" in rq else "Financing Profit"
        from analysis import _sum_last, _growth
        rev, op = _sum_last(rq.get(sk), 4), _sum_last(rq.get(ok), 4)
        pb = c["bs"]
        eq = ((pb.get("Equity Capital") or [0])[-1] or 0) + ((pb.get("Reserves") or [0])[-1] or 0)
        bo = (pb.get("Borrowings") or [None])[-1]
        fin = ok == "Financing Profit"
        de = bo / eq if bo is not None and eq > 0 and not fin else None
        om = op / rev * 100 if op is not None and rev and not fin else None
        g = _growth(rev, _sum_last(rq.get(sk), 4, 4))
        warn = "" if c["basis"] == "Consolidated" else ' <span class="badge bad">standalone</span>'
        return (f'<tr class="{"me" if me else ""}"><td>{esc(c["name"])}{warn}</td><td class="mono">{f(c["cmp"],1)}</td><td class="mono">{f(c["pe"],1)}</td>'
                f'<td class="mono">{f(c["pb"],2)}</td><td class="mono">{f(c["mcap"],0) if c["mcap"] is None else indian(c["mcap"])}</td>'
                f'<td class="mono">{f(c["roe"],1)}</td><td class="mono">{f(c["roce"],1)}</td><td class="mono">{f(om,1)}</td>'
                f'<td class="mono">{f(de,2)}</td><td class="mono">{signed(g)}</td></tr>')
    peer_html = ("".join(prow(c, False) for c in [d] ).replace('class=""', 'class="me"') + "".join(prow(c) for c in peers)) if peers else ""
    peer_tbl = (f'<table class="t"><thead><tr><th>Company</th><th>CMP ₹</th><th>P/E</th><th>P/B</th><th>Mkt cap ₹Cr</th><th>ROE %</th><th>ROCE %</th><th>OPM TTM %</th><th>D/E (gross)</th><th>Rev gr. TTM</th></tr></thead><tbody>{peer_html}</tbody></table>'
                if peers else '<div class="na box">No peers could be fetched.</div>')

    # ---------- D/E history ----------
    rows = ""
    hist_de = R["de_hist"]
    for i, r_ in enumerate(hist_de):
        prev = hist_de[i - 1]["de"] if i else None
        ch = None if prev is None else r_["de"] - prev
        chs = NA if ch is None else f'<span class="{"pos" if ch <= 0 else "neg"}">{ch:+.2f}</span>'
        rows += (f'<tr><td class="mono">{r_["year"]}</td><td class="mono">{indian(r_["borrow"])}</td><td class="mono">{indian(r_["equity"])}</td>'
                 f'<td class="mono" style="color:{COL[tone(0 if r_["de"]<0.3 else 40 if r_["de"]<1.2 else 80)]}">{r_["de"]:.2f}x</td><td class="mono">{chs}</td></tr>')
    de_tbl = (f'<table class="t"><thead><tr><th>FY</th><th>Borrowings ₹Cr</th><th>Equity + reserves ₹Cr</th><th>Gross D/E</th><th>YoY Δ</th></tr></thead><tbody>{rows}</tbody></table>'
              if rows and not R["fin"] else '<div class="na box">D/E history not meaningful / unavailable (financial company or missing balance-sheet data).</div>')
    de_note = (f'Latest net D/E: <b class="mono">{f(R["net_de"],2,"","x")}</b> (borrowings from Screener.in less cash &amp; ST investments {cr(R["cash"])} from Yahoo Finance fallback; mixed-source, unverified against filings).'
               if R["net_de"] is not None else "Net D/E could not be computed (cash balance unavailable); gross D/E shown.")

    # ---------- quarterly table ----------
    qi = list(range(max(0, len(qh) - 8), len(qh)))
    def qrow(label, key, kind="n", derive=None):
        cells = ""
        for i in qi:
            v = (q.get(key) or [None] * len(qh))[i] if key else derive(i)
            if v is None:
                cells += f"<td>{NA}</td>"
            elif kind == "g":
                cells += f'<td class="mono">{signed(v)}</td>'
            elif kind == "p":
                cells += f'<td class="mono">{v:.1f}%</td>'
            else:
                cells += f'<td class="mono">{indian(v) if abs(v) >= 1000 else f"{v:,.2f}" if kind=="e" else indian(v)}</td>'
        return f"<tr><td>{label}</td>{cells}</tr>"
    def yoy(key):
        def fn(i):
            row = q.get(key) or []
            return ((row[i] / row[i - 4] - 1) * 100 if i >= 4 and row[i] is not None and row[i - 4] and row[i - 4] > 0 else None)
        return fn
    qt = (f'<table class="t"><thead><tr><th>₹ Cr (consolidated)</th>{"".join(f"<th>{qh[i]}</th>" for i in qi)}</tr></thead><tbody>'
          + qrow("Revenue", sales_k) + qrow("Revenue YoY", None, "g", yoy(sales_k))
          + qrow("EBITDA (op. profit)" if op_k == "Operating Profit" else "Financing profit", op_k)
          + ("" if R["fin"] else qrow("EBITDA margin", "OPM %", "p"))
          + qrow("Other income", "Other Income") + qrow("Net profit (reported)", "Net Profit") + qrow("PAT YoY", None, "g", yoy("Net Profit"))
          + qrow("EPS ₹", "EPS in Rs", "e") + "</tbody></table>")

    # ---------- latest update ----------
    lq = qh[-1] if qh else "N/A"
    def qoq(key):
        r_ = q.get(key) or []
        return (r_[-1] / r_[-2] - 1) * 100 if len(r_) > 1 and r_[-1] is not None and r_[-2] and r_[-2] > 0 else None
    ex = R["exceptional"]
    ex_html = ("".join(f"<li><b>{k}</b>: {'+' if v>=0 else ''}{indian(v)} Cr (pre-tax unusual items, Yahoo Finance)</li>" for k, v in ex.items())
               if ex else "<li>No exceptional / unusual items identified in the fetched data for the last 4 quarters. <i>Unconfirmed against the company's results filing — check the BSE results PDF.</i></li>")
    ann = "".join(f'<li><a href="{esc(a["url"])}" target="_blank" rel="noopener">{esc(a["text"])}</a></li>' for a in d["announcements"]) or "<li>No recent BSE announcements fetched.</li>"
    latest = (f'<div class="two"><div><h4>Latest reported quarter: {lq}</h4><table class="t small"><tbody>'
              f'<tr><td>Revenue</td><td class="mono">{cr((q.get(sales_k) or [None])[-1])}</td><td class="mono">YoY {signed(R["q_rev_yoy"])}</td><td class="mono">QoQ {signed(qoq(sales_k))}</td></tr>'
              f'<tr><td>EBITDA</td><td class="mono">{cr((q.get(op_k) or [None])[-1])}</td><td class="mono">OPM {f((q.get("OPM %") or [None])[-1],0,"","%") if not R["fin"] else "n/m"}</td><td></td></tr>'
              f'<tr><td>PAT (reported)</td><td class="mono">{cr((q.get("Net Profit") or [None])[-1])}</td><td class="mono">YoY {signed(R["q_pat_yoy"])}</td><td class="mono">QoQ {signed(qoq("Net Profit"))}</td></tr>'
              f'</tbody></table><h4 style="margin-top:14px">PAT basis: {esc(R["pat_basis"])}</h4><ul class="pl">{ex_html}</ul></div>'
              f'<div><h4>Recent BSE announcements (via Screener.in)</h4><ul class="pl">{ann}</ul></div></div>')

    # ---------- catalysts vs risks ----------
    cons = mk.get("cons")
    cat, risk = [], []
    if R["rev_g"] is not None and R["rev_g"] > 10: cat.append(f"Revenue growing {R['rev_g']:.1f}% (TTM vs prior TTM)")
    if R["pat_g"] is not None and R["pat_g"] > 10: cat.append(f"Reported PAT up {R['pat_g']:.1f}% (TTM vs prior TTM)")
    if R["de_used"] is not None and R["de_used"] < 0.5: cat.append(f"Conservative leverage: {R['de_label'].split(' (')[0]} {R['de_used']:.2f}x")
    if d["roce"] and d["roce"] > 15: cat.append(f"ROCE {d['roce']:.1f}% indicates efficient capital use")
    if R["pe_rel"] and R["pe_rel"] < 0.9: cat.append(f"P/E at {R['pe_rel']:.2f}× peer median")
    if R["from_high"] is not None and R["from_high"] < -25: cat.append(f"Trading {abs(R['from_high']):.0f}% below 52W high — re-rating potential if fundamentals hold")
    if cons and cons.get("target") and d["cmp"] and cons["target"] / d["cmp"] > 1.1: cat.append(f"Mean analyst target ₹{cons['target']:,.0f} ({(cons['target']/d['cmp']-1)*100:+.0f}% vs CMP; {cons['n']} analysts, Yahoo fallback)")
    if R["rev_g"] is not None and R["rev_g"] < 0: risk.append(f"Revenue contracting {R['rev_g']:.1f}% (TTM)")
    if R["pat_g"] is not None and R["pat_g"] < 0: risk.append(f"Reported PAT down {abs(R['pat_g']):.1f}% (TTM)")
    if R["de_used"] is not None and R["de_used"] > 1: risk.append(f"Elevated leverage: {R['de_label'].split(' (')[0]} {R['de_used']:.2f}x")
    if R["int_cov"] is not None and R["int_cov"] < 3: risk.append(f"Thin interest coverage {R['int_cov']:.1f}x")
    if d["pe"] and d["pe"] > 40: risk.append(f"Rich P/E {d['pe']:.1f}x")
    if R["pe_rel"] and R["pe_rel"] > 1.3: risk.append(f"P/E {R['pe_rel']:.2f}× peer median")
    if d["roe"] is not None and d["roe"] < 8: risk.append(f"Low ROE {d['roe']:.1f}%")
    if ex: risk.append("Reported PAT includes exceptional items — underlying earnings may differ")
    if ret is not None and ret < -15: risk.append(f"Weak price momentum: {ret:.1f}% over 1Y")
    cat += [f"{t} <em>(Screener.in)</em>" for t in d["pros"][:3]]
    risk += [f"{t} <em>(Screener.in)</em>" for t in d["cons"][:3]]
    li = lambda xs, e: "".join(f"<li>{x if '<em>' in x else esc(x)}</li>" for x in xs) or f"<li>{e}</li>"
    cr_html = (f'<div class="two"><div class="cr good"><h4>▲ Catalysts</h4><ul class="pl">{li(cat,"None flagged by the fetched data")}</ul></div>'
               f'<div class="cr badc"><h4>▼ Risks</h4><ul class="pl">{li(risk,"None flagged by the fetched data")}</ul></div></div>'
               '<p class="mut">Mechanically derived from fetched numbers and Screener.in pros/cons; not a forward-looking view.</p>')

    # ---------- bottom line ----------
    segs = [("Low", 0, 25), ("Moderate", 25, 45), ("Elevated", 45, 62), ("High", 62, 80), ("Very high", 80, 100)]
    ratingbar = '<div class="rbar">' + "".join(
        f'<div class="seg{" on" if sc is not None and a <= sc < b or (sc == 100 and b == 100) else ""}" style="flex:{b-a}"><span>{n}</span></div>' for n, a, b in segs) + (
        f'<div class="pin" style="left:{min(max(sc,0),100):.1f}%"></div>' if sc is not None else "") + "</div>"
    weak = max(((k, s_) for k, (_, s_) in {**fi, **vi}.items() if s_ is not None), key=lambda x: x[1], default=None)
    strong = min(((k, s_) for k, (_, s_) in {**fi, **vi}.items() if s_ is not None), key=lambda x: x[1], default=None)
    verdict = (f"{esc(d['name'])} scores <b class='mono' style='color:{COL[tone(sc)]}'>{sc:.0f}/100 ({lab})</b> on this educational framework: "
               f"Financial Health {f(R['fh_score'],0)} and Valuation {f(R['val_score'],0)} (lower = safer). "
               + (f"Largest risk contributor: <b>{esc(weak[0])}</b> ({weak[1]:.0f}); strongest metric: <b>{esc(strong[0])}</b> ({strong[1]:.0f}). " if weak else "")
               + "This is a snapshot from automatically fetched data; it does not model the business, management quality, or macro factors.") if sc is not None else "Insufficient data to score."
    cons_html = (f'<div class="box"><b>Analyst consensus</b> <span class="badge warn">Yahoo Finance fallback — Trendlyne not fetched</span><br>'
                 f'<span class="mono">{esc(str(cons["key"]).replace("_"," ").upper())} · mean rating {cons["mean"]} (1=strong buy, 5=sell) · mean target ₹{cons["target"]:,.0f} · {cons["n"]} analysts</span></div>'
                 if cons and cons.get("target") else '<div class="box na">Analyst consensus unavailable (Trendlyne not fetched; Yahoo returned no data).</div>')

    srcs = [
        ("Price, market cap, P/E, ROE, ROCE, statements, peers, D/E", f'Screener.in — {d["basis"]} view', "ok" if d["basis"] == "Consolidated" else "bad"),
        ("12M price series, 1Y return (adjusted close)", "Yahoo Finance (fallback; Tickertape adjusted return not fetched)" if hist is not None else "UNAVAILABLE", "warn" if hist is not None else "bad"),
        ("Cash balance for Net D/E; exceptional items", "Yahoo Finance (fallback; unverified vs filings)" if mk.get("cash") is not None else "UNAVAILABLE", "warn" if mk.get("cash") is not None else "bad"),
        ("Analyst consensus", "Yahoo Finance (fallback; Trendlyne not fetched)" if cons else "UNAVAILABLE", "warn" if cons else "bad"),
        ("BSE filings / NSE data / company IR", "Only BSE announcement links surfaced via Screener.in; filings were not parsed directly", "warn"),
        ("Peer list", peer_src, "ok"),
    ]
    src_html = "".join(f'<tr><td>{a}</td><td><span class="badge {c}">{esc(b)}</span></td></tr>' for a, b, c in srcs)
    method = ("Method: each metric maps to a 0–100 risk score via fixed bands (e.g. P/E &lt;15→15, &lt;25→35, &lt;40→60, &lt;60→80, else 95; ROE ≥18%→15 … &lt;4%→90; D/E &lt;0.3→15 … ≥2→92). "
              "Pillar score = mean of available metrics; total = 50% Financial Health + 50% Valuation. Bands are generic across sectors — they will over/under-penalise capital-intensive or financial businesses.")

    disclaimer = ("<b>Educational reference only.</b> Not investment advice and not a SEBI-registered research analyst recommendation. "
                  "Figures are scraped at report time from third-party sites and may be delayed, wrong or mis-parsed; verify against BSE/NSE filings before relying on them.")

    standalone_warn = ('<div class="alert">⚠ Consolidated statements were not available — all figures below are STANDALONE and are not a reliable basis for analysis.</div>'
                       if d["basis"] != "Consolidated" else "")
    notes = "".join(f'<div class="alert info">{esc(n)}</div>' for n in R["notes"])

    page1 = f"""
{standalone_warn}{notes}{bar}
<div class="row g"><div class="panel gp"><div class="pt">Risk gauge</div>{gauge(sc, lab)}<div class="mut c">Educational score · 0 = low risk · 100 = high risk</div></div>
<div class="panel" style="flex:1"><div class="pt">Key metrics</div><div class="kpis">{kpi_html}</div>
<div class="mut" style="margin-top:10px">PAT basis: {esc(R["pat_basis"])}. Revenue, PAT, EBITDA = sum of last 4 reported quarters (consolidated).</div></div></div>
<div class="panel"><div class="pt">12-month price · NSE: {esc(ticker)} (unadjusted closes; KPI 52W range uses intraday high/low)</div>{price_chart(hist)}</div>
<div class="panel"><div class="pt">Valuation</div><div class="grid">{vcards}</div></div>
<div class="panel"><div class="pt">Financial health &amp; growth</div><div class="grid">{fcards}</div></div>
<div class="panel"><div class="pt">Risk score breakdown</div>{breakdown}</div>
<div class="panel"><div class="pt">Peer comparison <span class="mut">· {esc(peer_src)} · Screener.in</span></div><div class="scroll">{peer_tbl}</div></div>
<div class="panel"><div class="pt">Debt-to-equity · 5 years (consolidated, March year-end)</div><div class="scroll">{de_tbl}</div><div class="mut" style="margin-top:8px">{de_note}</div></div>
"""
    page2 = f"""
<div class="panel"><div class="pt">Quarterly trend (last 8 quarters)</div><div class="scroll">{qt}</div></div>
<div class="panel"><div class="pt">Latest earnings / delivery update</div>{latest}</div>
<div class="panel"><div class="pt">Catalysts vs risks</div>{cr_html}</div>
<div class="panel"><div class="pt">Bottom line</div>{ratingbar}<p class="verdict">{verdict}</p>{cons_html}</div>
<div class="panel"><div class="pt">Sources &amp; data quality</div><table class="t small"><tbody>{src_html}</tbody></table><p class="mut">{method}</p></div>
"""
    text = export_text(d, ticker, R, report_date, peers)
    return TEMPLATE.replace("%%TITLE%%", esc(f"{d['name']} — Risk Report")).replace("%%DATE%%", report_date) \
        .replace("%%DISCLAIMER%%", disclaimer).replace("%%PAGE1%%", page1).replace("%%PAGE2%%", page2) \
        .replace("%%TEXT%%", json.dumps(text).replace("</", "<\\/"))


def export_text(d, ticker, R, date, peers):
    p = lambda v, dec=1, s="": "N/A" if v is None else f"{v:,.{dec}f}{s}"
    L = [f"EQUITY RISK ANALYSIS — {d['name']} (NSE: {ticker}) as of {date}", f"Basis: {d['basis']} (Screener.in). Educational only; not investment advice.", "",
         f"CMP ₹{p(d['cmp'],2)} | Mkt cap ₹{p(d['mcap'],0)} Cr | 1Y return {p(R['ret_1y'],1,'%')} | Sector {d['sector']}",
         f"RISK SCORE {p(R['score'],0)}/100 — {R['label']} (Financial Health {p(R['fh_score'],0)} @50% + Valuation {p(R['val_score'],0)} @50%)", "",
         f"P/E {p(d['pe'],1,'x')} | P/B {p(d['pb'],2,'x')} | 52W {p(d['lo'],0)}–{p(d['hi'],0)} | {R['de_label']} {p(R['de_used'],2,'x')}",
         f"Revenue TTM ₹{p(R['rev_ttm'],0)} Cr | PAT TTM (reported) ₹{p(R['pat_ttm'],0)} Cr | EBITDA margin {p(R['ebitda_m'],1,'%')}", ""]
    if R["exceptional"]:
        L.append("Exceptional items: " + "; ".join(f"{k}: {v:+,.0f} Cr" for k, v in R["exceptional"].items()))
    L.append("Peers: " + ", ".join(f"{c['name']} (P/E {p(c['pe'],1)})" for c in peers))
    L.append("D/E history: " + ", ".join(f"{r['year']} {r['de']:.2f}x" for r in R["de_hist"]))
    L.append("")
    L.append("Score detail:")
    for k, (v, s) in {**R["fh_items"], **R["val_items"]}.items():
        L.append(f"  {k}: {p(v,2)} → risk {p(s,0)}")
    return "\n".join(L)


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%%TITLE%%</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#08090d;--panel:#10121a;--line:#1c1f2b;--txt:#e5e7eb;--mut:#8b90a0;--acc:#10b981;--pos:#10b981;--neg:#ef4444;--warn:#f59e0b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:14px/1.5 'DM Sans',system-ui,sans-serif}
.mono,.tk{font-family:'JetBrains Mono',ui-monospace,monospace}.wrap{max-width:1100px;margin:0 auto;padding:16px}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}
.top h1{font-size:16px;margin:0;color:var(--acc);letter-spacing:.04em}
.tabs button,.btn{background:var(--panel);color:var(--txt);border:1px solid var(--line);padding:8px 14px;border-radius:8px;cursor:pointer;font:inherit}
.tabs button.on,.btn:hover{border-color:var(--acc);color:var(--acc)}.btn.p{background:var(--acc);color:#04130d;border-color:var(--acc);font-weight:700}
.disc{border:1px solid #3b2f0a;background:#1a1507;color:#e8c872;padding:8px 12px;border-radius:8px;font-size:12px;margin-bottom:12px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:14px}
.pt{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--acc);margin-bottom:12px;font-weight:700}
.stockbar{display:flex;gap:22px;flex-wrap:wrap;align-items:center;background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:12px;padding:14px 16px;margin-bottom:14px}
.tk{color:var(--acc);font-weight:700;font-size:13px}.nm{font-size:20px;font-weight:700}
.sb label,.kpi label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--mut)}.sb b{font-size:16px}.sb small{display:block;font-size:11px;color:var(--mut);font-weight:400}
.row{display:flex;gap:14px;flex-wrap:wrap}.gp{width:340px;text-align:center}.gauge{width:100%;max-width:320px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:#0b0d13;border:1px solid var(--line);border-radius:8px;padding:10px}.kpi b{font-size:15px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.card{background:#0b0d13;border:1px solid var(--line);border-top:2px solid var(--c);border-radius:10px;padding:12px}
.ct{font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em}.cv{font-size:24px;font-weight:700;margin:4px 0;color:var(--c)}.cs{font-size:12px;color:var(--mut)}
.chart{width:100%;height:auto}.pos{color:var(--pos)}.neg{color:var(--neg)}.warn{color:var(--warn)}.na{color:var(--mut);font-style:italic;font-size:.9em}.mut{color:var(--mut);font-size:12px}.c{text-align:center}
.box{background:#0b0d13;border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin-top:10px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}h4{margin:0 0 10px;font-size:14px}.w{color:var(--mut);font-weight:400;font-size:12px;font-family:'JetBrains Mono',monospace}
.sr{display:grid;grid-template-columns:1.4fr .7fr 1.2fr 30px;gap:8px;align-items:center;padding:5px 0;border-bottom:1px solid var(--line);font-size:12px}
.bar{height:6px;background:#1c1f2b;border-radius:3px;overflow:hidden}.bar i{display:block;height:100%}
.formula{margin-top:14px;padding:10px;background:#0b0d13;border-radius:8px;font-size:12px;color:var(--mut)}
.scroll{overflow-x:auto}.t{width:100%;border-collapse:collapse;font-size:12.5px}.t th{text-align:right;color:var(--mut);font-weight:500;padding:8px;border-bottom:1px solid var(--line);white-space:nowrap}
.t td{padding:8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}.t th:first-child,.t td:first-child{text-align:left}.t tr.me td{background:#0d1f19}.t.small td{text-align:left}
.badge{display:inline-block;font-size:10px;padding:2px 8px;border-radius:99px;border:1px solid;margin-top:4px;font-family:'JetBrains Mono',monospace;white-space:normal}
.badge.ok{color:var(--pos);border-color:var(--pos)}.badge.bad{color:var(--neg);border-color:var(--neg)}.badge.warn{color:var(--warn);border-color:var(--warn)}
.alert{border:1px solid var(--neg);background:#1f0b0b;color:#fca5a5;padding:10px 12px;border-radius:8px;margin-bottom:12px}.alert.info{border-color:var(--warn);background:#1a1507;color:#fcd34d}
.pl{margin:0;padding-left:18px}.pl li{margin-bottom:6px}.pl a{color:var(--acc)}.pl em{color:var(--mut);font-size:11px}
.cr{padding:12px;border-radius:10px;border:1px solid var(--line)}.cr.good{border-top:2px solid var(--pos)}.cr.good h4{color:var(--pos)}.cr.badc{border-top:2px solid var(--neg)}.cr.badc h4{color:var(--neg)}
.rbar{position:relative;display:flex;gap:3px;margin:8px 0 22px}.seg{background:#1c1f2b;padding:8px 4px;text-align:center;font-size:11px;color:var(--mut);border-radius:4px}
.seg.on{background:#10b98122;color:var(--acc);outline:1px solid var(--acc);font-weight:700}.pin{position:absolute;top:-6px;bottom:-10px;width:3px;background:#fff;border-radius:2px;transform:translateX(-1px)}
.verdict{font-size:15px}.page{display:none}.page.on{display:block}
@media print{.page{display:block!important}.tabs,.btn{display:none}}@media(max-width:640px){.gp{width:100%}}
</style></head><body><div class="wrap">
<div class="top"><h1>▲ EQUITY RISK REPORT · %%DATE%%</h1>
<div class="tabs"><button class="on" data-p="1">Page 1 · Risk &amp; valuation</button> <button data-p="2">Page 2 · Trends &amp; verdict</button> <button class="btn p" id="cp">Copy report</button></div></div>
<div class="disc">%%DISCLAIMER%%</div>
<div class="page on" id="p1">%%PAGE1%%</div><div class="page" id="p2">%%PAGE2%%</div>
<div class="mut c" style="margin:14px 0">Generated %%DATE%% from live web data. Not investment advice.</div></div>
<script>
const TXT=%%TEXT%%;
document.querySelectorAll('.tabs button[data-p]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.page').forEach(p=>p.classList.remove('on'));
 document.querySelectorAll('.tabs button[data-p]').forEach(x=>x.classList.remove('on'));document.getElementById('p'+b.dataset.p).classList.add('on');b.classList.add('on');window.scrollTo(0,0)});
function legacy(t){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();let ok=false;try{ok=document.execCommand('copy')}catch(e){}a.remove();return ok}
document.getElementById('cp').onclick=async function(){let ok=false;
 try{await navigator.clipboard.writeText(TXT);ok=true}catch(e){ok=legacy(TXT)}
 this.textContent=ok?'Copied ✓':'Copy failed';setTimeout(()=>this.textContent='Copy report',1800)};
</script></body></html>"""
