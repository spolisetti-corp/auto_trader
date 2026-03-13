#!/usr/bin/env python3
"""Check why no new trades after AAPL"""
import sys
import os
sys.path.append('c:/Users/user/Desktop/ws_finance')

# Force reload config to pick up .env changes
if 'aggressive_config' in sys.modules:
    del sys.modules['aggressive_config']

from polygon_market_scanner import PolygonMarketScanner
from aggressive_config import config

print('CONFIG VALUES AFTER RELOAD:')
print(f'MIN_VOLUME_RATIO: {config.MIN_VOLUME_RATIO}')
print(f'MIN_MOMENTUM: {config.MIN_MOMENTUM}')
print(f'MAX_RSI: {config.MAX_RSI}')
print('='*60)

# Initialize scanner
scanner = PolygonMarketScanner(config.POLYGON_API_KEY)

print('CHECKING FOR NEW TRADE OPPORTUNITIES')
print('='*60)

# Get swing candidates
candidates = scanner.get_swing_candidates()
print(f'Total candidates found: {len(candidates)}')

if candidates:
    print('\nTop 5 candidates:')
    for i, candidate in enumerate(candidates[:5]):
        print(f'{i+1}. {candidate["symbol"]} - Momentum: {candidate["momentum_score"]:.1f} - Price: ${candidate["current_price"]:.2f}')
    
    # Filter with aggressive criteria
    filtered = scanner.filter_swing_trades(candidates)
    print(f'\nAggressive filtered trades: {len(filtered)}')
    
    if filtered:
        for trade in filtered[:3]:
            print(f'  - {trade["symbol"]}: RSI {trade.get("rsi", "N/A")} | Volume {trade.get("volume_ratio", "N/A")}x')
    else:
        print('  None met aggressive criteria')
        
        # Check why filtered out
        print('\nWhy candidates were filtered out:')
        for candidate in candidates[:5]:
            reasons = []
            
            # Check momentum
            if candidate.get('momentum_score', 0) < config.MIN_MOMENTUM:
                reasons.append(f'Low momentum ({candidate.get("momentum_score", 0):.1f} < {config.MIN_MOMENTUM})')
            
            # Check RSI
            rsi = candidate.get('rsi', 50)
            if rsi > config.MAX_RSI:
                reasons.append(f'RSI too high ({rsi:.1f} > {config.MAX_RSI})')
            
            # Check volume
            vol_momentum = candidate.get('volume_momentum', 0)
            vol_ratio = candidate.get('volume_ratio', 0)
            print(f'  {candidate["symbol"]}: volume_momentum={vol_momentum:.1f}, volume_ratio={vol_ratio:.1f}')
            
            if vol_momentum < config.MIN_VOLUME_RATIO:
                reasons.append(f'Low volume momentum ({vol_momentum:.1f}x < {config.MIN_VOLUME_RATIO}x)')
            
            # Check market cap
            mcap = candidate.get('market_cap', 0)
            if mcap < config.MIN_MARKET_CAP:
                reasons.append(f'Market cap too low (${mcap/1e9:.1f}B < ${config.MIN_MARKET_CAP/1e9:.0f}B)')
            
            # Check dollar volume
            dollar_vol = candidate.get('dollar_volume', 0)
            if dollar_vol < config.MIN_DAILY_DOLLAR_VOLUME:
                reasons.append(f'Dollar volume too low (${dollar_vol/1e6:.1f}M < ${config.MIN_DAILY_DOLLAR_VOLUME/1e6:.1f}M)')
            
            if reasons:
                print(f'    REJECTED: {" | ".join(reasons)}')
            else:
                print(f'    PASSED: All checks met')
else:
    print('No candidates found')

# Check current market conditions
print('\n' + '='*60)
print('MARKET CONDITIONS')
print('='*60)

try:
    import yfinance as yf
    spy = yf.Ticker('SPY')
    spy_data = spy.history(period='2d')
    if len(spy_data) >= 2:
        current = spy_data['Close'].iloc[-1]
        prev = spy_data['Close'].iloc[-2]
        change = ((current - prev) / prev) * 100
        print(f'SPY: {current:.2f} ({change:+.1f}%)')
        
        if abs(change) > 1:
            print('Market movement detected - may affect trading')
        elif abs(change) < 0.3:
            print('Low volatility - fewer opportunities')
            
    # Check VIX
    vix = yf.Ticker('^VIX')
    vix_data = vix.history(period='2d')
    if len(vix_data) >= 2:
        vix_current = vix_data['Close'].iloc[-1]
        print(f'VIX: {vix_current:.1f}')
        
        if vix_current > 25:
            print('High VIX - volatile market, fewer setups')
        elif vix_current < 12:
            print('Low VIX - calm market, less momentum')
            
except Exception as e:
    print(f'Could not fetch market data: {e}')

# Check system status
print('\n' + '='*60)
print('TRADING SYSTEM STATUS')
print('='*60)

try:
    import subprocess
    result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq python.exe'], capture_output=True, text=True)
    python_count = result.stdout.count('python.exe')
    print(f'Python processes running: {python_count}')
    
    if python_count > 0:
        print('Trading system appears to be running')
        
        # Check if main trader is running
        if 'main_aggressive_trader.py' in result.stdout:
            print('Main trading process detected')
        else:
            print('Main trading process not found')
    else:
        print('No trading system detected')
        
except Exception as e:
    print(f'Could not check system status: {e}')

# Check PDT limits
print('\n' + '='*60)
print('PDT & POSITION LIMITS')
print('='*60)

from alpaca.trading.client import TradingClient
try:
    client = TradingClient(config.APCA_API_KEY_ID, config.APCA_API_SECRET_KEY, paper=True)
    
    # Get account
    account = client.get_account()
    print(f'Portfolio Value: ${float(account.equity):,.2f}')
    print(f'Day Trade Count: {account.daytrade_count}')
    print(f'Pattern Day Trader: {account.pattern_day_trader}')
    
    # Check positions
    positions = client.get_all_positions()
    print(f'Current positions: {len(positions)}')
    
    if len(positions) >= config.MAX_POSITIONS:
        print(f'Max positions reached ({config.MAX_POSITIONS})')
        
except Exception as e:
    print(f'Could not check account: {e}')
