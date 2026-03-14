"""
OPTIONS ALERT SYSTEM
Sends notifications for 90%+ probability options setups
NO EXECUTION - Only alerts for user decision
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)

class OptionsAlertSystem:
    """
    Alert system for high-probability options opportunities
    Sends notifications - does NOT execute trades
    """
    
    def __init__(self, options_scanner, alert_methods: List[str] = None):
        self.scanner = options_scanner
        self.alert_methods = alert_methods or ['console', 'log']
        self.alert_history = []
        self.min_probability = 0.90  # 90% threshold
        
        # Track alerted setups to avoid duplicates
        self.alerted_setups = set()
        
    def scan_and_alert(self, symbols: List[str]) -> List[Dict]:
        """
        Scan for opportunities and send alerts
        Returns list of high-probability setups
        """
        logger.info("=" * 70)
        logger.info("OPTIONS SCAN - 90%+ PROBABILITY SETUPS")
        logger.info("=" * 70)
        
        # Scan for opportunities
        opportunities = self.scanner.scan_for_options_opportunities(symbols)
        
        # Filter for new alerts (avoid duplicates)
        new_opportunities = []
        for opp in opportunities:
            setup_key = f"{opp['symbol']}_{opp['strategy']}_{opp['expiration']}"
            if setup_key not in self.alerted_setups:
                new_opportunities.append(opp)
                self.alerted_setups.add(setup_key)
        
        # Send alerts
        if new_opportunities:
            self._send_alerts(new_opportunities)
            self._store_alerts(new_opportunities)
        else:
            logger.info("No new 90%+ probability options setups found.")
        
        return new_opportunities
    
    def _send_alerts(self, opportunities: List[Dict]):
        """Send alerts through configured channels"""
        
        for method in self.alert_methods:
            if method == 'console':
                self._console_alert(opportunities)
            elif method == 'log':
                self._log_alert(opportunities)
            elif method == 'email':
                self._email_alert(opportunities)
            elif method == 'webhook':
                self._webhook_alert(opportunities)
    
    def _console_alert(self, opportunities: List[Dict]):
        """Print alert to console"""
        print("\n" + "=" * 70)
        print("🚨 OPTIONS ALERT - HIGH PROBABILITY SETUPS DETECTED")
        print("=" * 70)
        print(f"\n⏰ Alert Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"📊 Found: {len(opportunities)} setup(s) with 90%+ probability")
        print("\n⚠️  REVIEW REQUIRED - NO AUTO-EXECUTION")
        print("=" * 70)
        
        for i, opp in enumerate(opportunities, 1):
            print(f"\n{i}. 🎯 {opp['symbol']} - {opp['strategy']}")
            print(f"   Direction: {opp['direction']}")
            print(f"   Probability: {opp['probability']*100:.1f}%")
            print(f"   Underlying: ${opp['underlying_price']:.2f}")
            print(f"   Max Profit: ${opp['max_profit']:.2f}")
            print(f"   Max Loss: ${opp['max_loss']:.2f}")
            
            if opp['direction'] == 'BULLISH':
                print(f"   Buy Strike: ${opp['buy_strike']}")
                print(f"   Sell Strike: ${opp['sell_strike']}")
            elif opp['direction'] == 'BEARISH':
                print(f"   Sell Strike: ${opp['sell_strike']}")
                print(f"   Buy Strike: ${opp['buy_strike']}")
            elif opp['direction'] == 'NEUTRAL':
                print(f"   Put Sell: ${opp['put_sell_strike']}")
                print(f"   Put Buy: ${opp['put_buy_strike']}")
                print(f"   Call Sell: ${opp['call_sell_strike']}")
                print(f"   Call Buy: ${opp['call_buy_strike']}")
            
            print(f"   Breakeven: ${opp['breakeven']}")
            print(f"   Expiration: {opp['expiration']} ({opp['days_to_expiration']} DTE)")
            print(f"   Premium: ${opp['premium']}")
            print(f"   IV Percentile: {opp['iv_percentile']}%")
            print(f"   Volume/OI: {opp['volume']}/{opp['open_interest']}")
            
        print("\n" + "=" * 70)
        print("✋ DECISION REQUIRED:")
        print("   To execute: Review in broker platform")
        print("   To ignore: Alert will clear in 30 minutes")
        print("=" * 70 + "\n")
    
    def _log_alert(self, opportunities: List[Dict]):
        """Log alert to file"""
        for opp in opportunities:
            logger.warning(
                f"OPTIONS ALERT: {opp['symbol']} | "
                f"{opp['strategy']} | "
                f"Prob: {opp['probability']*100:.1f}% | "
                f"Max Profit: ${opp['max_profit']:.2f} | "
                f"Max Loss: ${opp['max_loss']:.2f}"
            )
    
    def _email_alert(self, opportunities: List[Dict]):
        """Send email alert (placeholder)"""
        # TODO: Implement email notification
        logger.info("Email alert would be sent here")
        pass
    
    def _webhook_alert(self, opportunities: List[Dict]):
        """Send webhook alert (Slack/Discord) (placeholder)"""
        # TODO: Implement webhook
        logger.info("Webhook alert would be sent here")
        pass
    
    def _store_alerts(self, opportunities: List[Dict]):
        """Store alerts in history"""
        for opp in opportunities:
            alert_record = {
                'timestamp': datetime.now().isoformat(),
                'symbol': opp['symbol'],
                'strategy': opp['strategy'],
                'probability': opp['probability'],
                'direction': opp['direction'],
                'underlying_price': opp['underlying_price'],
                'max_profit': opp['max_profit'],
                'max_loss': opp['max_loss'],
                'expiration': opp['expiration'],
                'status': 'PENDING_DECISION'
            }
            self.alert_history.append(alert_record)
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get recent alert history"""
        return sorted(
            self.alert_history, 
            key=lambda x: x['timestamp'], 
            reverse=True
        )[:limit]
    
    def clear_alerted_setups(self):
        """Clear alerted setups (call periodically to allow re-alerts)"""
        self.alerted_setups.clear()
        logger.info("Cleared alerted setups cache - will alert on new signals")


def run_options_monitor(symbols: List[str], interval_minutes: int = 15):
    """
    Run continuous options monitoring
    Scans periodically and sends alerts
    """
    from config import config
    from options_scanner import OptionsScanner
    
    # Initialize
    scanner = OptionsScanner(config.POLYGON_API_KEY)
    alerter = OptionsAlertSystem(
        scanner, 
        alert_methods=['console', 'log']
    )
    
    logger.info("=" * 70)
    logger.info("OPTIONS MONITOR STARTED")
    logger.info(f"Scanning {len(symbols)} symbols every {interval_minutes} minutes")
    logger.info("Alert threshold: 90% probability")
    logger.info("NO AUTO-EXECUTION - Manual decision required")
    logger.info("=" * 70)
    
    try:
        while True:
            # Scan and alert
            opportunities = alerter.scan_and_alert(symbols)
            
            if opportunities:
                logger.info(f"Alerted on {len(opportunities)} setups - waiting for decision")
            
            # Clear old alerts every hour to allow re-alerts
            if datetime.now().minute == 0:
                alerter.clear_alerted_setups()
            
            # Wait for next scan
            logger.info(f"Next scan in {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
            
    except KeyboardInterrupt:
        logger.info("\nOptions monitor stopped by user")
    except Exception as e:
        logger.error(f"Error in options monitor: {e}")


# Quick test function
def test_options_alert():
    """Test the options alert system"""
    from config import config
    from options_scanner import OptionsScanner
    
    scanner = OptionsScanner(config.POLYGON_API_KEY)
    alerter = OptionsAlertSystem(scanner, ['console', 'log'])
    
    # Test symbols
    symbols = ['AAPL', 'TSLA', 'NVDA', 'AMD', 'SPY']
    
    print("\nTesting Options Alert System...")
    print("(Simulated data - would use real API in production)\n")
    
    opportunities = alerter.scan_and_alert(symbols)
    
    if opportunities:
        print(f"\n✅ Alert system working - found {len(opportunities)} setups")
    else:
        print("\nℹ️ No 90%+ setups found (this is normal)")
    
    return opportunities


if __name__ == "__main__":
    # Run test
    test_options_alert()
