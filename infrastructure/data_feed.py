"""
MARKET DATA REDUNDANCY SYSTEM
Proposed enhancement for reliable data feeds
"""

import yfinance as yf
import requests
import pandas as pd
from datetime import datetime
import time
import logging

class RedundantDataFeed:
    """
    Multiple data source fallback system
    """
    
    def __init__(self, polygon_key=None):
        self.polygon_key = polygon_key
        self.data_sources = {
            'primary': 'polygon',
            'fallback_1': 'yfinance',
            'fallback_2': 'alphavantage'  # If API key available
        }
        self.source_status = {}
        
    def get_stock_data(self, symbol, period='1mo'):
        """
        Get stock data with automatic fallback
        """
        # Try Polygon first
        if self.polygon_key:
            try:
                data = self._get_polygon_data(symbol, period)
                if data is not None and len(data) > 0:
                    self.source_status[symbol] = 'polygon'
                    return data
            except Exception as e:
                logging.warning(f"Polygon failed for {symbol}: {e}")
        
        # Fallback to Yahoo Finance
        try:
            data = self._get_yfinance_data(symbol, period)
            if data is not None and len(data) > 0:
                self.source_status[symbol] = 'yfinance'
                logging.info(f"Using Yahoo Finance for {symbol}")
                return data
        except Exception as e:
            logging.warning(f"Yahoo Finance failed for {symbol}: {e}")
        
        # All sources failed
        logging.error(f"All data sources failed for {symbol}")
        return None
    
    def get_real_time_quote(self, symbol):
        """
        Get real-time quote with fallback
        """
        # Try Polygon
        if self.polygon_key:
            try:
                quote = self._get_polygon_quote(symbol)
                if quote:
                    return quote
            except:
                pass
        
        # Fallback to Yahoo Finance
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='1d', interval='1m')
            
            if len(hist) > 0:
                return {
                    'symbol': symbol,
                    'price': hist['Close'].iloc[-1],
                    'volume': hist['Volume'].iloc[-1],
                    'timestamp': datetime.now()
                }
        except:
            pass
        
        return None
    
    def _get_polygon_data(self, symbol, period):
        """Get data from Polygon.io"""
        # Implementation would use Polygon API
        # Simplified version shown
        pass
    
    def _get_yfinance_data(self, symbol, period):
        """Get data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period)
            return data
        except Exception as e:
            logging.error(f"YFinance error: {e}")
            return None
    
    def _get_polygon_quote(self, symbol):
        """Get quote from Polygon"""
        # Implementation would use Polygon API
        pass
    
    def verify_data_quality(self, data):
        """
        Check if data meets quality standards
        """
        if data is None or len(data) == 0:
            return False
        
        # Check for recent data
        latest_date = data.index[-1]
        hours_since_update = (datetime.now() - latest_date).total_seconds() / 3600
        
        if hours_since_update > 24:
            logging.warning(f"Data is {hours_since_update:.1f} hours old")
            return False
        
        # Check for missing values
        if data.isnull().sum().sum() > len(data) * 0.1:  # >10% missing
            logging.warning("Too many missing values in data")
            return False
        
        return True

# PROPOSED INTEGRATION:
# Modify polygon_market_scanner.py:
#
# class PolygonMarketScanner:
#     def __init__(self, api_key):
#         self.api_key = api_key
#         self.data_feed = RedundantDataFeed(api_key)
#     
#     def get_swing_candidates(self):
#         # Use redundant data feed
#         data = self.data_feed.get_stock_data(symbol)
#         if not self.data_feed.verify_data_quality(data):
#             logging.warning(f"Poor data quality for {symbol}")
#             continue
