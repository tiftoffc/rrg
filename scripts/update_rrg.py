#!/usr/bin/env python3
"""
RRG Data Updater – robustere Version
"""

import yfinance as yf
import pandas as pd
import json
import time
from datetime import datetime, timezone
from pathlib import Path

SECTORS = {
    "XLK":  "Technology",
    "XLF":  "Financials",
    "XLV":  "Health Care",
    "XLE":  "Energy",
    "XLI":  "Industrials",
    "XLC":  "Communication Services",
    "XLY":  "Consumer Discretionary",
    "XLP":  "Consumer Staples",
    "XLB":  "Materials",
    "XLRE": "Real Estate",
    "XLU":  "Utilities",
}

BENCHMARK = "SPY"
WINDOW = 14
TAIL_LENGTH = 12
OUTPUT_DIR = Path("public")
OUTPUT_DIR.mkdir(exist_ok=True)


def download_with_retry(tickers, period="2y", max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Download-Versuch {attempt}/{max_retries}...")
            data = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=False)["Close"]
            data = data.dropna(how="all").ffill()
            if not data.empty:
                print(f"Erfolgreich geladen: {data.shape[0]} Zeilen, {list(data.columns)}")
                return data
        except Exception as e:
            print(f"Versuch {attempt} fehlgeschlagen: {e}")
            time.sleep(5)
    raise RuntimeError("Download nach mehreren Versuchen fehlgeschlagen")


def calculate_rrg(close: pd.DataFrame, window: int):
    # Nur Spalten verwenden, die wirklich da sind
    available = [c for c in close.columns if c in list(SECTORS.keys()) + [BENCHMARK]]
    close = close[available]

    rs = 100 * close.div(close[BENCHMARK], axis=0)
    rs_mean = rs.rolling(window).mean()
    rs_std = rs.rolling(window).std(ddof=0)
    rs_ratio = 100 + (rs - rs_mean) / rs_std.replace(0, pd.NA)

    roc = rs_ratio.pct_change() * 100
    roc_mean = roc.rolling(window).mean()
    roc_std = roc.rolling(window).std(ddof=0)
    rs_momentum = 100 + (roc - roc_mean) / roc_std.replace(0, pd.NA)
    return rs_ratio, rs_momentum


def build_output(rs_ratio: pd.DataFrame, rs_momentum: pd.DataFrame, tail_len: int) -> list:
    sectors_out = []
    for ticker, name in SECTORS.items():
        if ticker not in rs_ratio.columns:
            print(f"Warnung: {ticker} nicht in den Daten")
            continue
        r = rs_ratio[ticker].dropna()
        m = rs_momentum[ticker].dropna()
        if len(r) < 2 or len(m) < 2:
            continue
        common = r.index.intersection(m.index)
        r = r.loc[common]
        m = m.loc[common]
        if len(r) < 2:
            continue

        tail_r = r.iloc[-tail_len:]
        tail_m = m.iloc[-tail_len:]
        tail = [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "rs_ratio": round(float(tail_r.loc[idx]), 2),
                "rs_momentum": round(float(tail_m.loc[idx]), 2),
            }
            for idx in tail_r.index
        ]
        current = {
            "rs_ratio": round(float(r.iloc[-1]), 2),
            "rs_momentum": round(float(m.iloc[-1]), 2),
        }
        sectors_out.append({
            "ticker": ticker,
            "name": name,
            "current": current,
            "tail": tail,
        })
    return sectors_out


def main():
    tickers = list(SECTORS.keys()) + [BENCHMARK]
    data = download_with_retry(tickers)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Daily
    print("Berechne Daily...")
    rs_ratio_d, rs_mom_d = calculate_rrg(data, WINDOW)
    daily_sectors = build_output(rs_ratio_d, rs_mom_d, TAIL_LENGTH)
    daily_out = {"updated": now, "timeframe": "daily", "sectors": daily_sectors}
    (OUTPUT_DIR / "rrg-daily.json").write_text(json.dumps(daily_out, indent=2))
    print(f"Daily: {len(daily_sectors)} Sektoren geschrieben")

    # Weekly
    print("Berechne Weekly...")
    weekly = data.resample("W-FRI").last().dropna(how="all")
    rs_ratio_w, rs_mom_w = calculate_rrg(weekly, WINDOW)
    weekly_sectors = build_output(rs_ratio_w, rs_mom_w, TAIL_LENGTH)
    weekly_out = {"updated": now, "timeframe": "weekly", "sectors": weekly_sectors}
    (OUTPUT_DIR / "rrg-weekly.json").write_text(json.dumps(weekly_out, indent=2))
    print(f"Weekly: {len(weekly_sectors)} Sektoren geschrieben")

    # Meta
    (OUTPUT_DIR / "last_update.json").write_text(json.dumps({"updated": now}, indent=2))
    print("Fertig.")


if __name__ == "__main__":
    main()
