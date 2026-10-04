from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

import analysis
import fetch
import render

st.set_page_config(page_title="Equity Risk Analyst", page_icon="▲", layout="wide")
st.markdown("<style>.stApp{background:#08090d}</style>", unsafe_allow_html=True)
st.title("▲ Equity Risk Analyst — NSE")
st.caption("Educational reference only. Not investment advice or a SEBI-registered research recommendation. "
           "All numbers are fetched live on every run (no caching, no preloaded data).")

c1, c2 = st.columns([1, 2])
query = c1.text_input("Company name or NSE ticker", placeholder="e.g. RELIANCE or Tata Motors")
peer_in = c2.text_input("Peers (optional, comma-separated, up to 4)", placeholder="Leave blank to auto-pick 4 direct listed peers")
go = st.button("Generate report", type="primary", disabled=not query.strip())

if go:
    steps = st.status("Fetching live data…", expanded=True)
    try:
        steps.write("Resolving company on Screener.in")
        hit = fetch.search_screener(query)
        if not hit:
            steps.update(label="Company not found", state="error")
            st.error(f"No match for '{query}'.")
            st.stop()
        steps.write(f"Fetching consolidated financials for {hit['name']}")
        d = fetch.parse_company(hit["url"])
        steps.write("Selecting and fetching peers")
        user_peers = [p.strip() for p in peer_in.split(",") if p.strip()]
        paths, peer_src = fetch.pick_peers(d, user_peers)
        peers = fetch.fetch_peers(paths)
        steps.write("Fetching price history, cash and consensus (Yahoo Finance fallback)")
        mk = fetch.fetch_market(f"{d['nse']}.NS" if d["nse"] else (f"{d['bse']}.BO" if d["bse"] else f"{d['slug']}.NS"))
        steps.write("Scoring and rendering")
        R = analysis.compute(d, peers, mk)
        date = datetime.now().strftime("%d %b %Y %H:%M IST").replace(" IST", "")
        html = render.build(d, peers, peer_src, R, mk, date)
        steps.update(label="Report ready", state="complete", expanded=False)
    except Exception as e:  # surface, don't hide
        steps.update(label="Failed", state="error")
        st.exception(e)
        st.stop()

    st.download_button("⬇ Download self-contained HTML", html, file_name=f"{d['slug']}_risk_report.html", mime="text/html")
    components.html(html, height=2600, scrolling=True)
