"""
DATA BACKUP & RECOVERY SYSTEM
Proposed enhancement for trading state persistence
"""

import json
import pickle
import shutil
from datetime import datetime
from pathlib import Path
import logging

class TradingStateManager:
    """
    Persistent state management and recovery for trading system
    """
    
    def __init__(self, backup_dir='trading_backups'):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.state_file = self.backup_dir / 'current_state.json'
        self.positions_file = self.backup_dir / 'positions.pkl'
        self.history_file = self.backup_dir / 'trade_history.json'
        
    def save_current_state(self, trader):
        """
        Save complete trading state for recovery
        """
        try:
            state = {
                'timestamp': datetime.now().isoformat(),
                'daily_trades_count': trader.daily_trades_count,
                'current_positions': trader.current_positions,
                'is_trading_allowed': trader.is_trading_allowed,
                'engine_positions': trader.engine.positions,
                'swing_stops': trader.engine.swing_stops,
                'swing_targets': trader.engine.swing_targets,
                'tracker_performance': {
                    'daily': trader.tracker.daily_performance[-5:] if trader.tracker.daily_performance else [],
                    'trades': trader.tracker.trades[-10:] if trader.tracker.trades else []
                }
            }
            
            # Save to JSON
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
            
            # Create timestamped backup
            backup_name = f"state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy(self.state_file, self.backup_dir / backup_name)
            
            # Cleanup old backups (keep last 50)
            self._cleanup_old_backups()
            
            logging.info("💾 Trading state saved successfully")
            return True
            
        except Exception as e:
            logging.error(f"Failed to save state: {e}")
            return False
    
    def load_previous_state(self):
        """
        Load previous trading state for recovery
        """
        try:
            if not self.state_file.exists():
                logging.info("No previous state found - starting fresh")
                return None
            
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            logging.info(f"📂 Previous state loaded from {state.get('timestamp', 'unknown')}")
            return state
            
        except Exception as e:
            logging.error(f"Failed to load state: {e}")
            return None
    
    def recover_from_crash(self, trader):
        """
        Recover trading state after system crash
        """
        state = self.load_previous_state()
        
        if not state:
            return False
        
        try:
            logging.info("🔄 Recovering from previous state...")
            
            # Restore positions
            trader.current_positions = state.get('current_positions', {})
            trader.engine.positions = state.get('engine_positions', {})
            trader.engine.swing_stops = state.get('swing_stops', {})
            trader.engine.swing_targets = state.get('swing_targets', {})
            trader.daily_trades_count = state.get('daily_trades_count', 0)
            
            # Check if we need to sync with broker
            self._sync_positions_with_broker(trader)
            
            logging.info("✅ State recovery complete")
            return True
            
        except Exception as e:
            logging.error(f"Recovery failed: {e}")
            return False
    
    def _sync_positions_with_broker(self, trader):
        """
        Sync local positions with broker positions
        """
        try:
            # Get current broker positions
            broker_positions = trader.engine.api.list_positions()
            
            # Update local state to match broker
            broker_symbols = {pos.symbol for pos in broker_positions}
            local_symbols = set(trader.current_positions.keys())
            
            # Find discrepancies
            missing_from_local = broker_symbols - local_symbols
            missing_from_broker = local_symbols - broker_symbols
            
            if missing_from_local:
                logging.warning(f"⚠️ Positions in broker but not local: {missing_from_local}")
                # Add missing positions to local state
                for pos in broker_positions:
                    if pos.symbol in missing_from_local:
                        trader.current_positions[pos.symbol] = {
                            'shares': int(pos.qty),
                            'entry_price': float(pos.avg_entry_price),
                            'stop_loss': float(pos.avg_entry_price) * 0.90,
                            'take_profit': float(pos.avg_entry_price) * 1.08,
                            'entry_time': datetime.now(),
                            'extended_hours': False
                        }
            
            if missing_from_broker:
                logging.warning(f"⚠️ Positions in local but not broker: {missing_from_broker}")
                # Remove positions that don't exist in broker
                for symbol in missing_from_broker:
                    del trader.current_positions[symbol]
            
            if not missing_from_local and not missing_from_broker:
                logging.info("✅ Positions synchronized with broker")
            
        except Exception as e:
            logging.error(f"Position sync failed: {e}")
    
    def _cleanup_old_backups(self, max_backups=50):
        """
        Remove old backup files, keep only recent ones
        """
        try:
            backups = sorted(
                self.backup_dir.glob('state_*.json'),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )
            
            # Remove old backups
            for backup in backups[max_backups:]:
                backup.unlink()
                
        except Exception as e:
            logging.error(f"Backup cleanup failed: {e}")
    
    def export_trade_history(self, format='csv'):
        """
        Export trade history for analysis
        """
        try:
            if not self.history_file.exists():
                return None
            
            with open(self.history_file, 'r') as f:
                history = json.load(f)
            
            if format == 'csv':
                import csv
                import io
                
                output = io.StringIO()
                if history:
                    writer = csv.DictWriter(output, fieldnames=history[0].keys())
                    writer.writeheader()
                    writer.writerows(history)
                
                return output.getvalue()
            
            return history
            
        except Exception as e:
            logging.error(f"Export failed: {e}")
            return None

# PROPOSED INTEGRATION:
# Add to main_aggressive_trader.py:
#
# class AggressiveSwingTrader:
#     def __init__(self):
#         ...
#         self.state_manager = TradingStateManager()
#         
#         # Try to recover from previous state
#         if self.state_manager.load_previous_state():
#             recovered = self.state_manager.recover_from_crash(self)
#             if recovered:
#                 logging.info("🔄 Recovered from previous session")
#     
#     def run_aggressive_system(self):
#         # Auto-save state every 15 minutes
#         schedule.every(15).minutes.do(
#             lambda: self.state_manager.save_current_state(self)
#         )
#         
#         # Save state on graceful shutdown
#         try:
#             while True:
#                 schedule.run_pending()
#                 time.sleep(60)
#         except KeyboardInterrupt:
#             self.state_manager.save_current_state(self)
#             logging.info("💾 State saved on shutdown")
