"""
MARKET DATA FEED — EODHD primary, Finnhub fallback
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
import os

logger = logging.getLogger(__name__)


class RedundantDataFeed:
    """EODHD primary data source with Finnhub fallback."""

    def __init__(self, eodhd_key=None, finnhub_key=None):
        self.eodhd_key = eodhd_key or os.getenv("EODHD_API_KEY", "")
        self.finnhub_key = finnhub_key or os.getenv("FINNHUB_API_KEY", "")
        self.source_status = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_stock_data(self, symbol: str, period: str = "3mo") -> pd.DataFrame | None:
        """Return OHLCV DataFrame. Tries EODHD first, Finnhub second."""
        days = self._period_to_days(period)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days)

        data = self._get_eodhd_data(symbol, from_date, to_date)
        if data is not None and not data.empty:
            self.source_status[symbol] = "eodhd"
            return data

        logger.warning(f"EODHD failed for {symbol}, trying Finnhub")
        data = self._get_finnhub_data(symbol, from_date, to_date)
        if data is not None and not data.empty:
            self.source_status[symbol] = "finnhub"
            return data

        logger.error(f"All data sources failed for {symbol}")
        return None

    def get_real_time_quote(self, symbol: str) -> dict | None:
        """Return real-time quote dict. Tries EODHD first, Finnhub second."""
        quote = self._get_eodhd_quote(symbol)
        if quote:
            return quote
        return self._get_finnhub_quote(symbol)

    def verify_data_quality(self, data: pd.DataFrame) -> bool:
        if data is None or data.empty:
            return False
        if data.isnull().sum().sum() > len(data) * 0.1:
            logger.warning("Too many missing values in data")
            return False
        return True

    # ------------------------------------------------------------------
    # EODHD
    # ------------------------------------------------------------------

    def _get_eodhd_data(self, symbol: str, from_date: datetime, to_date: datetime) -> pd.DataFrame | None:
        try:
            url = (
                f"https://eodhd.com/api/eod/{symbol}.US"
                f"?api_token={self.eodhd_key}"
                f"&from={from_date.strftime('%Y-%m-%d')}"
                f"&to={to_date.strftime('%Y-%m-%d')}"
                f"&fmt=json"
            )
            r = requests.get(url, timeout=10)
            if r.status_code != 200 or not r.json():
                return None
            df = pd.DataFrame(r.json())
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")[["open", "high", "low", "close", "volume"]]
            return df
        except Exception as e:
            logger.warning(f"EODHD historical error for {symbol}: {e}")
            return None

    def _get_eodhd_quote(self, symbol: str) -> dict | None:
        try:
            url = f"https://eodhd.com/api/real-time/{symbol}.US?api_token={self.eodhd_key}&fmt=json"
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                return None
            d = r.json()
            price = float(d.get("close") or d.get("previousClose", 0))
            if price <= 0:
                return None
            return {
                "symbol": symbol,
                "price": price,
                "volume": int(d.get("volume", 0)),
                "change_pct": float(d.get("change_p", 0)),
                "timestamp": datetime.now(),
            }
        except Exception as e:
            logger.warning(f"EODHD quote error for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------
    # Finnhub
    # ------------------------------------------------------------------

    def _get_finnhub_data(self, symbol: str, from_date: datetime, to_date: datetime) -> pd.DataFrame | None:
        try:
            url = (
                f"https://finnhub.io/api/v1/stock/candle"
                f"?symbol={symbol}&resolution=D"
                f"&from={int(from_date.timestamp())}"
                f"&to={int(to_date.timestamp())}"
                f"&token={self.finnhub_key}"
            )
            r = requests.get(url, timeout=10)
            d = r.json()
            if d.get("s") != "ok" or not d.get("t"):
                return None
            df = pd.DataFrame({
                "date": pd.to_datetime(d["t"], unit="s"),
                "open": d["o"],
                "high": d["h"],
                "low": d["l"],
                "close": d["c"],
                "volume": d["v"],
            }).set_index("date")
            return df
        except Exception as e:
            logger.warning(f"Finnhub historical error for {symbol}: {e}")
            return None

    def _get_finnhub_quote(self, symbol: str) -> dict | None:
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={self.finnhub_key}"
            r = requests.get(url, timeout=10)
            d = r.json()
            price = float(d.get("c", 0))
            if price <= 0:
                return None
            prev = float(d.get("pc", price))
            change_pct = ((price - prev) / prev * 100) if prev else 0
            return {
                "symbol": symbol,
                "price": price,
                "volume": 0,
                "change_pct": change_pct,
                "timestamp": datetime.now(),
            }
        except Exception as e:
            logger.warning(f"Finnhub quote error for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _period_to_days(period: str) -> int:
        mapping = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "6mo": 180, "1y": 365}
        return mapping.get(period, 90)
