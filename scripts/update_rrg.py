#!/usr/bin/env python3
"""
RRG Data Updater
Erzeugt rrg-daily.json und rrg-weekly.json für die WordPress-Seite
"""

import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timezone
from pathlib import Path

# === Konfiguration ===
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
WINDOW = 14          # Lookback für RS-Ratio / Momentum
TAIL_LENGTH = 12     # Anzahl Punkte im Tail
OUTPUT_DIR = Path("public")

OUTPUT_DIR.mkdir(exist_ok=True)


def calculate_rrg(close: pd.DataFrame, window: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Berechnet RS-Ratio und RS-Momentum (Z-Score-Annäherung)"""
    rs = 100 * close.div(close[BENCHMARK], axis=0)

    # RS-Ratio
    rs_mean = rs.rolling(window).mean()
    rs_std = rs.rolling(window).std(ddof=0)
    rs_ratio = 100 + (rs - rs_mean) / rs_std.replace(0, pd.NA)

    # RS-Momentum
    roc = rs_ratio.pct_change() * 100
    roc_mean = roc.rolling(window).mean()
    roc_std = roc.rolling(window).std(ddof=0)
    rs_momentum = 100 + (roc - roc_mean) / roc_std.replace(0, pd.NA)

    return rs_ratio, rs_momentum


def build_output(rs_ratio: pd.DataFrame, rs_momentum: pd.DataFrame, tail_len: int) -> list:
    sectors_out = []

    for ticker, name in SECTORS.items():
        if ticker not in rs_ratio.columns:
            continue

        r = rs_ratio[ticker].dropna()
        m = rs_momentum[ticker].dropna()

        if len(r) < 2 or len(m) < 2:
            continue

        # Align
        common = r.index.intersection(m.index)
        r = r.loc[common]
        m = m.loc[common]

        # Tail (letzte N Punkte)
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
    print("Lade Daten...")
    tickers = list(SECTORS.keys()) + [BENCHMARK]
    data = yf.download(tickers, period="2y", auto_adjust=True, progress=False)["Close"]
    data = data.dropna(how="all").ffill()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # === Daily ===
    print("Berechne Daily RRG...")
    rs_ratio_d, rs_mom_d = calculate_rrg(data, WINDOW)
    daily_sectors = build_output(rs_ratio_d, rs_mom_d, TAIL_LENGTH)

    daily_out = {
        "updated": now,
        "timeframe": "daily",
        "sectors": daily_sectors,
    }

    # === Weekly ===
    print("Berechne Weekly RRG...")
    weekly = data.resample("W-FRI").last().dropna(how="all")
    rs_ratio_w, rs_mom_w = calculate_rrg(weekly, WINDOW)
    weekly_sectors = build_output(rs_ratio_w, rs_mom_w, TAIL_LENGTH)

    weekly_out = {
        "updated": now,
        "timeframe": "weekly",
        "sectors": weekly_sectors,
    }

    # Schreiben
    (OUTPUT_DIR / "rrg-daily.json").write_text(json.dumps(daily_out, indent=2))
    (OUTPUT_DIR / "rrg-weekly.json").write_text(json.dumps(weekly_out, indent=2))

    meta = {"updated": now}
    (OUTPUT_DIR / "last_update.json").write_text(json.dumps(meta, indent=2))

    print(f"Fertig. {len(daily_sectors)} Sektoren geschrieben.")
    print(f"Dateien: public/rrg-daily.json, public/rrg-weekly.json, public/last_update.json")


if __name__ == "__main__":
    main()
