import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
OPTIONS BACKTEST FOR TODAY (March 13, 2026)
Shows what options strategies would have been suggested
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class OptionsBacktest:
    """
    Backtest options scanner for today
    Shows hypothetical 90%+ probability setups
    """
    
    def __init__(self):
        self.today = datetime(2026, 3, 13)
        self.symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'SPY', 'QQQ', 'IWM', 'AMZN', 'MSFT', 'GOOGL']
        
        # Simulated market data for March 13, 2026 (Friday — elevated IV, quad-witching week)
        self.market_data = {
            'AAPL': {
                'price': 183.20,
                'change_pct': -1.8,
                'volume': 58000000,
                'iv_percentile': 71,
                'trend': 'bearish',
                'support': 180.00,
                'resistance': 188.00,
                'news': 'iPhone demand softening in China'
            },
            'TSLA': {
                'price': 238.45,
                'change_pct': -3.0,
                'volume': 68000000,
                'iv_percentile': 82,
                'trend': 'bearish',
                'support': 232.00,
                'resistance': 248.00,
                'news': 'CEO distraction concerns, Q1 delivery cut'
            },
            'NVDA': {
                'price': 875.60,
                'change_pct': 5.1,
                'volume': 44000000,
                'iv_percentile': 76,
                'trend': 'strong_bullish',
                'support': 840.00,
                'resistance': 900.00,
                'news': 'Blackwell GPU demand surge, Jensen keynote bullish'
            },
            'AMD': {
                'price': 172.30,
                'change_pct': 0.6,
                'volume': 26000000,
                'iv_percentile': 63,
                'trend': 'neutral',
                'support': 165.00,
                'resistance': 180.00,
                'news': 'MI300X data center orders steady'
            },
            'SPY': {
                'price': 592.80,
                'change_pct': -0.9,
                'volume': 82000000,
                'iv_percentile': 61,
                'trend': 'neutral',
                'support': 585.00,
                'resistance': 600.00,
                'news': 'CPI hotter than expected, rate cut hopes fade'
            },
            'QQQ': {
                'price': 508.75,
                'change_pct': -0.4,
                'volume': 55000000,
                'iv_percentile': 64,
                'trend': 'neutral',
                'support': 500.00,
                'resistance': 518.00,
                'news': 'Tech mixed on macro headwinds'
            },
            'IWM': {
                'price': 208.90,
                'change_pct': -2.1,
                'volume': 48000000,
                'iv_percentile': 69,
                'trend': 'bearish',
                'support': 203.00,
                'resistance': 215.00,
                'news': 'Small caps hit hard on rate fears'
            },
            'AMZN': {
                'price': 182.60,
                'change_pct': 1.4,
                'volume': 36000000,
                'iv_percentile': 59,
                'trend': 'bullish',
                'support': 176.00,
                'resistance': 190.00,
                'news': 'AWS re:Invent announcements driving cloud growth'
            },
            'MSFT': {
                'price': 404.10,
                'change_pct': -0.5,
                'volume': 24000000,
                'iv_percentile': 52,
                'trend': 'neutral',
                'support': 396.00,
                'resistance': 415.00,
                'news': 'Copilot enterprise adoption expanding'
            },
            'GOOGL': {
                'price': 169.85,
                'change_pct': -2.2,
                'volume': 32000000,
                'iv_percentile': 67,
                'trend': 'bearish',
                'support': 165.00,
                'resistance': 175.00,
                'news': 'DOJ antitrust ruling pressure, ad revenue miss'
            }
        }
    
    def analyze_for_options(self) -> List[Dict]:
        """Analyze each symbol for options opportunities"""
        opportunities = []
        
        for symbol, data in self.market_data.items():
            opp = self._evaluate_symbol(symbol, data)
            if opp and opp['probability'] >= 0.90:
                opportunities.append(opp)
        
        # Sort by probability
        opportunities.sort(key=lambda x: x['probability'], reverse=True)
        return opportunities
    
    def _evaluate_symbol(self, symbol: str, data: Dict) -> Dict:
        """Evaluate a single symbol for options setup"""
        trend = data['trend']
        price = data['price']
        iv = data['iv_percentile']
        change = data['change_pct']
        
        # Strategy selection based on setup
        if trend == 'strong_bullish' and iv > 60 and change > 3:
            # High momentum + high IV = Credit spread or naked call
            return self._create_bullish_setup(symbol, data, 'CALL_CREDIT_SPREAD')
        
        elif trend == 'bearish' and iv > 60 and change < -2:
            # Bearish momentum + high IV = Put spread
            return self._create_bearish_setup(symbol, data, 'PUT_CREDIT_SPREAD')
        
        elif trend == 'neutral' and iv > 50:
            # Range-bound = Iron condor
            return self._create_neutral_setup(symbol, data, 'IRON_CONDOR')
        
        elif abs(change) > 2 and iv < 50:
            # Directional move with low IV = Debit spread
            if change > 0:
                return self._create_bullish_setup(symbol, data, 'CALL_DEBIT_SPREAD')
            else:
                return self._create_bearish_setup(symbol, data, 'PUT_DEBIT_SPREAD')
        
        return None
    
    def _create_bullish_setup(self, symbol: str, data: Dict, strategy: str) -> Dict:
        """Create bullish options setup with correct strikes"""
        price = data['price']
        iv = data['iv_percentile']
        
        if strategy == 'CALL_DEBIT_SPREAD':
            # Bullish: Buy ATM call (lower strike), sell OTM call (higher strike)
            # Profit if stock goes up past both strikes
            buy_strike = round(price * 1.00, 0)  # ATM
            sell_strike = round(price * 1.05, 0)  # 5% OTM
            width = sell_strike - buy_strike
            premium = round(width * 0.35, 2)  # Pay 35% of width
            max_profit = width - premium
            max_loss = premium
            breakeven = buy_strike + premium
            direction = 'BULLISH'
            
        elif strategy == 'CALL_CREDIT_SPREAD':
            # Actually bearish/neutral: Sell OTM call, buy further OTM call
            # Profit if stock stays below both strikes
            sell_strike = round(price * 1.03, 0)  # 3% OTM
            buy_strike = round(price * 1.08, 0)  # 8% OTM (further)
            width = buy_strike - sell_strike
            premium = round(width * 0.30, 2)  # Collect 30% of width
            max_profit = premium
            max_loss = width - premium
            breakeven = sell_strike + premium
            direction = 'NEUTRAL/BEARISH'
        
        # Calculate probability
        prob = self._calculate_probability(data, 'bullish' if strategy == 'CALL_DEBIT_SPREAD' else 'neutral', strategy)
        
        return {
            'symbol': symbol,
            'strategy': strategy,
            'direction': direction,
            'probability': prob,
            'underlying_price': price,
            'long_strike': buy_strike,
            'short_strike': sell_strike,
            'premium': premium,
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven': round(breakeven, 2),
            'days_to_expiration': 21,
            'expiration': (self.today + timedelta(days=21)).strftime('%Y-%m-%d'),
            'iv_percentile': iv,
            'volume': 150,
            'open_interest': 450,
            'setup_reason': data.get('news', ''),
            'risk_reward': round(max_profit / max_loss, 2) if max_loss > 0 else 0,
            'spread_width': sell_strike - buy_strike if strategy == 'CALL_DEBIT_SPREAD' else buy_strike - sell_strike
        }
    
    def _create_bearish_setup(self, symbol: str, data: Dict, strategy: str) -> Dict:
        """Create bearish options setup with correct strikes"""
        price = data['price']
        iv = data['iv_percentile']
        
        if strategy == 'PUT_DEBIT_SPREAD':
            # Bearish: Buy ATM put (higher strike), sell OTM put (lower strike)
            # Profit if stock goes down past both strikes
            buy_strike = round(price * 1.00, 0)  # ATM
            sell_strike = round(price * 0.95, 0)  # 5% OTM (lower)
            width = buy_strike - sell_strike
            premium = round(width * 0.35, 2)  # Pay 35% of width
            max_profit = width - premium
            max_loss = premium
            breakeven = buy_strike - premium
            direction = 'BEARISH'
            
        elif strategy == 'PUT_CREDIT_SPREAD':
            # Actually bullish/neutral: Sell OTM put, buy further OTM put
            # Profit if stock stays above both strikes
            sell_strike = round(price * 0.97, 0)  # 3% OTM (below price)
            buy_strike = round(price * 0.92, 0)  # 8% OTM (further below)
            width = sell_strike - buy_strike
            premium = round(width * 0.30, 2)  # Collect 30% of width
            max_profit = premium
            max_loss = width - premium
            breakeven = sell_strike - premium
            direction = 'NEUTRAL/BULLISH'
        
        prob = self._calculate_probability(data, 'bearish' if strategy == 'PUT_DEBIT_SPREAD' else 'neutral', strategy)
        
        return {
            'symbol': symbol,
            'strategy': strategy,
            'direction': direction,
            'probability': prob,
            'underlying_price': price,
            'long_strike': buy_strike,
            'short_strike': sell_strike,
            'premium': premium,
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven': round(breakeven, 2),
            'days_to_expiration': 21,
            'expiration': (self.today + timedelta(days=21)).strftime('%Y-%m-%d'),
            'iv_percentile': iv,
            'volume': 120,
            'open_interest': 380,
            'setup_reason': data.get('news', ''),
            'risk_reward': round(max_profit / max_loss, 2) if max_loss > 0 else 0,
            'spread_width': buy_strike - sell_strike
        }
    
    def _create_neutral_setup(self, symbol: str, data: Dict, strategy: str) -> Dict:
        """Create neutral options setup (Iron Condor)"""
        price = data['price']
        iv = data['iv_percentile']
        
        # Iron condor strikes
        put_sell = round(price * 0.93, 1)
        put_buy = round(price * 0.88, 1)
        call_sell = round(price * 1.07, 1)
        call_buy = round(price * 1.12, 1)
        
        put_width = put_sell - put_buy
        call_width = call_buy - call_sell
        
        premium = round((put_width + call_width) * 0.30, 2)
        max_profit = premium
        max_loss = max(put_width, call_width) - premium
        
        prob = self._calculate_probability(data, 'neutral', strategy)
        
        return {
            'symbol': symbol,
            'strategy': strategy,
            'direction': 'NEUTRAL',
            'probability': prob,
            'underlying_price': price,
            'put_sell_strike': put_sell,
            'put_buy_strike': put_buy,
            'call_sell_strike': call_sell,
            'call_buy_strike': call_buy,
            'premium': premium,
            'max_profit': round(max_profit, 2),
            'max_loss': round(max_loss, 2),
            'breakeven_low': round(put_sell - premium, 2),
            'breakeven_high': round(call_sell + premium, 2),
            'days_to_expiration': 28,
            'expiration': (self.today + timedelta(days=28)).strftime('%Y-%m-%d'),
            'iv_percentile': iv,
            'volume': 85,
            'open_interest': 220,
            'setup_reason': data.get('news', ''),
            'risk_reward': round(max_profit / max_loss, 2) if max_loss > 0 else 0,
            'spread_width': f"Put:{put_width:.1f}/Call:{call_width:.1f}"
        }
    
    def _calculate_probability(self, data: Dict, direction: str, strategy: str) -> float:
        """Calculate probability of profit"""
        prob = 0.50  # Base
        trend = data['trend']
        
        # For credit spreads, trend alignment is different
        if strategy in ['CALL_CREDIT_SPREAD', 'PUT_CREDIT_SPREAD']:
            # Credit spreads profit from neutrality or slight movement away from strikes
            if strategy == 'CALL_CREDIT_SPREAD':
                # Profit if stock stays below strikes (bearish/neutral bias)
                if trend in ['bearish', 'neutral', 'strong_bullish']:
                    prob += 0.20  # Strong bullish helps because we want it to stay below high strikes
            elif strategy == 'PUT_CREDIT_SPREAD':
                # Profit if stock stays above strikes (bullish/neutral bias)
                if trend in ['bullish', 'neutral', 'strong_bullish']:
                    prob += 0.20
        else:
            # Debit spreads need directional alignment
            if direction == 'bullish' and trend in ['bullish', 'strong_bullish']:
                prob += 0.25
            elif direction == 'bearish' and trend == 'bearish':
                prob += 0.25
            elif direction == 'neutral' and trend == 'neutral':
                prob += 0.25
        
        # IV percentile (30%)
        iv = data['iv_percentile']
        if strategy in ['CALL_CREDIT_SPREAD', 'PUT_CREDIT_SPREAD', 'IRON_CONDOR']:
            # Selling premium - want high IV
            if iv > 70:
                prob += 0.20
            elif iv > 60:
                prob += 0.15
            elif iv > 50:
                prob += 0.10
        else:
            # Buying premium - want low IV
            if iv < 40:
                prob += 0.15
            elif iv < 50:
                prob += 0.10
        
        # Momentum confirmation (20%)
        change = abs(data['change_pct'])
        if change > 3:
            prob += 0.15
        elif change > 2:
            prob += 0.10
        
        # Time factor (10%)
        prob += 0.05
        
        return min(prob, 0.98)
    
    def generate_report(self, opportunities: List[Dict]):
        """Generate backtest report"""
        print("\n" + "=" * 80)
        print(f"📊 OPTIONS BACKTEST: {self.today.strftime('%B %d, %Y')}")
        print("=" * 80)
        print("\n🎯 HIGH PROBABILITY OPTIONS SETUPS (90%+):")
        print("-" * 80)
        
        if not opportunities:
            print("\nNo 90%+ probability setups found for today.")
            print("Market conditions not favorable for high-confidence options plays.")
            return
        
        for i, opp in enumerate(opportunities, 1):
            print(f"\n{i}. 🎰 {opp['symbol']} - {opp['strategy']}")
            print(f"   Direction: {opp['direction']}")
            print(f"   Probability: {opp['probability']*100:.1f}% ⭐")
            print(f"   Underlying: ${opp['underlying_price']:.2f}")
            print(f"   Strategy Details:")
            
            if 'CALL' in opp['strategy']:
                if 'DEBIT' in opp['strategy']:
                    print(f"      Long Call (Buy):  ${opp['long_strike']}")
                    print(f"      Short Call (Sell): ${opp['short_strike']}")
                else:  # CREDIT
                    print(f"      Short Call (Sell): ${opp['short_strike']}")
                    print(f"      Long Call (Buy):  ${opp['long_strike']}")
            elif 'PUT' in opp['strategy']:
                if 'DEBIT' in opp['strategy']:
                    print(f"      Long Put (Buy):   ${opp['long_strike']}")
                    print(f"      Short Put (Sell): ${opp['short_strike']}")
                else:  # CREDIT
                    print(f"      Short Put (Sell): ${opp['short_strike']}")
                    print(f"      Long Put (Buy):   ${opp['long_strike']}")
            else:  # NEUTRAL
                print(f"      Put Spread: ${opp['put_sell_strike']} / ${opp['put_buy_strike']}")
                print(f"      Call Spread: ${opp['call_sell_strike']} / ${opp['call_buy_strike']}")
            
            print(f"   Spread Width: ${opp['spread_width']}")
            print(f"   Premium: ${opp['premium']}")
            print(f"   Max Profit: ${opp['max_profit']:.2f}")
            print(f"   Max Loss: ${opp['max_loss']:.2f}")
            print(f"   R/R Ratio: 1:{opp['risk_reward']:.1f}")
            if 'breakeven' in opp:
                print(f"   Breakeven: ${opp['breakeven']}")
            elif 'breakeven_low' in opp and 'breakeven_high' in opp:
                print(f"   Breakeven Range: ${opp['breakeven_low']} - ${opp['breakeven_high']}")
            print(f"   Expiration: {opp['expiration']} ({opp['days_to_expiration']} DTE)")
            print(f"   IV Percentile: {opp['iv_percentile']}%")
            print(f"   Setup Reason: {opp['setup_reason']}")
        
        print("\n" + "=" * 80)
        print("📈 SUMMARY:")
        print(f"   Total Setups: {len(opportunities)}")
        print(f"   Bullish: {len([o for o in opportunities if o['direction'] == 'BULLISH'])}")
        print(f"   Bearish: {len([o for o in opportunities if o['direction'] == 'BEARISH'])}")
        print(f"   Neutral: {len([o for o in opportunities if o['direction'] == 'NEUTRAL'])}")
        
        avg_prob = sum(o['probability'] for o in opportunities) / len(opportunities)
        print(f"   Avg Probability: {avg_prob*100:.1f}%")
        
        print("\n⚠️  DISCLAIMER:")
        print("   These are hypothetical setups based on simulated market data.")
        print("   Past performance does not guarantee future results.")
        print("   Always do your own research before trading options.")
        print("=" * 80)


def main():
    backtest = OptionsBacktest()
    opportunities = backtest.analyze_for_options()
    backtest.generate_report(opportunities)
    
    # Save to file
    with open('options_backtest_today.json', 'w') as f:
        json.dump({
            'date': backtest.today.strftime('%Y-%m-%d'),
            'opportunities': opportunities
        }, f, indent=2)
    
    print("\n✅ Backtest results saved to options_backtest_today.json")


if __name__ == "__main__":
    main()
