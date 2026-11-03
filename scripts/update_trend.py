#!/usr/bin/env python3
"""
Erzeugt trend_4w.json aus RRG-Weekly + RSL-26W
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

OUTPUT_DIR = Path("public")
OUTPUT_DIR.mkdir(exist_ok=True)

# Mapping Sektor-Name → ETF-Ticker (aus deinem RRG)
SECTOR_TO_TICKER = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}

def get_quadrant(rs_ratio, rs_momentum):
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "Leading"
    if rs_ratio >= 100 and rs_momentum < 100:
        return "Weakening"
    if rs_ratio < 100 and rs_momentum < 100:
        return "Lagging"
    return "Improving"

def score_sector(quadrant, rs_momentum, avg_rsl):
    base = {"Leading": 40, "Improving": 30, "Weakening": 10, "Lagging": 0}.get(quadrant, 0)
    mom_score = max(0, min(30, (rs_momentum - 98) * 3))  # grob 0–30
    rsl_score = max(0, min(30, (avg_rsl - 50) * 0.6))   # grob 0–30
    return round(base + mom_score + rsl_score)

def main():
    # RRG lokal (wurde gerade geschrieben)
    rrg = json.loads((OUTPUT_DIR / "rrg-weekly.json").read_text())

    # RSL von der bestehenden RSL-Seite holen
    rsl_url = "https://raw.githubusercontent.com/tiftoffc/rsl-sp500/main/rsl_26w.json"
    print(f"Lade RSL von {rsl_url}")
    with urllib.request.urlopen(rsl_url) as resp:
        rsl = json.loads(resp.read().decode())

    # RSL nach Sektor gruppieren
    by_sector = defaultdict(list)
    for item in rsl:
        sector = item.get("sector")
        if sector and sector != "-":
            by_sector[sector].append(item)

    # RRG nach Ticker
    rrg_by_ticker = {s["ticker"]: s for s in rrg.get("sectors", [])}

    result = []
    for sector_name, ticker in SECTOR_TO_TICKER.items():
        rrg_data = rrg_by_ticker.get(ticker)
        if not rrg_data:
            continue

        stocks = by_sector.get(sector_name, [])
        if not stocks:
            avg_rsl = None
            top_tickers = []
        else:
            rsl_values = [s.get("rsl") or 0 for s in stocks]
            avg_rsl = round(sum(rsl_values) / len(rsl_values), 1)
            top = sorted(stocks, key=lambda x: x.get("rsl") or 0, reverse=True)[:3]
            top_tickers = [{"ticker": t["ticker"], "rsl": round(t.get("rsl") or 0, 2)} for t in top]

        c = rrg_data["current"]
        quadrant = get_quadrant(c["rs_ratio"], c["rs_momentum"])
        score = score_sector(quadrant, c["rs_momentum"], avg_rsl or 50)

        if score >= 70:
            einschätzung = "Übergewichten"
        elif score >= 50:
            einschätzung = "Neutral / Watch"
        else:
            einschätzung = "Untergewichten"

        result.append({
            "sector": sector_name,
            "ticker": ticker,
            "quadrant": quadrant,
            "rs_ratio": c["rs_ratio"],
            "rs_momentum": c["rs_momentum"],
            "avg_rsl": avg_rsl,
            "top_tickers": top_tickers,
            "score": score,
            "einschätzung": einschätzung,
        })

    # Nach Score sortieren
    result.sort(key=lambda x: x["score"], reverse=True)

    out = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "sectors": result,
    }
    (OUTPUT_DIR / "trend_4w.json").write_text(json.dumps(out, indent=2))
    print(f"trend_4w.json geschrieben ({len(result)} Sektoren)")

if __name__ == "__main__":
    main()
