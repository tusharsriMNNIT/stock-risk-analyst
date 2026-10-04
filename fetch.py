"""Live data fetching. Nothing is preloaded: every call hits the web at report time."""
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
SCR = "https://www.screener.in"


def num(s):
    """'₹ 1,168' / '21.2 %' / '15,80,194 Cr.' -> float, else None."""
    if s is None:
        return None
    m = re.search(r"-?\d[\d,]*\.?\d*", str(s).replace("−", "-"))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _get(url, **kw):
    r = requests.get(url, headers=UA, timeout=25, **kw)
    r.raise_for_status()
    return r


def search_screener(query):
    """Resolve a company name/ticker to a Screener path like /company/RELIANCE/consolidated/."""
    r = _get(f"{SCR}/api/company/search/", params={"q": query})
    hits = r.json()
    if not hits:
        return None
    q = query.strip().upper()
    for h in hits:  # prefer exact ticker match
        if h["url"].split("/")[2].upper() == q:
            return h
    return hits[0]


def _table(section):
    """Parse a Screener data table -> (headers, {label: [values]})."""
    if section is None:
        return [], {}
    t = section.select_one("table")
    if t is None:
        return [], {}
    heads = [c.get_text(strip=True) for c in t.select("thead th")][1:]
    rows = {}
    for tr in t.select("tbody tr"):
        cells = tr.select("td")
        if not cells:
            continue
        label = re.sub(r"[\s+]+$", "", cells[0].get_text(" ", strip=True))
        rows[label] = [num(c.get_text(strip=True)) for c in cells[1:]]
    return heads, rows


def parse_company(path):
    """Fetch and parse one Screener company page, consolidated view only."""
    path = re.sub(r"/consolidated/?$", "", path.rstrip("/")) + "/consolidated/"
    resp = _get(SCR + path)
    html = resp.text
    s = BeautifulSoup(html, "lxml")
    h1 = s.select_one("h1")
    d = {"path": path, "name": h1.get_text(strip=True) if h1 else path}
    d["slug"] = path.split("/")[2]
    if s.select_one("#top-ratios") is None:
        raise ValueError("Screener page has no ratios block")
    # Screener redirects to the standalone view when no consolidated statements exist.
    d["basis"] = "Consolidated" if "/consolidated" in resp.url else "Standalone"

    ratios = {}
    for li in s.select("#top-ratios li"):
        n = li.select_one(".name")
        if n:
            ratios[n.get_text(strip=True)] = [num(x.get_text()) for x in li.select(".number")]
    g = lambda k, i=0: (ratios.get(k) or [None] * 2)[i] if len(ratios.get(k) or []) > i else None
    d.update(cmp=g("Current Price"), mcap=g("Market Cap"), pe=g("Stock P/E"), bv=g("Book Value"),
             dy=g("Dividend Yield"), roce=g("ROCE"), roe=g("ROE"), hi=g("High / Low", 0), lo=g("High / Low", 1))
    d["pb"] = d["cmp"] / d["bv"] if d["cmp"] and d["bv"] else None

    # sector hierarchy + exchange symbols
    d["sector"] = ""
    d["industry"] = ""
    crumbs = [a.get_text(strip=True) for a in s.select("#peers p a")][:4]
    if len(crumbs) >= 2:
        d["sector"], d["industry"] = crumbs[0], crumbs[-1]
    nse = s.select_one('a[href*="nseindia.com"]')
    m = re.search(r"symbol=([^&]+)", nse["href"]) if nse else None
    d["nse"] = m.group(1) if m else None
    bse = s.select_one('a[href*="bseindia.com"]')
    m = re.search(r"/(\d{6})/?", bse["href"]) if bse else None
    d["bse"] = m.group(1) if m else None

    d["q_heads"], d["q"] = _table(s.select_one("#quarters"))
    d["pl_heads"], d["pl"] = _table(s.select_one("#profit-loss"))
    d["bs_heads"], d["bs"] = _table(s.select_one("#balance-sheet"))
    d["cf_heads"], d["cf"] = _table(s.select_one("#cash-flow"))

    d["pros"] = [li.get_text(" ", strip=True) for li in s.select(".pros li")]
    d["cons"] = [li.get_text(" ", strip=True) for li in s.select(".cons li")]
    d["announcements"] = [
        {"text": a.get_text(" ", strip=True)[:140], "url": a["href"] if a["href"].startswith("http") else SCR + a["href"]}
        for a in (s.select_one("#documents ul.list-links") or s).select("a")[:6]
    ]
    wh = s.select_one("[data-warehouse-id]")
    co = s.select_one("[data-company-id]")
    d["wh_id"] = wh["data-warehouse-id"] if wh else None
    d["co_id"] = co["data-company-id"] if co else None
    return d


def screener_peers(d):
    """Peer table rows from Screener's peer-comparison endpoint."""
    for pid in (d.get("wh_id"), d.get("co_id")):
        if not pid:
            continue
        try:
            s = BeautifulSoup(_get(f"{SCR}/api/company/{pid}/peers/").text, "lxml")
        except requests.RequestException:
            continue
        out = []
        for tr in s.select("table tr"):
            a = tr.select_one("a")
            tds = tr.select("td")
            if a and len(tds) > 5:
                out.append({"name": a.get_text(strip=True), "path": a["href"], "mcap": num(tds[4].get_text())})
        if out:
            return out
    return []


def pick_peers(d, user_peers):
    """User-supplied peers if given, else 4 closest-by-market-cap peers from Screener's list."""
    if user_peers:
        paths = []
        for q in user_peers:
            h = search_screener(q)
            if h:
                paths.append(h["url"])
        return paths[:4], "User-provided"
    cand = [p for p in screener_peers(d) if p["path"].split("/")[2] != d["slug"]]
    cand = [p for p in cand if p["mcap"]]
    cand.sort(key=lambda p: abs((p["mcap"] or 0) - d["mcap"]) if d["mcap"] else 0)
    return [p["path"] for p in cand[:4]], "Auto: Screener.in peer comparison (4 closest by market cap)"


def fetch_peers(paths):
    def one(p):
        try:
            return parse_company(p)
        except Exception:
            return None
    with ThreadPoolExecutor(max_workers=4) as ex:
        return [x for x in ex.map(one, paths) if x]


def fetch_market(symbol):
    """Price history + cash + consensus from Yahoo Finance (fallback source, labelled in report)."""
    import yfinance as yf
    out = {"hist": None, "cash": None, "unusual": None, "cons": None}
    t = yf.Ticker(symbol)
    try:
        h = t.history(period="1y", auto_adjust=False)
        h = h.dropna(subset=["Close"])
        out["hist"] = h if len(h) > 20 else None
    except Exception:
        pass
    try:
        bs = t.balance_sheet
        for k in ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"):
            if k in bs.index and bs.loc[k].dropna().size:
                out["cash"] = float(bs.loc[k].dropna().iloc[0]) / 1e7  # INR -> Cr
                out["cash_label"] = k
                break
    except Exception:
        pass
    try:
        qi = t.quarterly_income_stmt
        for k in ("Total Unusual Items", "Special Income Charges"):
            if k in qi.index:
                ser = qi.loc[k].dropna()
                out["unusual"] = {str(c.date()): float(v) / 1e7 for c, v in ser.items() if abs(v) > 0}
                break
    except Exception:
        pass
    try:
        i = t.info
        if i.get("numberOfAnalystOpinions"):
            out["cons"] = {"mean": i.get("recommendationMean"), "key": i.get("recommendationKey"),
                           "target": i.get("targetMeanPrice"), "n": i.get("numberOfAnalystOpinions")}
    except Exception:
        pass
    return out
