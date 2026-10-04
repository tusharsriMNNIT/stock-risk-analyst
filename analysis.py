"""Derives metrics and the 0-100 risk score (higher = riskier) from fetched data."""
import statistics


def _vals(row):
    return [v for v in (row or []) if v is not None]


def _sum_last(row, n, offset=0):
    row = row or []
    seg = row[len(row) - n - offset: len(row) - offset] if len(row) >= n + offset else []
    return sum(seg) if len(seg) == n and all(v is not None for v in seg) else None


def _growth(cur, prev):
    if cur is None or prev is None or prev <= 0:
        return None
    return (cur / prev - 1) * 100


def band(v, cuts, scores):
    """Risk score for v: first cut it is below -> matching score; else the last score."""
    if v is None:
        return None
    for c, s in zip(cuts, scores):
        if v < c:
            return s
    return scores[-1]


def label_for(score):
    for cut, name in ((25, "LOW"), (45, "MODERATE"), (62, "ELEVATED"), (80, "HIGH")):
        if score < cut:
            return name
    return "VERY HIGH"


def tone(score):
    return None if score is None else "pos" if score < 35 else "warn" if score < 62 else "neg"


def compute(d, peers, mk):
    q = d["q"]
    sales_k = "Sales" if "Sales" in q else "Revenue" if "Revenue" in q else None
    op_k = "Operating Profit" if "Operating Profit" in q else "Financing Profit" if "Financing Profit" in q else None
    fin = op_k == "Financing Profit"
    R = {"fin": fin, "notes": []}
    sales, op, npf = q.get(sales_k), q.get(op_k), q.get("Net Profit")
    R["rev_ttm"], R["pat_ttm"], R["op_ttm"] = _sum_last(sales, 4), _sum_last(npf, 4), _sum_last(op, 4)
    R["rev_g"] = _growth(R["rev_ttm"], _sum_last(sales, 4, 4))
    R["pat_g"] = _growth(R["pat_ttm"], _sum_last(npf, 4, 4))
    R["q_rev_yoy"] = _growth(sales[-1], sales[-5]) if sales and len(sales) >= 5 else None
    R["q_pat_yoy"] = _growth(npf[-1], npf[-5]) if npf and len(npf) >= 5 else None
    R["ebitda_m"] = R["op_ttm"] / R["rev_ttm"] * 100 if R["op_ttm"] is not None and R["rev_ttm"] and not fin else None
    if fin:
        R["notes"].append("Financial company: EBITDA margin, D/E, interest coverage and EV/EBITDA are not meaningful and are excluded from the score.")
    interest = _sum_last(q.get("Interest"), 4)
    R["int_cov"] = R["op_ttm"] / interest if interest and R["op_ttm"] and not fin else None

    # Exceptional items (Yahoo) falling in the last four reported quarters
    ex = {}
    if mk.get("unusual"):
        recent = {h for h in d["q_heads"][-4:]}
        for dt, v in mk["unusual"].items():
            y, m, _ = dt.split("-")
            lab = f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(m)-1]} {y}"
            if lab in recent:
                ex[lab] = v
    R["exceptional"] = ex
    R["pat_basis"] = "Reported (consolidated, attributable to owners)" if not ex else "Reported; exceptional items named separately"

    # Debt / equity history (annual, consolidated)
    bs, bh = d["bs"], d["bs_heads"]
    eq = [(a or 0) + (b or 0) for a, b in zip(bs.get("Equity Capital", []), bs.get("Reserves", []))]
    bor = bs.get("Borrowings", [])
    de = []
    for i in range(max(0, len(bh) - 5), len(bh)):
        if i < len(eq) and i < len(bor) and bor[i] is not None and eq[i] > 0:
            de.append({"year": bh[i], "borrow": bor[i], "equity": eq[i], "de": bor[i] / eq[i]})
    R["de_hist"] = de
    R["gross_de"] = de[-1]["de"] if de and not fin else None
    cash = mk.get("cash")
    R["cash"] = cash
    R["net_de"] = (de[-1]["borrow"] - cash) / de[-1]["equity"] if de and cash is not None and not fin else None
    R["de_used"] = R["net_de"] if R["net_de"] is not None else R["gross_de"]
    R["de_label"] = "Net D/E" if R["net_de"] is not None else "Gross D/E (net unavailable)"
    R["ev_ebitda"] = ((d["mcap"] + de[-1]["borrow"] - (cash or 0)) / R["op_ttm"]
                      if de and R["op_ttm"] and R["op_ttm"] > 0 and d["mcap"] and not fin else None)
    R["ps"] = d["mcap"] / R["rev_ttm"] if d["mcap"] and R["rev_ttm"] else None

    # Price history stats
    h = mk.get("hist")
    R["ret_1y"] = None
    if h is not None:
        adj = h["Adj Close"] if "Adj Close" in h else h["Close"]
        R["ret_1y"] = (adj.iloc[-1] / adj.iloc[0] - 1) * 100
    lo, hi, cmp_ = d["lo"], d["hi"], d["cmp"]
    R["range_pos"] = (cmp_ - lo) / (hi - lo) * 100 if lo is not None and hi and hi > lo and cmp_ else None
    R["from_high"] = (cmp_ / hi - 1) * 100 if hi and cmp_ else None

    # Peer medians
    pe_p = [p["pe"] for p in peers if p.get("pe") and p["pe"] > 0]
    R["peer_pe_med"] = statistics.median(pe_p) if pe_p else None
    R["pe_rel"] = d["pe"] / R["peer_pe_med"] if d["pe"] and R["peer_pe_med"] else None

    # ---- Scores (risk, 0 = safest) ----
    pe = d["pe"]
    val = {
        "P/E": (pe, band(pe, [15, 25, 40, 60], [15, 35, 60, 80, 95]) if pe and pe > 0 else (90 if pe is not None else None)),
        "P/E vs peer median": (R["pe_rel"], band(R["pe_rel"], [0.8, 1.2, 1.6], [20, 40, 65, 85])),
        "P/B": (d["pb"], band(d["pb"], [1.5, 3, 6, 10], [20, 40, 65, 80, 92])),
        "EV/EBITDA": (R["ev_ebitda"], band(R["ev_ebitda"], [8, 14, 22], [20, 40, 65, 85])),
        "Price vs 52W high": (R["from_high"], band(-R["from_high"] if R["from_high"] is not None else None, [10, 25, 40], [55, 35, 45, 65])),
    }
    fh = {
        R["de_label"]: (R["de_used"], band(R["de_used"], [0.3, 0.7, 1.2, 2], [15, 30, 50, 75, 92])),
        "Interest coverage": (R["int_cov"], band(-R["int_cov"] if R["int_cov"] is not None else None, [-8, -4, -2, -1], [15, 35, 60, 80, 95])),
        "ROE": (d["roe"], band(-d["roe"] if d["roe"] is not None else None, [-18, -12, -8, -4], [15, 30, 50, 70, 90])),
        "ROCE": (d["roce"], band(-d["roce"] if d["roce"] is not None else None, [-18, -12, -8, -4], [15, 30, 50, 70, 90])),
        "Revenue growth (TTM)": (R["rev_g"], band(-R["rev_g"] if R["rev_g"] is not None else None, [-15, -8, 0, 10], [15, 30, 50, 75, 90])),
        "PAT growth (TTM)": (R["pat_g"], band(-R["pat_g"] if R["pat_g"] is not None else None, [-20, -5, 0, 15], [15, 30, 50, 75, 90])),
    }
    R["val_items"], R["fh_items"] = val, fh
    avg = lambda items: (sum(s for _, s in items.values() if s is not None) / n) if (n := sum(1 for _, s in items.values() if s is not None)) else None
    R["val_score"], R["fh_score"] = avg(val), avg(fh)
    parts = [(x, w) for x, w in ((R["fh_score"], .5), (R["val_score"], .5)) if x is not None]
    R["score"] = sum(x * w for x, w in parts) / sum(w for _, w in parts) if parts else None
    R["label"] = label_for(R["score"]) if R["score"] is not None else "UNAVAILABLE"
    return R
