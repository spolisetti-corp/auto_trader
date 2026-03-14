import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
from config import config
from infrastructure.data_feed import RedundantDataFeed

class PolygonMarketScanner:
    def __init__(self, api_key):
        # Store API key for EODHD requests
        self.api_key = api_key
        self.config = config
        self.data_feed = RedundantDataFeed(polygon_key=api_key)
        self.logger = logging.getLogger(__name__)
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI from price series"""
        if len(prices) < period + 1:
            return 50  # Neutral if not enough data
        
        deltas = np.diff(prices)
        gain = np.where(deltas > 0, deltas, 0)
        loss = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gain[:period])
        avg_loss = np.mean(loss[:period])
        
        for i in range(period, len(gain)):
            avg_gain = (avg_gain * (period - 1) + gain[i]) / period
            avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_momentum(self, prices, days):
        """Calculate percentage momentum over days"""
        if len(prices) < days + 1:
            return 0
        current = prices.iloc[-1]
        past = prices.iloc[-days-1]
        return ((current - past) / past) * 100
    
    def calculate_volume_ratio(self, volumes, period=20):
        """Calculate volume ratio (current vs average)"""
        if len(volumes) < period + 1:
            return 1.0
        current_volume = volumes.iloc[-1]
        avg_volume = volumes.iloc[-period-1:-1].mean()
        return current_volume / avg_volume if avg_volume > 0 else 1.0
    
    def get_swing_candidates(self):
        """Get swing trading candidates using EODHD screener API"""
        try:
            # Use EODHD screener API for trending stocks
            screener_url = f"https://eodhd.com/api/screener?api_token={self.config.EODHD_API_KEY}"
            screener_url += "&sort=market_capitalization.desc"
            screener_url += "&filters=["
            screener_url += "[\"market_capitalization\",\">\",1000000000],"  # $1B+ market cap
            screener_url += "[\"exchange\",\"=\",\"US\"],"
            screener_url += "[\"price\",\">\",10],"  # Min $10 price
            screener_url += "[\"price\",\"<\",300]"  # Max $300 price
            screener_url += "]"
            screener_url += "&limit=100&offset=0"
            
            response = requests.get(screener_url)
            screener_data = response.json()
            
            symbols_to_scan = [item['code'] for item in screener_data if 'code' in item]
            
            self.logger.info(f"Fetched {len(symbols_to_scan)} filtered symbols from EODHD screener")
            
            swing_candidates = []
            
            # Get date ranges for technical indicators (last 3 months)
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            
            for symbol in symbols_to_scan:
                try:
                    # Get real-time quote
                    quote_url = f"https://eodhd.com/api/real-time/{symbol}.US?api_token={self.config.EODHD_API_KEY}&fmt=json"
                    quote_response = requests.get(quote_url)
                    quote = quote_response.json() if quote_response.status_code == 200 else {}
                    
                    current_price = quote.get('close', 0)
                    current_volume = quote.get('volume', 0)
                    
                    if current_price <= 0:
                        continue
                    
                    # Get historical bars for calculations (last 3 months)
                    hist_url = f"https://eodhd.com/api/eod/{symbol}.US?api_token={self.config.EODHD_API_KEY}&from={from_date}&to={to_date}&fmt=json"
                    hist_response = requests.get(hist_url)

                    if hist_response.status_code == 200 and hist_response.json():
                        bars_data = hist_response.json()
                        bars = pd.DataFrame(bars_data)
                    else:
                        # Fallback to yfinance via RedundantDataFeed
                        self.logger.warning(f"EODHD historical failed for {symbol}, trying yfinance fallback")
                        yf_data = self.data_feed.get_stock_data(symbol, period='3mo')
                        if yf_data is None or not self.data_feed.verify_data_quality(yf_data):
                            continue
                        yf_data = yf_data.reset_index()
                        yf_data.columns = [c.lower() for c in yf_data.columns]
                        yf_data = yf_data.rename(columns={'date': 'date', 'close': 'close', 'volume': 'volume'})
                        bars = yf_data
                    
                    momentum_20d = 0
                    momentum_50d = 0
                    rsi = 50  # Default neutral
                    volume_momentum = 1.0
                    market_cap = 0
                    sector = 'Unknown'
                    long_name = symbol
                    
                    if not bars.empty and len(bars) >= 50:
                        # Calculate RSI using historical prices
                        prices = bars['close'].values
                        rsi = self.calculate_rsi(prices)
                        
                        # Calculate momentum
                        momentum_20d = self.calculate_momentum(bars.set_index('date')['close'], 20)
                        momentum_50d = self.calculate_momentum(bars.set_index('date')['close'], 50)
                        
                        # Calculate volume ratio
                        volumes = bars.set_index('date')['volume']
                        volume_momentum = self.calculate_volume_ratio(volumes)
                        
                        # Get company info from screener data
                        screener_item = next((item for item in screener_data if item.get('code') == symbol), {})
                        market_cap = screener_item.get('market_capitalization', 0)
                        sector = screener_item.get('sector', 'Unknown')
                        long_name = screener_item.get('name', symbol)
                    
                    # Calculate momentum score and dollar volume
                    momentum_score = (momentum_20d * 0.6 + momentum_50d * 0.4)
                    dollar_volume = current_price * current_volume
                    
                    # Basic filters
                    if (current_price >= self.config.MIN_PRICE and 
                        current_price <= self.config.MAX_PRICE and
                        market_cap >= self.config.MIN_MARKET_CAP and
                        dollar_volume >= self.config.MIN_DAILY_DOLLAR_VOLUME):
                        
                        candidate = {
                            'symbol': symbol,
                            'name': long_name,
                            'current_price': current_price,
                            'momentum_20d': momentum_20d,
                            'momentum_50d': momentum_50d,
                            'rsi': rsi,
                            'volume_momentum': volume_momentum,
                            'market_cap': market_cap,
                            'sector': sector,
                            'momentum_score': momentum_score,
                            'dollar_volume': dollar_volume,
                            'spread_pct': 0.002,
                            'above_sma_20': True,  # Placeholder
                            'above_sma_50': True   # Placeholder
                        }
                        
                        swing_candidates.append(candidate)
                    
                    # Rate limiting for EODHD
                    time.sleep(0.5)  # 0.5 second between requests
                    
                except Exception as e:
                    self.logger.warning(f"Error processing {symbol}: {e}")
                    continue
            
            self.logger.info(f"Scanned {len(symbols_to_scan)} symbols with EODHD screener, found {len(swing_candidates)} candidates")
            return swing_candidates
            
        except Exception as e:
            self.logger.error(f"Error getting swing candidates from EODHD screener: {e}")
            return []
    
    def filter_swing_trades(self, candidates, max_trades=None):
        """Filter candidates using config.is_aggressive_candidate"""
        if max_trades is None:
            max_trades = self.config.MAX_POSITIONS
            
        swing_trades = []
        
        for candidate in candidates:
            # Use config's aggressive candidate check
            if self.config.is_aggressive_candidate(candidate):
                swing_trades.append(candidate)
        
        # Sort by momentum score and return top trades
        swing_trades.sort(key=lambda x: x['momentum_score'], reverse=True)
        return swing_trades[:max_trades]
    
    def get_real_time_quote(self, symbol):
        """Get real-time quote from EODHD API"""
        try:
            url = f"https://eodhd.com/api/real-time/{symbol}.US?api_token={self.api_key}&fmt=json"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                price = data.get('close', 0) or data.get('previousClose', 0)
                return {
                    'price': float(price),
                    'volume': int(data.get('volume', 0)),
                    'change': float(data.get('change_p', 0)),
                }
        except Exception as e:
            self.logger.warning(f"Error fetching real-time quote for {symbol}: {e}")
        return {'price': 0, 'volume': 0, 'change': 0}

def main():
    scanner = PolygonMarketScanner("utj3oghr1PD1OggLcpvkpUpiP6OQbRYO")
    
    print("🚀 POLYGON SWING TRADING SCANNER")
    print("=" * 60)
    
    # Get candidates
    candidates = scanner.get_swing_candidates()
    print(f"📊 Found {len(candidates)} swing candidates")
    
    # Filter for swing trades
    swing_trades = scanner.filter_swing_trades(candidates, max_trades=3)
    print(f"🎯 Qualified swing trades: {len(swing_trades)}")
    
    print("\n📈 TODAY'S SWING TRADES:")
    print("-" * 60)
    
    for i, trade in enumerate(swing_trades):
        print(f"{i+1}. {trade['symbol']} - {trade['name']}")
        print(f"   Price: ${trade['current_price']:.2f}")
        print(f"   Momentum: {trade['momentum_20d']:+.1f}% (20D)")
        print(f"   RSI: {trade['rsi']:.1f}")
        print(f"   Volume: {trade['volume_momentum']:.1f}x avg")
        print(f"   Sector: {trade['sector']}")
        print(f"   Score: {trade['momentum_score']:.1f}")
        print()

if __name__ == "__main__":
    main()
