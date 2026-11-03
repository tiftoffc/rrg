import yfinance as yf
import pandas as pd
import json
from datetime import datetime

SECTORS = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care",
    "XLE": "Energy", "XLI": "Industrials", "XLC": "Communication Services",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
    "XLB": "Materials", "XLRE": "Real Estate", "XLU": "Utilities"
}
BENCHMARK = "SPY"
WINDOW = 14          # oder 20 für Daily
TAIL_LENGTH = 12

def calculate_rrg(df_close, window):
    # RS = 100 * sector / benchmark
    rs = 100 * df_close.div(df_close[BENCHMARK], axis=0)
    
    # RS-Ratio ≈ 100 + z-score der RS
    rs_mean = rs.rolling(window).mean()
    rs_std = rs.rolling(window).std(ddof=0)
    rs_ratio = 100 + (rs - rs_mean) / rs_std
    
    # RS-Momentum ≈ 100 + z-score der ROC der RS-Ratio
    roc = rs_ratio.pct_change() * 100
    roc_mean = roc.rolling(window).mean()
    roc_std = roc.rolling(window).std(ddof=0)
    rs_momentum = 100 + (roc - roc_mean) / roc_std
    
    return rs_ratio, rs_momentum

# Download + Berechnung + JSON schreiben
# (vollständigen Code kann ich dir als fertige Datei geben)
