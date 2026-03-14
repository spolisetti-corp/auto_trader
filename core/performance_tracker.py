import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging

class AggressivePerformanceTracker:
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Performance tracking
        self.daily_performance = []
        self.weekly_performance = []
        self.monthly_performance = []
        self.quarterly_performance = []
        
        # Risk tracking
        self.daily_losses = []
        self.weekly_losses = []
        self.monthly_losses = []
        
        # Trade tracking
        self.trades = []
        self.current_positions = {}
        
    def track_daily_performance(self, date, portfolio_value, open_positions=0):
        """Track daily performance against targets"""
        # Calculate daily return
        if len(self.daily_performance) > 0:
            prev_value = self.daily_performance[-1]['portfolio_value']
            daily_return = (portfolio_value - prev_value) / prev_value
        else:
            daily_return = 0
        
        # Check if daily loss limit exceeded
        if daily_return < -self.config.MAX_DAILY_LOSS:
            self.logger.warning(f"Daily loss limit exceeded: {daily_return:.2%}")
            return False  # Stop trading for the day
        
        # Record performance
        performance = {
            'date': date,
            'portfolio_value': portfolio_value,
            'daily_return': daily_return,
            'daily_target': self.config.DAILY_TARGET,
            'target_met': daily_return >= self.config.DAILY_TARGET,
            'open_positions': open_positions
        }
        
        self.daily_performance.append(performance)
        
        # Log performance
        status = "TARGET MET" if performance['target_met'] else "TARGET MISSED"
        self.logger.info(f"Daily Performance {date}: {daily_return:+.2%} {status}")
        
        return True
    
    def track_weekly_performance(self, week_start, week_end):
        """Track weekly performance against targets"""
        # Filter daily performance for the week
        week_data = [d for d in self.daily_performance 
                    if week_start <= d['date'] <= week_end]
        
        if len(week_data) < 2:
            return
        
        # Calculate weekly return
        start_value = week_data[0]['portfolio_value']
        end_value = week_data[-1]['portfolio_value']
        weekly_return = (end_value - start_value) / start_value
        
        # Check if weekly loss limit exceeded
        if weekly_return < -self.config.WEEKLY_TARGET:
            self.logger.warning(f"Weekly loss limit exceeded: {weekly_return:.2%}")
            return False
        
        # Record performance
        performance = {
            'week_start': week_start,
            'week_end': week_end,
            'weekly_return': weekly_return,
            'weekly_target': self.config.WEEKLY_TARGET,
            'target_met': weekly_return >= self.config.WEEKLY_TARGET,
            'trades_count': len([t for t in self.trades if week_start <= t['date'] <= week_end])
        }
        
        self.weekly_performance.append(performance)
        
        # Log performance
        status = "✅ TARGET MET" if performance['target_met'] else "❌ TARGET MISSED"
        self.logger.info(f"Weekly Performance {week_start}: {weekly_return:+.2%} {status}")
        
        return True
    
    def track_monthly_performance(self, month_start, month_end):
        """Track monthly performance against targets"""
        # Filter daily performance for the month
        month_data = [d for d in self.daily_performance 
                     if month_start <= d['date'] <= month_end]
        
        if len(month_data) < 2:
            return
        
        # Calculate monthly return
        start_value = month_data[0]['portfolio_value']
        end_value = month_data[-1]['portfolio_value']
        monthly_return = (end_value - start_value) / start_value
        
        # Check if monthly loss limit exceeded
        if monthly_return < -self.config.MONTHLY_MAX_LOSS:
            self.logger.error(f"Monthly loss limit exceeded: {monthly_return:.2%}")
            return False  # Stop trading for the month
        
        # Record performance
        performance = {
            'month_start': month_start,
            'month_end': month_end,
            'monthly_return': monthly_return,
            'monthly_target': self.config.MONTHLY_PROFIT_TARGET,
            'target_met': monthly_return >= self.config.MONTHLY_PROFIT_TARGET,
            'loss_limit_hit': monthly_return < -self.config.MONTHLY_MAX_LOSS,
            'trades_count': len([t for t in self.trades if month_start <= t['date'] <= month_end])
        }
        
        self.monthly_performance.append(performance)
        
        # Log performance
        if performance['loss_limit_hit']:
            status = "🚨 LOSS LIMIT HIT"
        elif performance['target_met']:
            status = "✅ TARGET MET"
        else:
            status = "❌ TARGET MISSED"
        
        self.logger.info(f"Monthly Performance {month_start}: {monthly_return:+.2%} {status}")
        
        return not performance['loss_limit_hit']
    
    def track_quarterly_performance(self, quarter_start, quarter_end):
        """Track quarterly performance against targets"""
        # Filter daily performance for the quarter
        quarter_data = [d for d in self.daily_performance 
                       if quarter_start <= d['date'] <= quarter_end]
        
        if len(quarter_data) < 2:
            return
        
        # Calculate quarterly return
        start_value = quarter_data[0]['portfolio_value']
        end_value = quarter_data[-1]['portfolio_value']
        quarterly_return = (end_value - start_value) / start_value
        
        # Check if quarterly loss limit exceeded
        if quarterly_return < -self.config.QUARTERLY_MAX_LOSS:
            self.logger.error(f"Quarterly loss limit exceeded: {quarterly_return:.2%}")
            return False
        
        # Record performance
        performance = {
            'quarter_start': quarter_start,
            'quarter_end': quarter_end,
            'quarterly_return': quarterly_return,
            'quarterly_target': self.config.QUARTERLY_PROFIT_TARGET,
            'target_met': quarterly_return >= self.config.QUARTERLY_PROFIT_TARGET,
            'loss_limit_hit': quarterly_return < -self.config.QUARTERLY_MAX_LOSS,
            'trades_count': len([t for t in self.trades if quarter_start <= t['date'] <= quarter_end])
        }
        
        self.quarterly_performance.append(performance)
        
        # Log performance
        if performance['loss_limit_hit']:
            status = "🚨 LOSS LIMIT HIT"
        elif performance['target_met']:
            status = "✅ TARGET MET"
        else:
            status = "❌ TARGET MISSED"
        
        self.logger.info(f"Quarterly Performance {quarter_start}: {quarterly_return:+.2%} {status}")
        
        return not performance['loss_limit_hit']
    
    def track_trade(self, trade_data):
        """Track individual trade performance"""
        trade = {
            'date': trade_data['date'],
            'symbol': trade_data['symbol'],
            'action': trade_data['action'],
            'quantity': trade_data['quantity'],
            'entry_price': trade_data['entry_price'],
            'exit_price': trade_data.get('exit_price', 0),
            'pnl': trade_data.get('pnl', 0),
            'pnl_percent': trade_data.get('pnl_percent', 0),
            'holding_days': trade_data.get('holding_days', 0),
            'confidence_level': trade_data.get('confidence_level', 'medium')
        }
        
        self.trades.append(trade)
        
        # Log trade
        action = "PROFIT" if trade['pnl'] > 0 else "LOSS"
        self.logger.info(f"Trade {action} {trade['symbol']}: {trade['pnl_percent']:+.2%}")
        
        return trade
    
    def get_current_quarter_status(self):
        """Get current quarter performance status"""
        if not self.daily_performance:
            return "No data available"
        
        # Calculate current quarter performance
        current_date = datetime.now().date()
        quarter_start = self._get_quarter_start(current_date)
        
        quarter_data = [d for d in self.daily_performance 
                       if d['date'] >= quarter_start]
        
        if len(quarter_data) < 2:
            return "Insufficient data"
        
        start_value = quarter_data[0]['portfolio_value']
        current_value = quarter_data[-1]['portfolio_value']
        current_return = (current_value - start_value) / start_value
        
        # Calculate progress to target
        target = self.config.QUARTERLY_PROFIT_TARGET
        progress = current_return / target
        
        # Determine status
        if current_return <= -self.config.QUARTERLY_MAX_LOSS:
            status = "LOSS LIMIT HIT"
        elif progress >= 1.0:
            status = "TARGET ACHIEVED"
        elif progress >= 0.5:
            status = "ON TRACK"
        else:
            status = "BEHIND TARGET"
        
        return {
            'status': status,
            'current_return': current_return,
            'target_return': target,
            'progress': progress,
            'days_remaining': self._get_days_in_quarter() - len(quarter_data)
        }
    
    def get_risk_assessment(self):
        """Get current risk assessment"""
        if not self.daily_performance:
            return "No data available"
        
        # Calculate recent performance
        recent_days = 5
        recent_data = self.daily_performance[-recent_days:]
        
        if len(recent_data) < 2:
            return "Insufficient data"
        
        # Calculate recent volatility
        returns = [d['daily_return'] for d in recent_data]
        volatility = np.std(returns)
        
        # Calculate max drawdown
        portfolio_values = [d['portfolio_value'] for d in recent_data]
        peak = max(portfolio_values)
        current = portfolio_values[-1]
        drawdown = (current - peak) / peak
        
        # Risk assessment
        risk_level = "LOW"
        if volatility > 0.03 or drawdown < -0.10:
            risk_level = "HIGH"
        elif volatility > 0.02 or drawdown < -0.05:
            risk_level = "MEDIUM"
        
        return {
            'risk_level': risk_level,
            'volatility': volatility,
            'max_drawdown': drawdown,
            'recent_performance': np.mean(returns)
        }
    
    def _get_quarter_start(self, date):
        """Get the start of the quarter for a given date"""
        quarter = (date.month - 1) // 3
        year = date.year
        quarter_start = datetime(year, quarter * 3 + 1, 1).date()
        return quarter_start
    
    def _get_days_in_quarter(self):
        """Get total days in current quarter"""
        current_date = datetime.now().date()
        quarter_start = self._get_quarter_start(current_date)
        
        if current_date.month in [1, 2, 3]:
            quarter_end = datetime(current_date.year, 3, 31).date()
        elif current_date.month in [4, 5, 6]:
            quarter_end = datetime(current_date.year, 6, 30).date()
        elif current_date.month in [7, 8, 9]:
            quarter_end = datetime(current_date.year, 9, 30).date()
        else:
            quarter_end = datetime(current_date.year, 12, 31).date()
        
        return (quarter_end - quarter_start).days
    
    def generate_performance_report(self):
        """Generate comprehensive performance report"""
        report = {
            'quarterly_status': self.get_current_quarter_status(),
            'risk_assessment': self.get_risk_assessment(),
            'recent_trades': self.trades[-10:],  # Last 10 trades
            'daily_performance': self.daily_performance[-7:],  # Last 7 days
            'total_trades': len(self.trades),
            'win_rate': self._calculate_win_rate(),
            'avg_return': self._calculate_avg_return(),
            'sharpe_ratio': self._calculate_sharpe_ratio()
        }
        
        return report
    
    def _calculate_win_rate(self):
        """Calculate win rate"""
        if not self.trades:
            return 0
        
        wins = len([t for t in self.trades if t['pnl'] > 0])
        return wins / len(self.trades)
    
    def _calculate_avg_return(self):
        """Calculate average return"""
        if not self.trades:
            return 0
        
        returns = [t['pnl_percent'] for t in self.trades]
        return np.mean(returns)
    
    def _calculate_sharpe_ratio(self):
        """Calculate Sharpe ratio"""
        if not self.trades:
            return 0
        
        returns = [t['pnl_percent'] for t in self.trades]
        excess_returns = [r - 0.01 for r in returns]  # Assume 1% risk-free rate
        
        if len(excess_returns) < 2:
            return 0
        
        return np.mean(excess_returns) / np.std(excess_returns)

def main():
    # Test aggressive performance tracker
    from config import config
    
    tracker = AggressivePerformanceTracker(config)
    
    # Simulate some performance data
    print("AGGRESSIVE PERFORMANCE TRACKER")
    print("=" * 50)
    
    # Simulate daily performance
    today = datetime.now().date()
    portfolio_value = 100000
    
    for i in range(10):
        date = today - timedelta(days=9-i)
        # Simulate some daily returns
        daily_return = np.random.normal(0.015, 0.02)  # 1.5% target, 2% volatility
        portfolio_value *= (1 + daily_return)
        
        can_continue = tracker.track_daily_performance(date, portfolio_value)
        if not can_continue:
            print("Daily loss limit hit - trading stopped")
            break
    
    # Generate report
    report = tracker.generate_performance_report()
    
    print(f"\nCurrent Quarter Status: {report['quarterly_status']['status']}")
    print(f"Current Return: {report['quarterly_status']['current_return']:+.2%}")
    print(f"Target Return: {report['quarterly_status']['target_return']:+.2%}")
    print(f"Progress: {report['quarterly_status']['progress']:.1%}")
    print(f"Risk Level: {report['risk_assessment']['risk_level']}")
    print(f"Win Rate: {report['win_rate']:.1%}")
    print(f"Avg Return: {report['avg_return']:+.2%}")

if __name__ == "__main__":
    main()
