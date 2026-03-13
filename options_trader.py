"""
OPTIONS TRADER MODULE - 80% Probability Strategies
Executes options trades automatically with:
- 80% probability threshold (lower than scanner's 90%)
- 10% portfolio allocation
- 25% stop loss / 50% take profit
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional, Tuple
import json
import os

logger = logging.getLogger(__name__)

class OptionsTrader:
    """
    Execute options trades with 80% probability
    Portfolio allocation: 10% max
    Risk: 25% SL / 50% TP
    """
    
    def __init__(self, config):
        self.config = config
        self.min_probability = 0.80  # 80% threshold (lower than scanner's 90%)
        self.max_portfolio_allocation = 0.10  # 10% of total portfolio
        self.stop_loss_pct = 0.25  # 25% stop loss
        self.take_profit_pct = 0.50  # 50% take profit
        
        # Position tracking
        self.options_positions = {}  # symbol -> position details
        self.positions_file = "options_positions.json"
        self.load_positions()
        
        self.logger = logging.getLogger(__name__)
    
    def load_positions(self):
        """Load saved options positions"""
        if os.path.exists(self.positions_file):
            try:
                with open(self.positions_file, 'r') as f:
                    self.options_positions = json.load(f)
                self.logger.info(f"Loaded {len(self.options_positions)} options positions")
            except:
                self.options_positions = {}
    
    def save_positions(self):
        """Save options positions to file"""
        try:
            with open(self.positions_file, 'w') as f:
                json.dump(self.options_positions, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving positions: {e}")
    
    def get_options_allocation(self, portfolio_value: float) -> float:
        """Calculate available options allocation (10% max)"""
        max_allocation = portfolio_value * self.max_portfolio_allocation
        
        # Calculate current options exposure
        current_exposure = sum(
            pos.get('premium_paid', 0) * pos.get('contracts', 0) * 100
            for pos in self.options_positions.values()
        )
        
        available = max_allocation - current_exposure
        return max(0, available)
    
    def scan_for_options_opportunities(self, symbols: List[str]) -> List[Dict]:
        """Scan for 90%+ probability options opportunities (used by OptionsAlertSystem)"""
        all_opportunities = self.scan_for_80_percent_opportunities(symbols)
        return [opp for opp in all_opportunities if opp.get('probability', 0) >= 0.90]

    def scan_for_80_percent_opportunities(self, symbols: List[str]) -> List[Dict]:
        """Scan for 80%+ probability options opportunities"""
        opportunities = []
        
        self.logger.info("OPTIONS TRADER SCAN - 80% Probability Threshold")
        self.logger.info("=" * 60)
        
        for symbol in symbols:
            try:
                data = self._get_options_data(symbol)
                if not data:
                    continue
                
                # Find best 80%+ strategy
                opp = self._find_best_strategy(symbol, data)
                
                if opp and opp['probability'] >= self.min_probability:
                    opportunities.append(opp)
                    self.logger.info(f"80%+ Setup: {symbol} - {opp['strategy']} - {opp['probability']*100:.1f}%")
                
            except Exception as e:
                self.logger.error(f"Error scanning {symbol}: {e}")
        
        return opportunities
    
    def _get_options_data(self, symbol: str) -> Optional[Dict]:
        """Get options data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Get stock data
            stock_info = ticker.history(period='2d')
            if len(stock_info) < 2:
                return None
            
            current_price = stock_info['Close'].iloc[-1]
            prev_price = stock_info['Close'].iloc[-2]
            change_pct = ((current_price - prev_price) / prev_price) * 100
            
            # Get options chain
            options = ticker.option_chain()
            
            if options.calls.empty or options.puts.empty:
                return None
            
            # Estimate IV
            iv_estimate = self._estimate_iv(options, current_price)
            
            return {
                'symbol': symbol,
                'price': current_price,
                'change_pct': change_pct,
                'volume': stock_info['Volume'].iloc[-1],
                'iv_percentile': iv_estimate,
                'calls': options.calls,
                'puts': options.puts,
                'expiration_dates': ticker.options
            }
            
        except Exception as e:
            self.logger.error(f"Error getting data for {symbol}: {e}")
            return None
    
    def _estimate_iv(self, options, current_price: float) -> float:
        """Estimate IV percentile from option prices"""
        try:
            atm_call = options.calls.iloc[(options.calls['strike'] - current_price).abs().argmin()]
            atm_put = options.puts.iloc[(options.puts['strike'] - current_price).abs().argmin()]
            
            avg_premium = (atm_call['lastPrice'] + atm_put['lastPrice']) / 2
            
            if avg_premium > current_price * 0.15:
                return 80
            elif avg_premium > current_price * 0.10:
                return 70
            elif avg_premium > current_price * 0.05:
                return 60
            else:
                return 50
        except:
            return 60
    
    def _find_best_strategy(self, symbol: str, data: Dict) -> Optional[Dict]:
        """Find best options strategy for 80% probability"""
        strategies = []
        
        # Try different strategies
        for strategy_type in ['CALL_CREDIT_SPREAD', 'PUT_CREDIT_SPREAD', 'IRON_CONDOR']:
            opp = self._analyze_strategy(symbol, data, strategy_type)
            if opp and opp['probability'] >= self.min_probability:
                strategies.append(opp)
        
        # Return highest probability
        if strategies:
            return max(strategies, key=lambda x: x['probability'])
        
        return None
    
    def _analyze_strategy(self, symbol: str, data: Dict, strategy_type: str) -> Optional[Dict]:
        """Analyze a specific options strategy"""
        try:
            price = data['price']
            calls = data['calls']
            puts = data['puts']
            
            if strategy_type == 'CALL_CREDIT_SPREAD':
                return self._analyze_call_credit_spread(symbol, data, calls, price)
            elif strategy_type == 'PUT_CREDIT_SPREAD':
                return self._analyze_put_credit_spread(symbol, data, puts, price)
            elif strategy_type == 'IRON_CONDOR':
                return self._analyze_iron_condor(symbol, data, calls, puts, price)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error analyzing {strategy_type} for {symbol}: {e}")
            return None
    
    def _analyze_call_credit_spread(self, symbol: str, data: Dict, calls: pd.DataFrame, price: float) -> Optional[Dict]:
        """Analyze call credit spread - Bearish/Neutral strategy"""
        try:
            # Find OTM calls (sell closer, buy further)
            otm_calls = calls[calls['strike'] > price * 1.02]  # 2%+ OTM
            if len(otm_calls) < 2:
                return None
            
            otm_calls = otm_calls.sort_values('strike')
            sell_strike = otm_calls.iloc[0]['strike']
            buy_strike = otm_calls.iloc[1]['strike']
            
            sell_price = otm_calls.iloc[0]['lastPrice']
            buy_price = otm_calls.iloc[1]['lastPrice']
            
            width = buy_strike - sell_strike
            premium = sell_price - buy_price
            
            if premium <= 0:
                return None
            
            max_profit = premium * 100
            max_loss = (width - premium) * 100
            breakeven = sell_strike + premium
            
            # Calculate probability (80%+ target)
            prob = self._calculate_80_probability(data, 'neutral', 'CALL_CREDIT_SPREAD')
            
            return {
                'symbol': symbol,
                'strategy': 'CALL_CREDIT_SPREAD',
                'direction': 'BEARISH/NEUTRAL',
                'probability': prob,
                'underlying_price': price,
                'short_strike': sell_strike,
                'long_strike': buy_strike,
                'premium': premium,
                'max_profit': round(max_profit, 2),
                'max_loss': round(max_loss, 2),
                'breakeven': round(breakeven, 2),
                'days_to_expiration': 21,
                'expiration': self._get_next_expiration(data['expiration_dates']),
                'iv_percentile': data['iv_percentile'],
                'risk_reward': round(max_profit / max_loss, 2) if max_loss > 0 else 0,
                'contracts': 1  # Will be calculated based on allocation
            }
            
        except Exception as e:
            self.logger.error(f"Error in call credit spread: {e}")
            return None
    
    def _analyze_put_credit_spread(self, symbol: str, data: Dict, puts: pd.DataFrame, price: float) -> Optional[Dict]:
        """Analyze put credit spread - Bullish/Neutral strategy"""
        try:
            # Find OTM puts (sell closer, buy further)
            otm_puts = puts[puts['strike'] < price * 0.98]  # 2%+ OTM
            if len(otm_puts) < 2:
                return None
            
            otm_puts = otm_puts.sort_values('strike', ascending=False)
            sell_strike = otm_puts.iloc[0]['strike']
            buy_strike = otm_puts.iloc[1]['strike']
            
            sell_price = otm_puts.iloc[0]['lastPrice']
            buy_price = otm_puts.iloc[1]['lastPrice']
            
            width = sell_strike - buy_strike
            premium = sell_price - buy_price
            
            if premium <= 0:
                return None
            
            max_profit = premium * 100
            max_loss = (width - premium) * 100
            breakeven = sell_strike - premium
            
            # Calculate probability (80%+ target)
            prob = self._calculate_80_probability(data, 'neutral', 'PUT_CREDIT_SPREAD')
            
            return {
                'symbol': symbol,
                'strategy': 'PUT_CREDIT_SPREAD',
                'direction': 'BULLISH/NEUTRAL',
                'probability': prob,
                'underlying_price': price,
                'short_strike': sell_strike,
                'long_strike': buy_strike,
                'premium': premium,
                'max_profit': round(max_profit, 2),
                'max_loss': round(max_loss, 2),
                'breakeven': round(breakeven, 2),
                'days_to_expiration': 21,
                'expiration': self._get_next_expiration(data['expiration_dates']),
                'iv_percentile': data['iv_percentile'],
                'risk_reward': round(max_profit / max_loss, 2) if max_loss > 0 else 0,
                'contracts': 1
            }
            
        except Exception as e:
            self.logger.error(f"Error in put credit spread: {e}")
            return None
    
    def _analyze_iron_condor(self, symbol: str, data: Dict, calls: pd.DataFrame, puts: pd.DataFrame, price: float) -> Optional[Dict]:
        """Analyze iron condor - Neutral strategy"""
        try:
            # Find OTM strikes
            put_spreads = puts[puts['strike'] < price * 0.97].sort_values('strike', ascending=False)
            call_spreads = calls[calls['strike'] > price * 1.03].sort_values('strike')
            
            if len(put_spreads) < 2 or len(call_spreads) < 2:
                return None
            
            put_sell = put_spreads.iloc[0]['strike']
            put_buy = put_spreads.iloc[1]['strike']
            call_sell = call_spreads.iloc[0]['strike']
            call_buy = call_spreads.iloc[1]['strike']
            
            put_sell_price = put_spreads.iloc[0]['lastPrice']
            put_buy_price = put_spreads.iloc[1]['lastPrice']
            call_sell_price = call_spreads.iloc[0]['lastPrice']
            call_buy_price = call_spreads.iloc[1]['lastPrice']
            
            # Iron condor is two credit spreads
            put_credit = put_sell_price - put_buy_price
            call_credit = call_sell_price - call_buy_price
            net_premium = put_credit + call_credit
            
            if net_premium <= 0:
                return None
            
            max_profit = net_premium * 100
            put_width = put_sell - put_buy
            call_width = call_buy - call_sell
            max_loss = max(put_width, call_width) * 100 - max_profit
            
            breakeven_low = put_sell - net_premium
            breakeven_high = call_sell + net_premium
            
            # Iron condors need high IV for 80% probability
            prob = self._calculate_80_probability(data, 'neutral', 'IRON_CONDOR')
            
            return {
                'symbol': symbol,
                'strategy': 'IRON_CONDOR',
                'direction': 'NEUTRAL',
                'probability': prob,
                'underlying_price': price,
                'put_sell_strike': put_sell,
                'put_buy_strike': put_buy,
                'call_sell_strike': call_sell,
                'call_buy_strike': call_buy,
                'premium': net_premium,
                'max_profit': round(max_profit, 2),
                'max_loss': round(max_loss, 2),
                'breakeven_low': round(breakeven_low, 2),
                'breakeven_high': round(breakeven_high, 2),
                'days_to_expiration': 28,
                'expiration': self._get_next_expiration(data['expiration_dates']),
                'iv_percentile': data['iv_percentile'],
                'risk_reward': round(max_profit / max_loss, 2) if max_loss > 0 else 0,
                'contracts': 1
            }
            
        except Exception as e:
            self.logger.error(f"Error in iron condor: {e}")
            return None
    
    def _calculate_80_probability(self, data: Dict, direction: str, strategy: str) -> float:
        """Calculate 80%+ probability for options trading"""
        prob = 0.60  # Higher base for 80% target
        
        # Trend alignment (35% weight)
        change = data['change_pct']
        if strategy == 'CALL_CREDIT_SPREAD':
            # Profit if stock stays below strikes (bearish/neutral helps)
            if change < -1 or abs(change) < 1:
                prob += 0.20
        elif strategy == 'PUT_CREDIT_SPREAD':
            # Profit if stock stays above strikes (bullish/neutral helps)
            if change > 1 or abs(change) < 1:
                prob += 0.20
        elif strategy == 'IRON_CONDOR':
            # Profit if stock stays in range (neutral preferred)
            if abs(change) < 2:
                prob += 0.25
        
        # IV percentile (25% weight)
        iv = data['iv_percentile']
        if iv > 65:  # High IV good for selling premium
            prob += 0.15
        elif iv > 50:
            prob += 0.10
        
        # Volume confirmation (20% weight)
        if data['volume'] > 1000000:  # High volume
            prob += 0.15
        elif data['volume'] > 500000:
            prob += 0.10
        
        # Time factor (20% weight)
        prob += 0.10
        
        return min(prob, 0.85)  # Cap at 85%
    
    def _get_next_expiration(self, expirations) -> str:
        """Get optimal expiration date (21-35 DTE)"""
        today = datetime.now()
        
        for exp in expirations:
            try:
                exp_date = datetime.strptime(exp, '%Y-%m-%d')
                days_to_exp = (exp_date - today).days
                
                if 21 <= days_to_exp <= 35:
                    return exp
            except:
                continue
        
        return (today + timedelta(days=30)).strftime('%Y-%m-%d')
    
    def execute_options_trade(self, opportunity: Dict, portfolio_value: float) -> bool:
        """Execute an options trade with proper sizing"""
        try:
            available_allocation = self.get_options_allocation(portfolio_value)
            
            if available_allocation <= 0:
                self.logger.warning("No options allocation available")
                return False
            
            # Calculate position size
            max_loss = opportunity['max_loss']
            contracts = min(
                int(available_allocation / max_loss),
                10  # Max 10 contracts per trade
            )
            
            if contracts < 1:
                self.logger.warning(f"Insufficient allocation for {opportunity['symbol']}")
                return False
            
            # Record position
            position = {
                'symbol': opportunity['symbol'],
                'strategy': opportunity['strategy'],
                'direction': opportunity['direction'],
                'probability': opportunity['probability'],
                'contracts': contracts,
                'premium_paid': opportunity['premium'],
                'underlying_price_at_entry': opportunity.get('underlying_price', 0),
                'max_profit': opportunity['max_profit'] * contracts,
                'max_loss': max_loss * contracts,
                'entry_date': datetime.now().isoformat(),
                'expiration': opportunity['expiration'],
                'stop_loss_price': opportunity['premium'] * (1 + self.stop_loss_pct),  # 25% SL
                'take_profit_price': opportunity['premium'] * (1 - self.take_profit_pct),  # 50% TP (credit spread)
                'status': 'OPEN'
            }
            
            self.options_positions[opportunity['symbol']] = position
            self.save_positions()
            
            self.logger.info(f"OPTIONS TRADE EXECUTED: {opportunity['symbol']}")
            self.logger.info(f"  Strategy: {opportunity['strategy']}")
            self.logger.info(f"  Contracts: {contracts}")
            self.logger.info(f"  Max Profit: ${position['max_profit']:.2f}")
            self.logger.info(f"  Max Loss: ${position['max_loss']:.2f}")
            self.logger.info(f"  SL: {self.stop_loss_pct:.0%} | TP: {self.take_profit_pct:.0%}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error executing options trade: {e}")
            return False
    
    def monitor_options_positions(self, portfolio_value: float) -> List[str]:
        """Monitor options positions for SL/TP"""
        actions = []
        
        for symbol, position in list(self.options_positions.items()):
            if position['status'] != 'OPEN':
                continue
            
            try:
                # Check if expired
                exp_date = datetime.fromisoformat(position['expiration'])
                if datetime.now() > exp_date:
                    position['status'] = 'EXPIRED'
                    actions.append(f"{symbol}: Options expired")
                    self.save_positions()
                    continue
                
                # Estimate current spread premium from underlying price movement
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d')
                if hist.empty:
                    continue
                current_price = hist['Close'].iloc[-1]

                entry_price = position.get('underlying_price_at_entry', 0)
                entry_premium = position.get('premium_paid', 0)
                direction = position.get('direction', '')

                if entry_price > 0 and entry_premium > 0:
                    price_move_pct = (current_price - entry_price) / entry_price
                    # Approximate net delta: ~0.20 for OTM credit spread
                    NET_DELTA = 0.20
                    if 'BULLISH' in direction:
                        # Put credit spread: profits when underlying rises
                        spread_change = -NET_DELTA * price_move_pct * entry_price
                    elif 'BEARISH' in direction:
                        # Call credit spread: profits when underlying falls
                        spread_change = NET_DELTA * price_move_pct * entry_price
                    else:
                        # Iron condor: loss proportional to absolute move
                        spread_change = NET_DELTA * abs(price_move_pct) * entry_price
                    estimated_premium = max(0, entry_premium + spread_change)
                    # For credit spreads, profit = entry_premium - current_premium
                    pnl_pct = (entry_premium - estimated_premium) / entry_premium
                else:
                    pnl_pct = 0
                
                if pnl_pct <= -self.stop_loss_pct:
                    position['status'] = 'STOPPED'
                    actions.append(f"{symbol}: Stop loss hit (-25%)")
                    self.save_positions()
                    
                elif pnl_pct >= self.take_profit_pct:
                    position['status'] = 'PROFIT'
                    actions.append(f"{symbol}: Take profit hit (+50%)")
                    self.save_positions()
                
            except Exception as e:
                self.logger.error(f"Error monitoring {symbol}: {e}")
        
        return actions
    
    def get_options_summary(self) -> Dict:
        """Get summary of options positions"""
        open_positions = [p for p in self.options_positions.values() if p['status'] == 'OPEN']
        
        total_exposure = sum(p['max_loss'] for p in open_positions)
        total_potential_profit = sum(p['max_profit'] for p in open_positions)
        
        return {
            'open_positions': len(open_positions),
            'total_exposure': total_exposure,
            'total_potential_profit': total_potential_profit,
            'allocation_used': total_exposure / (self.max_portfolio_allocation * 100000) if open_positions else 0,
            'positions': open_positions
        }


def main():
    """Test options trader"""
    from aggressive_config import config
    
    trader = OptionsTrader(config)
    
    symbols = ['AAPL', 'TSLA', 'NVDA', 'SPY', 'QQQ']
    
    print("80% PROBABILITY OPTIONS TRADER TEST")
    print("=" * 60)
    print(f"Threshold: 80%")
    print(f"Max Allocation: 10% of portfolio")
    print(f"Stop Loss: 25% | Take Profit: 50%")
    print("=" * 60)
    
    # Scan for opportunities
    opportunities = trader.scan_for_80_percent_opportunities(symbols)
    
    print(f"\nFound {len(opportunities)} 80%+ opportunities")
    
    # Display opportunities
    for opp in opportunities:
        print(f"\n{opp['symbol']} - {opp['strategy']}")
        print(f"  Probability: {opp['probability']*100:.1f}%")
        print(f"  Max Profit: ${opp['max_profit']:.2f}")
        print(f"  Max Loss: ${opp['max_loss']:.2f}")
        print(f"  R/R: 1:{opp['risk_reward']:.1f}")
    
    # Summary
    summary = trader.get_options_summary()
    print(f"\nCurrent Options Allocation Used: {summary['allocation_used']:.1%}")


if __name__ == "__main__":
    main()
