"""
SELF-IMPROVING TRADING STRATEGY MODULE
Adapts execution strategy based on trade observations and outcomes
Machine learning feedback loop for continuous optimization
"""

import json
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SelfImprovingStrategy:
    """
    Self-learning trading strategy that adapts based on trade outcomes
    Tracks performance and optimizes parameters dynamically
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Data storage
        self.trade_history_file = "trade_outcomes.json"
        self.strategy_params_file = "strategy_params.json"
        self.performance_metrics_file = "performance_metrics.json"
        
        # Strategy components to optimize
        self.components = {
            'entry_timing': {'weight': 0.25, 'performance': []},
            'position_sizing': {'weight': 0.20, 'performance': []},
            'stop_loss': {'weight': 0.25, 'performance': []},
            'take_profit': {'weight': 0.20, 'performance': []},
            'selection_criteria': {'weight': 0.10, 'performance': []}
        }
        
        # Adaptive parameters
        self.params = self._load_params()
        
        # Performance tracking
        self.trade_outcomes = self._load_trade_history()
        self.session_stats = {
            'trades_today': 0,
            'wins_today': 0,
            'losses_today': 0,
            'current_streak': 0,
            'best_streak': 0,
            'worst_streak': 0
        }
        
        # Market regime detection
        self.current_regime = 'neutral'
        self.regime_history = []
        
        self._initialize_default_params()
    
    def _load_params(self) -> Dict:
        """Load strategy parameters from file"""
        if os.path.exists(self.strategy_params_file):
            try:
                with open(self.strategy_params_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _save_params(self):
        """Save strategy parameters to file"""
        try:
            with open(self.strategy_params_file, 'w') as f:
                json.dump(self.params, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving params: {e}")
    
    def _load_trade_history(self) -> List[Dict]:
        """Load trade history from file"""
        if os.path.exists(self.trade_history_file):
            try:
                with open(self.trade_history_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def _save_trade_history(self):
        """Save trade history to file"""
        try:
            with open(self.trade_history_file, 'w') as f:
                json.dump(self.trade_outcomes, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving trade history: {e}")
    
    def _initialize_default_params(self):
        """Initialize default adaptive parameters"""
        defaults = {
            # Entry timing optimization
            'entry_delay_minutes': 5,  # Delay before entry after signal
            'entry_confirmation_bars': 2,  # Bars to confirm trend
            'momentum_threshold': 0.03,  # Min momentum for entry
            
            # Position sizing optimization
            'base_position_pct': 0.25,  # Base 25% allocation
            'confidence_multiplier': 0.05,  # +/- 5% based on confidence
            'consecutive_loss_reduction': 0.10,  # Reduce 10% after each loss
            'win_streak_increase': 0.05,  # Increase 5% per win streak
            
            # Stop loss optimization
            'base_stop_loss_pct': 0.10,  # Base 10% SL
            'volatility_adjustment': True,  # Adjust SL based on volatility
            'sl_tightening_after_loss': 0.02,  # Tighten 2% after loss
            'max_sl_pct': 0.15,  # Max 15% SL
            'min_sl_pct': 0.05,  # Min 5% SL
            
            # Take profit optimization
            'base_take_profit_pct': 0.08,  # Base 8% TP
            'rr_ratio_target': 1.5,  # Min R/R ratio
            'tp_extension_on_momentum': True,  # Extend TP if strong momentum
            'max_tp_pct': 0.20,  # Max 20% TP
            
            # Selection criteria weights
            'momentum_weight': 0.35,
            'volume_weight': 0.25,
            'trend_weight': 0.25,
            'sector_weight': 0.15,
            
            # Time-based adjustments
            'pre_market_boost': 0.02,  # 2% boost for pre-market setups
            'lunch_reduction': 0.10,  # 10% reduction during lunch
            'power_hour_boost': 0.03,  # 3% boost during power hour
            
            # Risk management
            'daily_loss_limit_pct': 0.03,
            'consecutive_loss_limit': 3,
            'drawdown_pause_threshold': 0.05
        }
        
        # Merge with existing params
        for key, value in defaults.items():
            if key not in self.params:
                self.params[key] = value
        
        self._save_params()
    
    def record_trade_outcome(self, trade_data: Dict):
        """
        Record trade outcome for learning
        trade_data: {
            'symbol', 'entry_price', 'exit_price', 'pnl', 'pnl_pct',
            'entry_time', 'exit_time', 'strategy', 'regime',
            'stop_loss', 'take_profit', 'max_drawdown', 'exit_reason'
        }
        """
        try:
            # Add metadata
            trade_data['recorded_at'] = datetime.now().isoformat()
            trade_data['regime'] = self.current_regime
            trade_data['params_snapshot'] = self.params.copy()
            
            # Calculate outcome metrics
            trade_data['was_win'] = trade_data['pnl'] > 0
            trade_data['holding_minutes'] = (
                datetime.fromisoformat(trade_data['exit_time']) - 
                datetime.fromisoformat(trade_data['entry_time'])
            ).total_seconds() / 60
            
            # Add to history
            self.trade_outcomes.append(trade_data)
            self._save_trade_history()
            
            # Update session stats
            self._update_session_stats(trade_data)
            
            # Analyze and adapt
            self._analyze_and_adapt()
            
            logger.info(f"Trade recorded: {trade_data['symbol']} {trade_data['pnl_pct']:+.2%}")
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")
    
    def _update_session_stats(self, trade: Dict):
        """Update daily session statistics"""
        self.session_stats['trades_today'] += 1
        
        if trade['was_win']:
            self.session_stats['wins_today'] += 1
            self.session_stats['current_streak'] = max(0, self.session_stats['current_streak']) + 1
            self.session_stats['best_streak'] = max(
                self.session_stats['best_streak'], 
                self.session_stats['current_streak']
            )
        else:
            self.session_stats['losses_today'] += 1
            self.session_stats['current_streak'] = min(0, self.session_stats['current_streak']) - 1
            self.session_stats['worst_streak'] = min(
                self.session_stats['worst_streak'], 
                self.session_stats['current_streak']
            )
    
    def _analyze_and_adapt(self):
        """Analyze recent trades and adapt strategy parameters"""
        if len(self.trade_outcomes) < 5:
            return  # Not enough data
        
        # Get recent trades (last 20 or all if less)
        recent_trades = self.trade_outcomes[-20:]
        wins = [t for t in recent_trades if t['was_win']]
        losses = [t for t in recent_trades if not t['was_win']]
        
        if not wins and not losses:
            return
        
        win_rate = len(wins) / len(recent_trades) if recent_trades else 0
        
        # Calculate average PnL
        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl_pct'] for t in losses]) if losses else 0
        
        logger.info(f"Analysis: Win rate {win_rate:.1%}, Avg win {avg_win:+.2%}, Avg loss {avg_loss:+.2%}")
        
        # Adapt parameters based on performance
        self._adapt_entry_timing(recent_trades)
        self._adapt_position_sizing(win_rate)
        self._adapt_stop_loss(wins, losses)
        self._adapt_take_profit(wins, losses)
        self._adapt_selection_criteria(recent_trades)
        
        # Save updated params
        self._save_params()
        
        # Log adaptations
        logger.info("Strategy parameters adapted based on performance")
    
    def _adapt_entry_timing(self, trades: List[Dict]):
        """Adapt entry timing based on outcomes"""
        # If early entries are hitting SL, delay more
        early_exits = [t for t in trades if t.get('exit_reason') == 'stop_loss' and t['holding_minutes'] < 30]
        
        if len(early_exits) > len(trades) * 0.4:  # 40% early SL hits
            # Increase delay and confirmation
            self.params['entry_delay_minutes'] = min(15, self.params['entry_delay_minutes'] + 1)
            self.params['entry_confirmation_bars'] = min(5, self.params['entry_confirmation_bars'] + 1)
            logger.info(f"Adapted: Increased entry delay to {self.params['entry_delay_minutes']} min")
        elif len(early_exits) < len(trades) * 0.2:  # Less than 20% early SL
            # Can be more aggressive
            self.params['entry_delay_minutes'] = max(0, self.params['entry_delay_minutes'] - 1)
            logger.info(f"Adapted: Decreased entry delay to {self.params['entry_delay_minutes']} min")
    
    def _adapt_position_sizing(self, win_rate: float):
        """Adapt position sizing based on win rate and streaks"""
        # Reduce size during losing streaks
        if self.session_stats['current_streak'] <= -2:
            reduction = abs(self.session_stats['current_streak']) * self.params['consecutive_loss_reduction']
            self.params['base_position_pct'] = max(0.10, 0.25 - reduction)
            logger.info(f"Adapted: Reduced position size to {self.params['base_position_pct']:.1%} due to streak")
        
        # Increase size during winning streaks (if win rate good)
        elif self.session_stats['current_streak'] >= 3 and win_rate > 0.60:
            increase = min(self.session_stats['current_streak'] * self.params['win_streak_increase'], 0.15)
            self.params['base_position_pct'] = min(0.40, 0.25 + increase)
            logger.info(f"Adapted: Increased position size to {self.params['base_position_pct']:.1%} on hot streak")
        
        # Reset to base if neutral
        elif -1 <= self.session_stats['current_streak'] <= 1:
            self.params['base_position_pct'] = 0.25
    
    def _adapt_stop_loss(self, wins: List[Dict], losses: List[Dict]):
        """Adapt stop loss based on outcomes"""
        # Check if SL is being hit too often before TP
        sl_hits = [t for t in losses if t.get('exit_reason') == 'stop_loss']
        
        if len(sl_hits) > len(losses) * 0.7:  # 70% of losses hit SL
            # Widen SL slightly
            self.params['base_stop_loss_pct'] = min(
                self.params['max_sl_pct'],
                self.params['base_stop_loss_pct'] + self.params['sl_tightening_after_loss']
            )
            logger.info(f"Adapted: Widened SL to {self.params['base_stop_loss_pct']:.1%}")
        elif len(sl_hits) < len(losses) * 0.3:  # Less than 30% hit SL
            # Can tighten SL
            self.params['base_stop_loss_pct'] = max(
                self.params['min_sl_pct'],
                self.params['base_stop_loss_pct'] - 0.01
            )
            logger.info(f"Adapted: Tightened SL to {self.params['base_stop_loss_pct']:.1%}")
    
    def _adapt_take_profit(self, wins: List[Dict], losses: List[Dict]):
        """Adapt take profit based on outcomes"""
        # Check if TP is being hit often and early (might be too tight)
        early_tp = [t for t in wins if t['holding_minutes'] < 60]
        
        if len(early_tp) > len(wins) * 0.6:  # 60% hit TP early
            # Extend TP to capture more profit
            self.params['base_take_profit_pct'] = min(
                self.params['max_tp_pct'],
                self.params['base_take_profit_pct'] + 0.02
            )
            logger.info(f"Adapted: Extended TP to {self.params['base_take_profit_pct']:.1%}")
        
        # Check R/R ratio
        avg_win = np.mean([t['pnl_pct'] for t in wins]) if wins else 0
        avg_loss_abs = abs(np.mean([t['pnl_pct'] for t in losses])) if losses else 0.10
        
        if avg_loss_abs > 0:
            current_rr = avg_win / avg_loss_abs
            if current_rr < self.params['rr_ratio_target']:
                # Need better R/R, either tighten SL or extend TP
                if self.params['base_stop_loss_pct'] > self.params['min_sl_pct']:
                    self.params['base_stop_loss_pct'] -= 0.01
                    logger.info(f"Adapted: Tightened SL for better R/R ratio")
    
    def _adapt_selection_criteria(self, trades: List[Dict]):
        """Adapt stock selection criteria based on outcomes"""
        # Analyze which factors led to wins vs losses
        # This would require more detailed trade data
        pass
    
    def detect_market_regime(self, market_data: Dict):
        """
        Detect current market regime for context-aware trading
        regimes: 'bullish', 'bearish', 'volatile', 'ranging', 'neutral'
        """
        try:
            vix = market_data.get('vix', 20)
            spy_change = market_data.get('spy_change_pct', 0)
            volume = market_data.get('volume_ratio', 1.0)
            
            # Simple regime detection
            if vix > 25 or abs(spy_change) > 2:
                regime = 'volatile'
            elif spy_change > 1 and volume > 1.5:
                regime = 'bullish'
            elif spy_change < -1 and volume > 1.5:
                regime = 'bearish'
            elif abs(spy_change) < 0.5:
                regime = 'ranging'
            else:
                regime = 'neutral'
            
            self.current_regime = regime
            self.regime_history.append({
                'time': datetime.now().isoformat(),
                'regime': regime,
                'vix': vix,
                'spy_change': spy_change
            })
            
            # Keep only last 100 regimes
            self.regime_history = self.regime_history[-100:]
            
            # Adapt parameters for regime
            self._adapt_for_regime(regime)
            
            return regime
            
        except Exception as e:
            logger.error(f"Error detecting regime: {e}")
            return 'neutral'
    
    def _adapt_for_regime(self, regime: str):
        """Adapt parameters for current market regime"""
        if regime == 'volatile':
            # Widen stops, reduce size
            self.params['base_stop_loss_pct'] = min(self.params['max_sl_pct'], 0.12)
            self.params['base_position_pct'] = max(0.15, self.params['base_position_pct'] - 0.05)
            logger.info(f"Regime adaptation: Volatile - Wider SL, smaller size")
            
        elif regime == 'bullish':
            # Normal aggressive settings
            self.params['base_stop_loss_pct'] = 0.10
            self.params['base_take_profit_pct'] = 0.10
            logger.info(f"Regime adaptation: Bullish - Normal aggressive settings")
            
        elif regime == 'bearish':
            # Tighter stops, focus on shorts
            self.params['base_stop_loss_pct'] = 0.08
            self.params['base_take_profit_pct'] = 0.06
            logger.info(f"Regime adaptation: Bearish - Tighter risk management")
            
        elif regime == 'ranging':
            # Tighter stops for scalping
            self.params['base_stop_loss_pct'] = 0.06
            self.params['base_take_profit_pct'] = 0.05
            logger.info(f"Regime adaptation: Ranging - Scalping mode")
    
    def get_optimized_parameters(self, symbol: str = None, 
                                  confidence: float = 0.5,
                                  time_of_day: str = None) -> Dict:
        """
        Get optimized parameters for next trade
        Returns adapted parameters based on current conditions
        """
        params = self.params.copy()
        
        # Adjust for time of day
        if time_of_day:
            if time_of_day == 'pre_market':
                params['momentum_threshold'] += params['pre_market_boost']
            elif time_of_day == 'lunch':
                params['base_position_pct'] *= (1 - params['lunch_reduction'])
            elif time_of_day == 'power_hour':
                params['momentum_threshold'] += params['power_hour_boost']
        
        # Adjust for confidence level
        params['base_position_pct'] += (confidence - 0.5) * params['confidence_multiplier']
        params['base_position_pct'] = max(0.10, min(0.50, params['base_position_pct']))
        
        # Apply session adjustments
        if self.session_stats['current_streak'] <= -2:
            # Defensive mode
            params['base_position_pct'] *= 0.7
            params['base_stop_loss_pct'] *= 0.8
            
        elif self.session_stats['current_streak'] >= 3:
            # Aggressive mode
            params['base_take_profit_pct'] *= 1.2
        
        return params
    
    def get_strategy_report(self) -> Dict:
        """Generate strategy performance report"""
        if not self.trade_outcomes:
            return {
                'total_trades_recorded': 0,
                'recent_win_rate': 0,
                'recent_avg_return': 0,
                'current_streak': self.session_stats['current_streak'],
                'best_streak': self.session_stats['best_streak'],
                'worst_streak': self.session_stats['worst_streak'],
                'current_regime': self.current_regime,
                'component_scores': {},
                'current_params': self.params,
                'adaptations_made': len(self.regime_history)
            }
        
        recent = self.trade_outcomes[-20:]
        wins = [t for t in recent if t['was_win']]
        
        win_rate = len(wins) / len(recent) if recent else 0
        avg_return = np.mean([t['pnl_pct'] for t in recent]) if recent else 0
        
        # Component performance
        component_scores = {}
        for component, data in self.components.items():
            if data['performance']:
                component_scores[component] = np.mean(data['performance'])
        
        return {
            'total_trades_recorded': len(self.trade_outcomes),
            'recent_win_rate': win_rate,
            'recent_avg_return': avg_return,
            'current_streak': self.session_stats['current_streak'],
            'best_streak': self.session_stats['best_streak'],
            'worst_streak': self.session_stats['worst_streak'],
            'current_regime': self.current_regime,
            'component_scores': component_scores,
            'current_params': self.params,
            'adaptations_made': len(self.regime_history)
        }
    
    def should_pause_trading(self) -> Tuple[bool, str]:
        """Determine if trading should be paused based on performance"""
        # Pause on excessive losses
        if self.session_stats['losses_today'] >= self.params['consecutive_loss_limit']:
            return True, f"Paused: {self.params['consecutive_loss_limit']} consecutive losses"
        
        # Check daily loss limit
        daily_pnl = sum([t['pnl'] for t in self.trade_outcomes 
                        if datetime.fromisoformat(t['recorded_at']).date() == datetime.now().date()])
        account_value = 100000  # Placeholder, should get from API
        daily_loss_pct = abs(daily_pnl) / account_value if account_value > 0 else 0
        
        if daily_loss_pct >= self.params['daily_loss_limit_pct']:
            return True, f"Paused: Daily loss limit hit ({daily_loss_pct:.1%})"
        
        # Pause on extended losing streak
        if self.session_stats['current_streak'] <= -5:
            return True, "Paused: Extended losing streak"
        
        return False, "Trading allowed"


# Integration functions for main trader
def create_self_improving_strategy(config):
    """Factory function to create self-improving strategy instance"""
    return SelfImprovingStrategy(config)


if __name__ == "__main__":
    # Test self-improving strategy
    from config import config
    
    strategy = SelfImprovingStrategy(config)
    
    print("SELF-IMPROVING STRATEGY MODULE TEST")
    print("=" * 60)
    
    # Simulate some trades
    test_trades = [
        {'symbol': 'AAPL', 'pnl': 500, 'pnl_pct': 0.08, 'was_win': True, 
         'exit_reason': 'take_profit', 'holding_minutes': 45},
        {'symbol': 'TSLA', 'pnl': -300, 'pnl_pct': -0.10, 'was_win': False,
         'exit_reason': 'stop_loss', 'holding_minutes': 20},
        {'symbol': 'NVDA', 'pnl': 800, 'pnl_pct': 0.12, 'was_win': True,
         'exit_reason': 'take_profit', 'holding_minutes': 60},
    ]
    
    for i, trade in enumerate(test_trades):
        trade['entry_time'] = (datetime.now() - timedelta(hours=2-i)).isoformat()
        trade['exit_time'] = datetime.now().isoformat()
        strategy.record_trade_outcome(trade)
    
    # Get report
    report = strategy.get_strategy_report()
    print(f"\nTotal trades: {report['total_trades_recorded']}")
    print(f"Recent win rate: {report['recent_win_rate']:.1%}")
    print(f"Current streak: {report['current_streak']}")
    print(f"\nOptimized params:")
    print(f"  Position size: {report['current_params']['base_position_pct']:.1%}")
    print(f"  Stop loss: {report['current_params']['base_stop_loss_pct']:.1%}")
    print(f"  Take profit: {report['current_params']['base_take_profit_pct']:.1%}")
    
    # Check if should pause
    should_pause, reason = strategy.should_pause_trading()
    print(f"\nTrading status: {reason}")
