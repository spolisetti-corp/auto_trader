import alpaca_trade_api as tradeapi
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
from config import config

class SwingTradingEngine:
    def __init__(self, paper_trading=True):
        self.config = config
        self.paper_trading = paper_trading
        self.logger = logging.getLogger(__name__)
        
        # Initialize Alpaca API
        if paper_trading:
            self.api = tradeapi.REST(
                self.config.APCA_API_KEY_ID,
                self.config.APCA_API_SECRET_KEY,
                base_url='https://paper-api.alpaca.markets'
            )
        else:
            self.api = tradeapi.REST(
                self.config.APCA_API_KEY_ID,
                self.config.APCA_API_SECRET_KEY,
                base_url='https://api.alpaca.markets'
            )
        
        # PDT tracking
        self.daily_trades = 0
        self.five_day_trades = []
        self.max_daily_trades = 3
        self.max_five_day_avg = 3
        
        # Position tracking
        self.positions = {}
        self.swing_stops = {}
        self.swing_targets = {}
        
        # Swing trading parameters
        self.swing_position_size = 0.20  # 20% per position
        self.swing_stop_loss = 0.10  # 10% stop loss
        self.swing_take_profit = 0.20  # 20% take profit
        
    def initialize(self):
        """Initialize the trading engine"""
        try:
            # Test connection
            account = self.api.get_account()
            self.logger.info(f"Connected to Alpaca account: {account.id}")
            self.logger.info(f"Account equity: ${float(account.equity):,.2f}")
            self.logger.info(f"Paper trading: {self.paper_trading}")
            
            # Get current positions
            self._update_positions()
            
            # Load PDT history
            self._load_pdt_history()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize trading engine: {e}")
            return False
    
    def _update_positions(self):
        """Update current positions"""
        try:
            positions = self.api.list_positions()
            self.positions = {}
            
            for pos in positions:
                self.positions[pos.symbol] = {
                    'quantity': int(float(pos.qty)),
                    'entry_price': float(pos.avg_entry_price),
                    'current_price': float(pos.current_price),
                    'unrealized_pnl': float(pos.unrealized_pl),
                    'side': pos.side
                }
            
            self.logger.info(f"Current positions: {len(self.positions)}")
            
        except Exception as e:
            self.logger.error(f"Error updating positions: {e}")
    
    def _load_pdt_history(self):
        """Load PDT trading history"""
        # In production, this would load from database
        # For now, simulate empty history
        today = datetime.now().date()
        for i in range(5):
            date = today - timedelta(days=i)
            self.five_day_trades.append({
                'date': date,
                'trades': 0
            })
    
    def check_pdt_limit(self):
        """Check if we can make more trades (PDT rules) - Respects config.AVOID_PDT"""
        # If AVOID_PDT is disabled in config, skip PDT check
        if not getattr(self.config, 'AVOID_PDT', True):
            return True
            
        # Update today's trade count
        today = datetime.now().date()
        today_trades = next((d['trades'] for d in self.five_day_trades if d['date'] == today), 0)
        
        # Calculate 5-day total
        five_day_total = sum(d['trades'] for d in self.five_day_trades)
        
        # Strict PDT: Block 4th trade in 5-day window
        if five_day_total >= 3:
            self.logger.warning(f"🚫 PDT BLOCK: {five_day_total}/3 trades in 5-day window")
            return False
        
        # Check daily limits
        can_trade = (
            today_trades < self.max_daily_trades and
            five_day_total < 3  # Hard limit at 3 trades
        )
        
        self.logger.info(f"PDT Check - Today: {today_trades}/{self.max_daily_trades}, "
                        f"5-day total: {five_day_total}/3, "
                        f"Can trade: {can_trade}")
        
        return can_trade
    
    def calculate_position_size(self, stock_price, portfolio_value=None):
        """Calculate position size for swing trading"""
        if portfolio_value is None:
            account = self.api.get_account()
            portfolio_value = float(account.equity)
        
        # Swing trading position sizing
        position_value = portfolio_value * self.swing_position_size
        shares = int(position_value / stock_price)
        
        self.logger.info(f"Position sizing: Portfolio ${portfolio_value:,.0f}, "
                        f"Position {self.swing_position_size*100:.0f}% = ${position_value:,.0f}, "
                        f"Shares: {shares}")
        
        return shares
    
    def place_swing_order(self, symbol, quantity, side='buy', extended_hours=False):
        """Place a swing trading order with extended hours support"""
        try:
            # Check PDT limits
            if not self.check_pdt_limit():
                self.logger.warning(f"PDT limit reached, cannot place order for {symbol}")
                return None
            
            # Build order parameters
            order_params = {
                'symbol': symbol,
                'qty': quantity,
                'side': side,
                'type': 'market',
                'time_in_force': 'day',
                'order_class': 'simple'
            }
            
            # Add extended hours support for pre/post market
            if extended_hours:
                order_params['extended_hours'] = True
                self.logger.info(f"Extended hours order for {symbol}")
            
            # Place order
            order = self.api.submit_order(**order_params)
            
            # Update PDT tracking
            self.daily_trades += 1
            today = datetime.now().date()
            for day_data in self.five_day_trades:
                if day_data['date'] == today:
                    day_data['trades'] += 1
                    break
            
            market_session = "EXTENDED" if extended_hours else "REGULAR"
            self.logger.info(f"Order placed ({market_session}): {side} {quantity} shares of {symbol}, Order ID: {order.id}")
            
            return order
            
        except Exception as e:
            self.logger.error(f"Error placing order for {symbol}: {e}")
            return None
    
    def set_swing_stops_and_targets(self, symbol, entry_price):
        """Set swing trading stops and targets"""
        stop_loss_price = entry_price * (1 - self.swing_stop_loss)
        take_profit_price = entry_price * (1 + self.swing_take_profit)
        
        self.swing_stops[symbol] = stop_loss_price
        self.swing_targets[symbol] = take_profit_price
        
        self.logger.info(f"Swing levels for {symbol}: "
                        f"Entry ${entry_price:.2f}, "
                        f"Stop ${stop_loss_price:.2f}, "
                        f"Target ${take_profit_price:.2f}")
    
    def manage_swing_positions(self):
        """Manage existing swing positions"""
        actions = []
        
        for symbol, position in self.positions.items():
            if position['side'] != 'long':
                continue
            
            current_price = position['current_price']
            entry_price = position['entry_price']
            
            # Check if we have stops/targets set
            if symbol not in self.swing_stops:
                self.set_swing_stops_and_targets(symbol, entry_price)
            
            stop_loss = self.swing_stops[symbol]
            take_profit = self.swing_targets[symbol]
            
            # Check stop loss
            if current_price <= stop_loss:
                action = f"Stop loss hit for {symbol} at ${current_price:.2f}"
                self._close_position(symbol, "Stop loss")
                actions.append(action)
                continue
            
            # Check take profit
            if current_price >= take_profit:
                action = f"Take profit hit for {symbol} at ${current_price:.2f}"
                self._close_position(symbol, "Take profit")
                actions.append(action)
                continue
            
            # Update trailing stop (if profitable)
            if current_price > entry_price * 1.1:  # 10% profit
                new_stop = entry_price  # Break-even
                if new_stop > self.swing_stops[symbol]:
                    self.swing_stops[symbol] = new_stop
                    action = f"Trailing stop updated for {symbol} to ${new_stop:.2f}"
                    actions.append(action)
        
        return actions
    
    def _close_position(self, symbol, reason):
        """Close a position"""
        try:
            position = self.positions.get(symbol)
            if not position:
                return
            
            # Place sell order
            order = self.place_swing_order(symbol, position['quantity'], 'sell')
            
            if order:
                # Update PDT tracking for sell
                self.daily_trades += 1
                today = datetime.now().date()
                for day_data in self.five_day_trades:
                    if day_data['date'] == today:
                        day_data['trades'] += 1
                        break
                
                # Remove from tracking
                del self.positions[symbol]
                if symbol in self.swing_stops:
                    del self.swing_stops[symbol]
                if symbol in self.swing_targets:
                    del self.swing_targets[symbol]
                
                self.logger.info(f"Closed {symbol} position: {reason}")
        
        except Exception as e:
            self.logger.error(f"Error closing position {symbol}: {e}")
    
    def execute_swing_trades(self, swing_candidates):
        """Execute swing trading strategy"""
        actions = []
        
        # Manage existing positions
        position_actions = self.manage_swing_positions()
        actions.extend(position_actions)
        
        # Check if we can open new positions
        if not self.check_pdt_limit():
            actions.append("PDT limit reached, no new trades")
            return actions
        
        # Get account info
        account = self.api.get_account()
        portfolio_value = float(account.equity)
        max_positions = 3  # Swing trading limit
        
        # Open new positions
        open_positions = len(self.positions)
        available_slots = max_positions - open_positions
        
        if available_slots <= 0:
            actions.append("Maximum positions reached")
            return actions
        
        # Select top candidates
        for candidate in swing_candidates[:available_slots]:
            symbol = candidate['symbol']
            current_price = candidate['current_price']
            
            # Calculate position size
            shares = self.calculate_position_size(current_price, portfolio_value)
            
            if shares <= 0:
                continue
            
            # Place order
            order = self.place_swing_order(symbol, shares, 'buy')
            
            if order:
                # Set stops and targets
                self.set_swing_stops_and_targets(symbol, current_price)
                
                action = f"Swing trade opened: {symbol} {shares} shares at ${current_price:.2f}"
                actions.append(action)
        
        return actions

def main():
    # Test swing trading engine
    engine = SwingTradingEngine(paper_trading=True)
    
    if engine.initialize():
        print("✅ Swing trading engine initialized")
        
        # Get account info
        account = engine.api.get_account()
        print(f"Account equity: ${float(account.equity):,.2f}")
        print(f"Paper trading: {engine.paper_trading}")
        
        # Check PDT status
        can_trade = engine.check_pdt_limit()
        print(f"Can trade: {can_trade}")
        
        # Test position sizing
        shares = engine.calculate_position_size(50.00, 100000)
        print(f"Position size test: {shares} shares at $50")
        
    else:
        print("❌ Failed to initialize")

if __name__ == "__main__":
    main()
