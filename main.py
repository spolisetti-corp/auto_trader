#!/usr/bin/env python3
"""
AGGRESSIVE SWING TRADING SYSTEM
Target: 75-100% quarterly profit
Risk: 20% maximum quarterly loss
"""

import logging
import schedule
import time
from datetime import datetime, timedelta
from config import config
from core.market_scanner import PolygonMarketScanner
from core.trading_engine import SwingTradingEngine
from core.performance_tracker import AggressivePerformanceTracker
from options.scanner import OptionsAlertSystem
from options.trader import OptionsTrader
from core.adaptive_strategy import SelfImprovingStrategy
from infrastructure.state_manager import TradingStateManager
from infrastructure.error_handler import RobustTradingManager
from infrastructure.alerting import TradingAlertSystem

class AggressiveSwingTrader:
    def __init__(self):
        self.config = config
        self.scanner = PolygonMarketScanner(self.config.POLYGON_API_KEY)
        self.engine = SwingTradingEngine(paper_trading=True)
        self.tracker = AggressivePerformanceTracker(self.config)
        self.logger = self._setup_logging()
        
        self.options_symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'SPY', 'QQQ', 'IWM', 'AMZN', 'MSFT', 'GOOGL']

        # Options TRADER (80% probability, 10% allocation, 25% SL / 50% TP)
        self.options_trader = OptionsTrader(self.config)

        # Options alerter (90%+ probability, alert only - reuses options_trader as scanner)
        self.options_alerter = OptionsAlertSystem(self.options_trader, ['console', 'log'])
        self.options_active = True  # Enable automatic options trading
        
        # SELF-IMPROVING STRATEGY - Adaptive execution based on outcomes
        self.self_improving = SelfImprovingStrategy(self.config)
        self.adaptive_trading = True  # Enable self-improvement
        
        # Trading state
        self.is_trading_allowed = True
        self.daily_trades_count = 0
        self.current_positions = {}

        # Enhancement modules
        self.state_manager = TradingStateManager()
        self.robust_manager = RobustTradingManager()
        self.alert_system = TradingAlertSystem(
            email_config=self.config.ALERT_EMAIL_CONFIG or None,
            webhook_url=self.config.ALERT_WEBHOOK_URL or None,
        )
        # Route circuit-breaker alerts from robust_manager through alert_system
        self.robust_manager.send_alert = lambda msg: self.alert_system.send_circuit_breaker_alert(msg)
        
    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('aggressive_trading.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
    
    def initialize(self):
        """Initialize the aggressive trading system"""
        self.logger.info("AGGRESSIVE SWING TRADING SYSTEM INITIALIZING")
        self.logger.info("=" * 60)
        self.logger.info(f"Quarterly Target: {self.config.QUARTERLY_PROFIT_TARGET:.1%}")
        self.logger.info(f"Quarterly Max Loss: {self.config.QUARTERLY_MAX_LOSS:.1%}")
        self.logger.info(f"Position Size: {self.config.AGGRESSIVE_POSITION_SIZE:.1%}")
        self.logger.info(f"Max Positions: {self.config.MAX_POSITIONS}")
        
        # Initialize components
        if not self.engine.initialize():
            self.logger.error("Failed to initialize trading engine")
            return False
        
        # Check quarterly limits
        quarterly_status = self.tracker.get_current_quarter_status()
        if quarterly_status == "LOSS LIMIT HIT":
            self.logger.error("Quarterly loss limit hit - trading suspended")
            self.is_trading_allowed = False
            return False
        
        # Recover state from a previous session if one exists
        if self.state_manager.load_previous_state():
            recovered = self.state_manager.recover_from_crash(self)
            if recovered:
                self.logger.info("Recovered positions and state from previous session")

        self.logger.info("System initialized successfully")
        return True
    
    def is_extended_hours(self):
        """Check if we're in extended hours (pre or post market)"""
        now = datetime.now()
        weekday = now.weekday()
        current_time = now.time()
        
        if weekday >= 5:  # Weekend
            return False
        
        # Pre-market: 7:00 AM - 9:30 AM
        pre_market_start = datetime.strptime("07:00", "%H:%M").time()
        pre_market_end = datetime.strptime("09:30", "%H:%M").time()
        
        # Post-market: 4:00 PM - 8:00 PM
        post_market_start = datetime.strptime("16:00", "%H:%M").time()
        post_market_end = datetime.strptime("20:00", "%H:%M").time()
        
        is_pre_market = pre_market_start <= current_time < pre_market_end
        is_post_market = post_market_start <= current_time < post_market_end
        
        return is_pre_market or is_post_market

    def is_market_open(self):
        """Check if market is open"""
        try:
            clock = self.engine.api.get_clock()
            is_open = clock.is_open
            self.logger.info(f"Market Status: {'OPEN' if is_open else 'CLOSED'}")
            return is_open
        except:
            # Fallback to time-based check
            now = datetime.now()
            weekday = now.weekday()
            current_time = now.time()

            if weekday >= 5:  # Weekend
                return False

            open_time = datetime.strptime("09:30", "%H:%M").time()
            close_time = datetime.strptime("16:00", "%H:%M").time()

            return open_time <= current_time <= close_time
    
    def _get_market_conditions(self):
        """Fetch real VIX and SPY data for market regime detection"""
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX").history(period="2d")
            spy = yf.Ticker("SPY").history(period="2d")

            vix_value = float(vix['Close'].iloc[-1]) if not vix.empty else 20.0
            if len(spy) >= 2:
                spy_change_pct = float(
                    (spy['Close'].iloc[-1] - spy['Close'].iloc[-2]) / spy['Close'].iloc[-2] * 100
                )
                volume_ratio = float(spy['Volume'].iloc[-1] / spy['Volume'].iloc[-2]) if spy['Volume'].iloc[-2] > 0 else 1.0
            else:
                spy_change_pct = 0.0
                volume_ratio = 1.0

            return {
                'vix': vix_value,
                'spy_change_pct': spy_change_pct,
                'volume_ratio': volume_ratio,
            }
        except Exception as e:
            self.logger.warning(f"Could not fetch market conditions: {e}, using defaults")
            return {'vix': 20.0, 'spy_change_pct': 0.0, 'volume_ratio': 1.0}

    def aggressive_morning_scan(self):
        """Aggressive morning scan and trade execution (pre-market at 7:00 AM)"""
        self.logger.info("PRE-MARKET AGGRESSIVE SCAN (7:00 AM)")
        self.logger.info("=" * 50)
        self.logger.info("Extended hours trading enabled")
        
        if not self.is_trading_allowed:
            self.logger.warning("Trading suspended - limits hit")
            return
        
        def _run():
            candidates = self.scanner.get_swing_candidates()
            self.logger.info(f"Found {len(candidates)} candidates for pre-market")

            aggressive_trades = self.scanner.filter_swing_trades(candidates, max_trades=self.config.MAX_POSITIONS)
            self.logger.info(f"Qualified pre-market trades: {len(aggressive_trades)}")

            if aggressive_trades:
                actions = self.execute_aggressive_trades(aggressive_trades, extended_hours=True)
                for action in actions:
                    self.logger.info(f"Action: {action}")
            else:
                self.logger.info("No qualified pre-market trades")

            self.display_aggressive_positions()

        result = self.robust_manager.execute_with_retry(_run)
        if result is None and self.robust_manager.circuit_breaker:
            if self.config.ENABLE_ERROR_ALERTS:
                self.alert_system.send_error_alert({
                    'type': 'CircuitBreaker',
                    'message': 'Circuit breaker triggered during morning scan',
                    'system_status': 'HALTED',
                })
    
    def execute_aggressive_trades(self, aggressive_trades, extended_hours=False):
        """Execute aggressive swing trades with self-improving adaptive parameters"""
        actions = []
        
        # Check if self-improvement suggests pausing
        if self.adaptive_trading:
            should_pause, reason = self.self_improving.should_pause_trading()
            if should_pause:
                self.logger.warning(f"SELF-IMPROVEMENT: {reason}")
                actions.append(f"Trading paused: {reason}")
                return actions
        
        # Get account info
        account = self.engine.api.get_account()
        portfolio_value = float(account.equity)
        
        # Detect market regime using real market data
        market_data = self._get_market_conditions()
        
        if self.adaptive_trading:
            regime = self.self_improving.detect_market_regime(market_data)
            self.logger.info(f"Market regime: {regime}")
            
            # Get optimized parameters
            time_of_day = 'pre_market' if extended_hours else 'regular'
            params = self.self_improving.get_optimized_parameters(
                confidence=0.7,
                time_of_day=time_of_day
            )
            
            position_size_pct = params['base_position_pct']
            stop_loss_pct = params['base_stop_loss_pct']
            take_profit_pct = params['base_take_profit_pct']
            
            self.logger.info(f"ADAPTIVE PARAMS: Size {position_size_pct:.1%}, SL {stop_loss_pct:.1%}, TP {take_profit_pct:.1%}")
        else:
            # Use default config
            position_size_pct = self.config.SWING_POSITION_SIZE
            stop_loss_pct = self.config.SWING_STOP_LOSS
            take_profit_pct = self.config.SWING_TAKE_PROFIT
        
        self.logger.info(f"Portfolio Value: ${portfolio_value:,.2f}")
        if extended_hours:
            self.logger.info("Extended hours trading active")
        
        # Check daily loss limit
        if self.daily_trades_count >= self.config.MAX_POSITIONS:
            actions.append("Max positions reached")
            return actions
        
        # Execute trades with adaptive sizing
        for trade in aggressive_trades:
            symbol = trade['symbol']
            current_price = trade['current_price']
            
            # Calculate adaptive position size
            position_value = portfolio_value * position_size_pct
            shares = int(position_value / current_price)
            
            if shares <= 0:
                continue
            
            # Place order with extended hours support
            order = self.engine.place_swing_order(symbol, shares, 'buy', extended_hours=extended_hours)
            
            if order:
                # Set adaptive stops and targets
                stop_loss = current_price * (1 - stop_loss_pct)
                take_profit = current_price * (1 + take_profit_pct)
                
                self.engine.swing_stops[symbol] = stop_loss
                self.engine.swing_targets[symbol] = take_profit
                
                # Track trade
                trade_data = {
                    'date': datetime.now().date(),
                    'symbol': symbol,
                    'action': 'buy',
                    'quantity': shares,
                    'entry_price': current_price,
                    'confidence_level': 'high',
                    'extended_hours': extended_hours
                }
                self.tracker.track_trade(trade_data)
                
                session_type = "PRE-MARKET" if extended_hours else "REGULAR"
                action = f"{session_type} TRADE: {symbol} {shares} shares at ${current_price:.2f}"
                action += f" | Stop: ${stop_loss:.2f} | Target: ${take_profit:.2f}"
                actions.append(action)
                
                self.daily_trades_count += 1
                
                # Track position
                self.current_positions[symbol] = {
                    'shares': shares,
                    'entry_price': current_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'entry_time': datetime.now(),
                    'extended_hours': extended_hours
                }

                if self.config.ENABLE_TRADE_ALERTS:
                    self.alert_system.send_trade_alert({
                        'symbol': symbol,
                        'action': 'BUY',
                        'quantity': shares,
                        'price': current_price,
                        'session': 'PRE-MARKET' if extended_hours else 'REGULAR',
                    })
        
        return actions
    
    def aggressive_monitoring(self):
        """Aggressive position monitoring"""
        self.logger.info("AGGRESSIVE MONITORING")
        self.logger.info("=" * 50)
        
        def _run():
            self.engine._update_positions()
            actions = self.manage_aggressive_positions()
            for action in actions:
                self.logger.info(f"Action: {action}")
            self.track_performance()
            self.display_aggressive_positions()

        result = self.robust_manager.execute_with_retry(_run)
        if result is None and self.robust_manager.circuit_breaker:
            if self.config.ENABLE_ERROR_ALERTS:
                self.alert_system.send_error_alert({
                    'type': 'CircuitBreaker',
                    'message': 'Circuit breaker triggered during position monitoring',
                    'system_status': 'HALTED',
                })
    
    def manage_aggressive_positions(self):
        """Manage aggressive positions with tight stops"""
        actions = []
        
        for symbol, position in self.current_positions.items():
            try:
                # Get current quote
                quote = self.scanner.get_real_time_quote(symbol)
                if not quote:
                    continue
                
                current_price = quote['price']
                entry_price = position['entry_price']
                stop_loss = position['stop_loss']
                take_profit = position['take_profit']
                
                # Check stop loss
                if current_price <= stop_loss:
                    pnl = (current_price - entry_price) / entry_price
                    self.close_aggressive_position(symbol, current_price, pnl, "Stop Loss")
                    action = f"STOP LOSS: {symbol} at ${current_price:.2f} ({pnl:+.1%})"
                    actions.append(action)
                    continue
                
                # Check take profit
                if current_price >= take_profit:
                    pnl = (current_price - entry_price) / entry_price
                    self.close_aggressive_position(symbol, current_price, pnl, "Take Profit")
                    action = f"TAKE PROFIT: {symbol} at ${current_price:.2f} ({pnl:+.1%})"
                    actions.append(action)
                    continue
                
                # Update trailing stop (aggressive)
                if current_price > entry_price * 1.05:  # 5% profit
                    new_stop = entry_price * 1.02  # 2% trailing stop
                    if new_stop > position['stop_loss']:
                        position['stop_loss'] = new_stop
                        action = f"TRAILING STOP: {symbol} to ${new_stop:.2f}"
                        actions.append(action)
                
            except Exception as e:
                self.logger.error(f"Error managing position {symbol}: {e}")
        
        return actions
    
    def close_aggressive_position(self, symbol, exit_price, pnl, reason):
        """Close aggressive position and record outcome for self-improvement"""
        try:
            position = self.current_positions.get(symbol)
            if not position:
                return
            
            # Place sell order
            shares = position['shares']
            order = self.engine.place_swing_order(symbol, shares, 'sell')
            
            if order:
                # Track trade
                trade_data = {
                    'date': datetime.now().date(),
                    'symbol': symbol,
                    'action': 'sell',
                    'quantity': shares,
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'pnl': pnl * shares * position['entry_price'],
                    'pnl_percent': pnl,
                    'holding_days': (datetime.now() - position['entry_time']).days,
                    'exit_reason': reason.lower().replace(' ', '_'),
                    'entry_time': position['entry_time'].isoformat(),
                    'exit_time': datetime.now().isoformat(),
                    'stop_loss': position.get('stop_loss', position['entry_price'] * 0.9),
                    'take_profit': position.get('take_profit', position['entry_price'] * 1.08),
                    'strategy': 'aggressive_swing',
                    'extended_hours': position.get('extended_hours', False)
                }
                self.tracker.track_trade(trade_data)
                
                # RECORD FOR SELF-IMPROVING STRATEGY
                if self.adaptive_trading:
                    self.self_improving.record_trade_outcome(trade_data)
                    self.logger.info(f"Trade outcome recorded for self-improvement: {symbol} {pnl:+.2%}")
                
                # Remove from tracking
                del self.current_positions[symbol]

                self.logger.info(f"Closed {symbol}: {reason} at ${exit_price:.2f} ({pnl:+.1%})")

                # Send SL / TP alert
                if self.config.ENABLE_TRADE_ALERTS:
                    alert_payload = {
                        'symbol': symbol,
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'pnl': pnl * 100,
                    }
                    if 'Stop' in reason:
                        self.alert_system.send_stop_loss_alert(alert_payload)
                    elif 'Profit' in reason:
                        self.alert_system.send_take_profit_alert(alert_payload)
        
        except Exception as e:
            self.logger.error(f"Error closing position {symbol}: {e}")
    
    def display_aggressive_positions(self):
        """Display current aggressive positions"""
        if not self.current_positions:
            self.logger.info("No open positions")
            return
        
        self.logger.info("CURRENT AGGRESSIVE POSITIONS:")
        total_pnl = 0
        
        for symbol, pos in self.current_positions.items():
            try:
                quote = self.scanner.get_real_time_quote(symbol)
                if quote:
                    current_price = quote['price']
                    pnl = (current_price - pos['entry_price']) / pos['entry_price']
                    total_pnl += pnl
                    
                    self.logger.info(f"  {symbol}: {pos['shares']} shares @ ${pos['entry_price']:.2f}")
                    self.logger.info(f"    Current: ${current_price:.2f} ({pnl:+.1%})")
                    self.logger.info(f"    Stop: ${pos['stop_loss']:.2f} | Target: ${pos['take_profit']:.2f}")
                    self.logger.info(f"    Holding: {(datetime.now() - pos['entry_time']).days} days")
            except:
                continue
        
        self.logger.info(f"Total PnL: {total_pnl:+.1%}")
    
    def track_performance(self):
        """Track performance against targets"""
        try:
            account = self.engine.api.get_account()
            portfolio_value = float(account.equity)
            
            # Track daily performance
            can_continue = self.tracker.track_daily_performance(
                datetime.now().date(), 
                portfolio_value,
                len(self.current_positions)
            )
            
            if not can_continue:
                self.logger.warning("Daily loss limit hit - stopping trading")
                self.is_trading_allowed = False
            
            # Check quarterly status
            quarterly_status = self.tracker.get_current_quarter_status()
            if isinstance(quarterly_status, dict):
                self.logger.info(f"Quarterly Status: {quarterly_status['status']}")
                self.logger.info(f"Progress: {quarterly_status['progress']:.1%} to target")
            else:
                self.logger.info(f"Quarterly Status: {quarterly_status}")
            
        except Exception as e:
            self.logger.error(f"Error tracking performance: {e}")
    
    def end_of_day_report(self):
        """Generate end of day report"""
        self.logger.info("END OF DAY REPORT")
        self.logger.info("=" * 50)
        
        try:
            # Final performance tracking
            self.track_performance()
            
            # Generate comprehensive report
            report = self.tracker.generate_performance_report()
            
            if isinstance(report.get('quarterly_status'), dict):
                self.logger.info(f"Quarterly Status: {report['quarterly_status']['status']}")
                self.logger.info(f"Quarterly Return: {report['quarterly_status']['current_return']:+.1%}")
                self.logger.info(f"Quarterly Target: {report['quarterly_status']['target_return']:+.1%}")
                self.logger.info(f"Progress: {report['quarterly_status']['progress']:.1%}")
                
                # Check if we need to stop trading
                if report['quarterly_status']['status'] == "LOSS LIMIT HIT":
                    self.logger.error("Quarterly loss limit hit - TRADING SUSPENDED")
                    self.is_trading_allowed = False

            # Send daily summary alert
            if self.config.ENABLE_DAILY_SUMMARY:
                try:
                    account = self.engine.api.get_account()
                    portfolio_value = float(account.equity)
                    daily_perf = self.tracker.daily_performance
                    start_value = daily_perf[-1].get('start_value', portfolio_value) if daily_perf else portfolio_value
                    daily_return = (portfolio_value - start_value) / start_value * 100 if start_value else 0
                    from datetime import date, timedelta
                    next_day = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
                    self.alert_system.send_daily_summary({
                        'start_value': start_value,
                        'end_value': portfolio_value,
                        'return': daily_return,
                        'trades_count': self.daily_trades_count,
                        'open_positions': len(self.current_positions),
                        'win_rate': 0,
                        'next_day': next_day,
                    })
                except Exception as alert_e:
                    self.logger.warning(f"Could not send daily summary alert: {alert_e}")

        except Exception as e:
            self.logger.error(f"Error generating end of day report: {e}")
    
    def scan_options_opportunities(self):
        """
        Scan for high-probability options opportunities
        ALERT ONLY - No execution (90%+ probability)
        """
        self.logger.info("OPTIONS SCAN (90%+ Probability)")
        self.logger.info("=" * 60)
        self.logger.info("ALERT ONLY - No auto-execution")
        
        try:
            # Scan and alert (90%+ threshold)
            opportunities = self.options_alerter.scan_and_alert(self.options_symbols)
            
            if opportunities:
                self.logger.info(f"Found {len(opportunities)} high-probability options setups")
                self.logger.info("Review alerts above and decide manually")
            else:
                self.logger.info("No 90%+ probability options setups found")
                
        except Exception as e:
            self.logger.error(f"Error in options scan: {e}")
    
    def execute_80_percent_options(self):
        """
        Execute 80% probability options trades
        10% portfolio allocation | 25% SL | 50% TP
        """
        if not self.options_active:
            return
        
        self.logger.info("80% OPTIONS TRADER - Auto-Execution")
        self.logger.info("=" * 60)
        self.logger.info("Threshold: 80% | Allocation: 10% | SL: 25% | TP: 50%")
        
        try:
            # Get portfolio value for sizing
            account = self.engine.api.get_account()
            portfolio_value = float(account.equity)
            
            # Check available options allocation
            available = self.options_trader.get_options_allocation(portfolio_value)
            self.logger.info(f"Options allocation available: ${available:,.2f}")
            
            if available <= 0:
                self.logger.info("No options allocation available")
                return
            
            # Scan for 80%+ opportunities
            opportunities = self.options_trader.scan_for_80_percent_opportunities(self.options_symbols)
            
            # Filter and execute
            executed = 0
            for opp in opportunities:
                if opp['probability'] >= 0.80:
                    success = self.options_trader.execute_options_trade(opp, portfolio_value)
                    if success:
                        executed += 1
                        self.logger.info(f"EXECUTED: {opp['symbol']} {opp['strategy']}")
                    
                    # Stop after 2 options trades per scan
                    if executed >= 2:
                        break
            
            self.logger.info(f"Executed {executed} options trades")
            
            # Monitor existing positions
            self.monitor_options_positions(portfolio_value)
            
        except Exception as e:
            self.logger.error(f"Error in 80% options execution: {e}")
    
    def monitor_options_positions(self, portfolio_value: float):
        """Monitor options positions for SL/TP"""
        try:
            actions = self.options_trader.monitor_options_positions(portfolio_value)
            
            for action in actions:
                self.logger.info(f"OPTIONS: {action}")
            
            # Show summary
            summary = self.options_trader.get_options_summary()
            if summary['open_positions'] > 0:
                self.logger.info(f"Options Positions: {summary['open_positions']} open")
                self.logger.info(f"Total Exposure: ${summary['total_exposure']:,.2f}")
                self.logger.info(f"Potential Profit: ${summary['total_potential_profit']:,.2f}")
                
        except Exception as e:
            self.logger.error(f"Error monitoring options: {e}")
    
    def generate_self_improvement_report(self):
        """Generate self-improvement strategy report"""
        if not self.adaptive_trading:
            return
        
        try:
            self.logger.info("=" * 60)
            self.logger.info("SELF-IMPROVEMENT STRATEGY REPORT")
            self.logger.info("=" * 60)
            
            report = self.self_improving.get_strategy_report()
            
            self.logger.info(f"Total Trades Analyzed: {report['total_trades_recorded']}")
            self.logger.info(f"Recent Win Rate: {report['recent_win_rate']:.1%}")
            self.logger.info(f"Recent Avg Return: {report['recent_avg_return']:+.2%}")
            self.logger.info(f"Current Streak: {report['current_streak']}")
            self.logger.info(f"Best/Worst Streak: {report['best_streak']}/{report['worst_streak']}")
            self.logger.info(f"Market Regime: {report['current_regime']}")
            self.logger.info(f"Adaptations Made: {report['adaptations_made']}")
            
            # Show current adaptive parameters
            params = report['current_params']
            self.logger.info("Current Adaptive Parameters:")
            self.logger.info(f"  Position Size: {params['base_position_pct']:.1%}")
            self.logger.info(f"  Stop Loss: {params['base_stop_loss_pct']:.1%}")
            self.logger.info(f"  Take Profit: {params['base_take_profit_pct']:.1%}")
            self.logger.info(f"  Entry Delay: {params['entry_delay_minutes']} min")
            self.logger.info(f"  R/R Target: {params['rr_ratio_target']:.1f}")
            
            # Check if should pause
            should_pause, reason = self.self_improving.should_pause_trading()
            if should_pause:
                self.logger.warning(f"SELF-IMPROVEMENT ALERT: {reason}")
            
            self.logger.info("=" * 60)
            
        except Exception as e:
            self.logger.error(f"Error generating self-improvement report: {e}")
    
    def run_aggressive_system(self):
        """Run the aggressive trading system with extended hours support"""
        self.logger.info("AGGRESSIVE SWING TRADING SYSTEM STARTED")
        self.logger.info("=" * 60)
        self.logger.info("Extended Hours Trading: ENABLED")
        self.logger.info("Pre-Market: 7:00 AM - 9:30 AM EST")
        self.logger.info("Regular Hours: 9:30 AM - 4:00 PM EST")
        self.logger.info("Post-Market: 4:00 PM - 8:00 PM EST")
        self.logger.info("=" * 60)
        self.logger.info("OPTIONS SCANNER: ENABLED (90%+ Probability Alerts)")
        self.logger.info("Options are ALERT ONLY - Manual execution required")
        self.logger.info("=" * 60)
        self.logger.info("80% OPTIONS TRADER: ENABLED (Auto-Execution)")
        self.logger.info("Allocation: 10% | SL: 25% | TP: 50%")
        self.logger.info("=" * 60)
        self.logger.info("SELF-IMPROVING STRATEGY: ENABLED")
        self.logger.info("Adaptive execution based on trade outcomes")
        self.logger.info("Auto-adjusts: Position size, SL/TP, Entry timing")
        self.logger.info("=" * 60)
        
        # Initialize
        if not self.initialize():
            return
        
        # Schedule aggressive tasks with extended hours - ULTRA FREQUENCY (every 15 min)
        # Pre-market scans
        schedule.every().day.at("07:00").do(self.aggressive_morning_scan)
        schedule.every().day.at("07:15").do(self.aggressive_morning_scan)
        schedule.every().day.at("07:30").do(self.aggressive_morning_scan)
        schedule.every().day.at("07:45").do(self.aggressive_morning_scan)
        schedule.every().day.at("08:00").do(self.aggressive_morning_scan)
        schedule.every().day.at("08:15").do(self.aggressive_morning_scan)
        schedule.every().day.at("08:30").do(self.aggressive_morning_scan)
        schedule.every().day.at("08:45").do(self.aggressive_morning_scan)
        
        # Market open scans
        schedule.every().day.at("09:25").do(self.aggressive_morning_scan)
        schedule.every().day.at("09:30").do(self.aggressive_morning_scan)
        schedule.every().day.at("09:45").do(self.aggressive_morning_scan)
        
        # Regular hours - every 15 minutes
        schedule.every().day.at("10:00").do(self.aggressive_monitoring)
        schedule.every().day.at("10:15").do(self.aggressive_monitoring)
        schedule.every().day.at("10:30").do(self.aggressive_monitoring)
        schedule.every().day.at("10:45").do(self.aggressive_monitoring)
        schedule.every().day.at("11:00").do(self.aggressive_monitoring)
        schedule.every().day.at("11:15").do(self.aggressive_monitoring)
        schedule.every().day.at("11:30").do(self.aggressive_monitoring)
        schedule.every().day.at("11:45").do(self.aggressive_monitoring)
        schedule.every().day.at("12:00").do(self.aggressive_monitoring)
        schedule.every().day.at("12:15").do(self.aggressive_monitoring)
        schedule.every().day.at("12:30").do(self.aggressive_monitoring)
        schedule.every().day.at("12:45").do(self.aggressive_monitoring)
        schedule.every().day.at("13:00").do(self.aggressive_monitoring)
        schedule.every().day.at("13:15").do(self.aggressive_monitoring)
        schedule.every().day.at("13:30").do(self.aggressive_monitoring)
        schedule.every().day.at("13:45").do(self.aggressive_monitoring)
        schedule.every().day.at("14:00").do(self.aggressive_monitoring)
        schedule.every().day.at("14:15").do(self.aggressive_monitoring)
        schedule.every().day.at("14:30").do(self.aggressive_monitoring)
        schedule.every().day.at("14:45").do(self.aggressive_monitoring)
        schedule.every().day.at("15:00").do(self.aggressive_monitoring)
        schedule.every().day.at("15:15").do(self.aggressive_monitoring)
        schedule.every().day.at("15:30").do(self.aggressive_monitoring)
        schedule.every().day.at("15:45").do(self.aggressive_monitoring)
        schedule.every().day.at("15:55").do(self.aggressive_monitoring)
        
        # Post-market scans - every 15 minutes
        schedule.every().day.at("16:05").do(self.aggressive_monitoring)
        schedule.every().day.at("16:15").do(self.aggressive_monitoring)
        schedule.every().day.at("16:30").do(self.aggressive_monitoring)
        schedule.every().day.at("16:45").do(self.aggressive_monitoring)
        schedule.every().day.at("17:00").do(self.aggressive_monitoring)
        schedule.every().day.at("17:15").do(self.aggressive_monitoring)
        schedule.every().day.at("17:30").do(self.aggressive_monitoring)
        schedule.every().day.at("17:45").do(self.aggressive_monitoring)
        schedule.every().day.at("18:00").do(self.aggressive_monitoring)
        schedule.every().day.at("18:15").do(self.aggressive_monitoring)
        schedule.every().day.at("18:30").do(self.aggressive_monitoring)
        schedule.every().day.at("18:45").do(self.aggressive_monitoring)
        schedule.every().day.at("19:00").do(self.aggressive_monitoring)
        schedule.every().day.at("19:15").do(self.aggressive_monitoring)
        schedule.every().day.at("19:30").do(self.end_of_day_report)
        
        # 90%+ Options scanner (alert only) - every 30 minutes
        schedule.every().day.at("09:45").do(self.scan_options_opportunities)
        schedule.every().day.at("10:15").do(self.scan_options_opportunities)
        schedule.every().day.at("10:45").do(self.scan_options_opportunities)
        schedule.every().day.at("11:15").do(self.scan_options_opportunities)
        schedule.every().day.at("11:45").do(self.scan_options_opportunities)
        schedule.every().day.at("12:15").do(self.scan_options_opportunities)
        schedule.every().day.at("12:45").do(self.scan_options_opportunities)
        schedule.every().day.at("13:15").do(self.scan_options_opportunities)
        schedule.every().day.at("13:45").do(self.scan_options_opportunities)
        schedule.every().day.at("14:15").do(self.scan_options_opportunities)
        schedule.every().day.at("14:45").do(self.scan_options_opportunities)
        schedule.every().day.at("15:15").do(self.scan_options_opportunities)
        schedule.every().day.at("15:45").do(self.scan_options_opportunities)
        schedule.every().day.at("16:15").do(self.scan_options_opportunities)
        schedule.every().day.at("16:45").do(self.scan_options_opportunities)
        
        # 80%+ Options trader (auto-execution) - every 30 minutes
        schedule.every().day.at("09:30").do(self.execute_80_percent_options)
        schedule.every().day.at("10:00").do(self.execute_80_percent_options)
        schedule.every().day.at("10:30").do(self.execute_80_percent_options)
        schedule.every().day.at("11:00").do(self.execute_80_percent_options)
        schedule.every().day.at("11:30").do(self.execute_80_percent_options)
        schedule.every().day.at("12:00").do(self.execute_80_percent_options)
        schedule.every().day.at("12:30").do(self.execute_80_percent_options)
        schedule.every().day.at("13:00").do(self.execute_80_percent_options)
        schedule.every().day.at("13:30").do(self.execute_80_percent_options)
        schedule.every().day.at("14:00").do(self.execute_80_percent_options)
        schedule.every().day.at("14:30").do(self.execute_80_percent_options)
        schedule.every().day.at("15:00").do(self.execute_80_percent_options)
        schedule.every().day.at("15:30").do(self.execute_80_percent_options)
        schedule.every().day.at("16:00").do(self.execute_80_percent_options)
        schedule.every().day.at("16:30").do(self.execute_80_percent_options)
        schedule.every().day.at("17:00").do(self.execute_80_percent_options)
        
        # Self-improvement reports - every 2 hours during trading
        schedule.every().day.at("09:00").do(self.generate_self_improvement_report)
        schedule.every().day.at("11:00").do(self.generate_self_improvement_report)
        schedule.every().day.at("13:00").do(self.generate_self_improvement_report)
        schedule.every().day.at("15:00").do(self.generate_self_improvement_report)
        schedule.every().day.at("17:00").do(self.generate_self_improvement_report)
        schedule.every().day.at("19:00").do(self.generate_self_improvement_report)
        
        # Auto-save state every 15 minutes
        schedule.every(15).minutes.do(lambda: self.state_manager.save_current_state(self))

        # Initial scans
        self.aggressive_morning_scan()
        self.scan_options_opportunities()

        # Initial self-improvement report
        if self.adaptive_trading:
            self.generate_self_improvement_report()

        # Run scheduled tasks
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.info("Shutting down aggressive trading system...")
                self.state_manager.save_current_state(self)
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(60)

def main():
    trader = AggressiveSwingTrader()
    
    # Check if test run
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        trader.initialize()
        trader.aggressive_morning_scan()
        trader.aggressive_monitoring()
        trader.end_of_day_report()
    else:
        trader.run_aggressive_system()

if __name__ == "__main__":
    main()
