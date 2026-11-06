"""Fetch real ETF price history for the portfolio app's universe.

Downloads ~5 years of daily closes for a curated set of liquid ETFs via
yfinance, plus approximate annual dividend yields, then writes two bundled
CSVs used by the app:

    data/etf_prices.csv   daily Close per ticker (dates x tickers)
    data/etf_meta.csv     ticker, name, asset_class, defensive, div_yield_pct

If the download fails (no internet / Yahoo rate limits), a synthetic but
realistic dataset is generated instead and SOURCE.txt records which path
was taken, so the app is always runnable offline.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

TICKERS = [
    "SPY", "QQQ", "IWM", "VTI",          # US equity
    "VXUS", "EFA",                        # international equity
    "BND", "TLT", "LQD", "HYG", "SHY",   # bonds
    "GLD", "VNQ",                          # alternatives (gold, real estate)
]

# Fallback dividend yields (annual %, approximate) used only if yfinance
# info lookups fail. yfinance values override these when available.
FALLBACK_DIV_YIELD = {
    "SPY": 1.2, "QQQ": 0.6, "IWM": 1.6, "VTI": 1.3,
    "VXUS": 2.9, "EFA": 2.8,
    "BND": 3.5, "TLT": 3.9, "LQD": 4.4, "HYG": 5.8, "SHY": 3.9,
    "GLD": 0.0, "VNQ": 3.6,
}

META = {
    "SPY": ("SPDR S&P 500 ETF", "US Equity"),
    "QQQ": ("Invesco Nasdaq-100 ETF", "US Equity"),
    "IWM": ("iShares Russell 2000 ETF", "US Equity"),
    "VTI": ("Vanguard Total Stock Market ETF", "US Equity"),
    "VXUS": ("Vanguard Total Intl Stock ETF", "International"),
    "EFA": ("iShares MSCI EAFE ETF", "International"),
    "BND": ("Vanguard Total Bond Market ETF", "Bonds"),
    "TLT": ("iShares 20+ Yr Treasury ETF", "Bonds"),
    "LQD": ("iShares Inv Grade Corp Bond ETF", "Bonds"),
    "HYG": ("iShares High Yield Corp Bond ETF", "Bonds"),
    "SHY": ("iShares 1-3 Yr Treasury ETF", "Bonds"),
    "GLD": ("SPDR Gold Shares ETF", "Alternatives"),
    "VNQ": ("Vanguard Real Estate ETF", "Alternatives"),
}

DEFENSIVE_CLASSES = {"Bonds", "Alternatives"}  # gold counts as a diversifier


def dividend_yield_pct(annual, price, fallback: float) -> float:
    """Trailing annual cash distribution divided by price, in percent units."""
    try:
        annual, price = float(annual), float(price)
        if np.isfinite(annual) and np.isfinite(price) and annual >= 0 and price > 0:
            return 100.0 * annual / price
    except (TypeError, ValueError):
        pass
    return fallback


def _fetch_live() -> tuple[pd.DataFrame, dict, int]:
    """Return (price_df, div_yields, n_days_downloaded). Raises on total failure."""
    import yfinance as yf

    raw = yf.download(
        TICKERS, period="5y", interval="1d", auto_adjust=True,
        progress=False, threads=False,
    )
    if raw is None or raw.empty:
        raise RuntimeError("yfinance returned no data")

    closes = raw["Close"].dropna(how="all")
    closes = closes.dropna(axis=1, thresh=max(60, int(0.5 * len(closes))))
    if closes.shape[1] < 4:
        raise RuntimeError("too few tickers survived download")

    div: dict[str, float] = {}
    for t in closes.columns:
        try:
            info = yf.Ticker(t).info
            # Compute a percentage from annual cash dividend / current price.
            # Avoid dividendYield, whose unit conventions have varied.
            annual = info.get("trailingAnnualDividendRate")
            price = info.get("regularMarketPrice") or info.get("previousClose")
            div[t] = dividend_yield_pct(annual, price, FALLBACK_DIV_YIELD[t])
        except Exception:
            div[t] = FALLBACK_DIV_YIELD[t]

    return closes, div, int(len(closes))


def _fetch_synthetic(seed: int = 2026) -> tuple[pd.DataFrame, dict]:
    """Realistic synthetic daily closes so the app runs fully offline."""
    rng = np.random.default_rng(seed)
    n_days = 252 * 5
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n_days)

    # Annualized mean / vol per asset class (plausible long-run values).
    class_stats = {
        "US Equity": (0.090, 0.160),
        "International": (0.075, 0.170),
        "Bonds": (0.040, 0.065),
        "Alternatives": (0.055, 0.150),
    }
    corr = {
        "US Equity": {"US Equity": 1.00, "International": 0.80, "Bonds": 0.10, "Alternatives": 0.35},
        "International": {"US Equity": 0.80, "International": 1.00, "Bonds": 0.15, "Alternatives": 0.30},
        "Bonds": {"US Equity": 0.10, "International": 0.15, "Bonds": 1.00, "Alternatives": 0.05},
        "Alternatives": {"US Equity": 0.35, "International": 0.30, "Bonds": 0.05, "Alternatives": 1.00},
    }
    classes = [META[t][1] for t in TICKERS]
    means = np.array([class_stats[c][0] / 252 for c in classes])
    vols = np.array([class_stats[c][1] / np.sqrt(252) for c in classes])
    corr_mat = np.array([[corr[a][b] for b in classes] for a in classes])
    cov = corr_mat * np.outer(vols, vols)

    z = rng.multivariate_normal(np.zeros(len(TICKERS)), cov, size=n_days)
    daily_rets = np.exp(means + z - 0.5 * np.diag(cov)) - 1.0
    prices = 100.0 * np.cumprod(1.0 + daily_rets, axis=0)

    closes = pd.DataFrame(prices, index=dates, columns=TICKERS)
    div = dict(FALLBACK_DIV_YIELD)
    return closes, div


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    source = "unknown"
    try:
        closes, div, n_days = _fetch_live()
        source = f"yfinance live download ({n_days} trading days, ~5y)"
        print(f"[ok] live download: {closes.shape}")
    except Exception as exc:  # noqa: BLE001 - fall back deliberately
        print(f"[warn] live download failed ({exc}); using synthetic data")
        closes, div = _fetch_synthetic()
        source = "synthetic (generated offline; mean/vol per asset class, seeded)"

    rows = []
    for t in closes.columns:
        name, cls = META[t]
        rows.append({
            "ticker": t,
            "name": name,
            "asset_class": cls,
            "defensive": int(cls in DEFENSIVE_CLASSES),
            "div_yield_pct": round(div.get(t, FALLBACK_DIV_YIELD[t]), 3),
        })
    meta = pd.DataFrame(rows)

    closes.to_csv(os.path.join(DATA_DIR, "etf_prices.csv"))
    meta.to_csv(os.path.join(DATA_DIR, "etf_meta.csv"), index=False)
    with open(os.path.join(DATA_DIR, "SOURCE.txt"), "w", encoding="utf-8") as fh:
        fh.write(source + "\n")
    print(f"[ok] wrote {closes.shape[1]} tickers x {closes.shape[0]} days to data/")
    print(f"[ok] source: {source}")


if __name__ == "__main__":
    sys.exit(main())
