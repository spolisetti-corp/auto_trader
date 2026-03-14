#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""Quick check for new trades"""
from alpaca.trading.client import TradingClient
from config import config

# Initialize client
client = TradingClient(config.APCA_API_KEY_ID, config.APCA_API_SECRET_KEY, paper=True)

# Get positions
positions = client.get_all_positions()
orders = client.get_orders()

print('='*60)
print('CURRENT POSITIONS')
print('='*60)
if positions:
    for pos in positions:
        print(f"Symbol: {pos.symbol}")
        print(f"  Qty: {pos.qty}")
        print(f"  Market Value: ${float(pos.market_value):,.2f}")
        print(f"  Avg Entry: ${float(pos.avg_entry_price):,.2f}")
        print(f"  Current: ${float(pos.current_price):,.2f}")
        pnl = float(pos.unrealized_pl)
        print(f"  P&L: ${pnl:,.2f} ({float(pos.unrealized_plpc)*100:+.1f}%)")
        print()
else:
    print('No open positions')

print('='*60)
print('RECENT ORDERS (Last 10)')
print('='*60)
if orders:
    for order in orders[:10]:
        print(f"{order.symbol} | {order.side.upper()} | {order.qty} | {order.status}")
else:
    print('No recent orders')
