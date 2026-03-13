"""
MONITORING & ALERTING SYSTEM
Proposed enhancement for real-time trading alerts
"""

import logging
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict
import requests

class TradingAlertSystem:
    """
    Real-time monitoring and alerting for trading system
    """
    
    def __init__(self, email_config=None, webhook_url=None):
        self.email_config = email_config or {}
        self.webhook_url = webhook_url
        self.alert_history = []
        
    def send_trade_alert(self, trade_info: Dict):
        """
        Send alert when trade is executed
        """
        message = f"""
🚀 TRADE EXECUTED

Symbol: {trade_info['symbol']}
Action: {trade_info['action']}
Quantity: {trade_info['quantity']}
Price: ${trade_info['price']:.2f}
Time: {datetime.now().strftime('%H:%M:%S')}
Session: {trade_info.get('session', 'Regular')}
        """
        
        self._send_alert(message, level='INFO')
        
    def send_stop_loss_alert(self, position_info: Dict):
        """
        Send alert when stop loss is hit
        """
        message = f"""
🔴 STOP LOSS TRIGGERED

Symbol: {position_info['symbol']}
Entry: ${position_info['entry_price']:.2f}
Exit: ${position_info['exit_price']:.2f}
Loss: {position_info['pnl']:.2f}%
Time: {datetime.now().strftime('%H:%M:%S')}

Action: Position closed automatically
        """
        
        self._send_alert(message, level='WARNING')
        
    def send_take_profit_alert(self, position_info: Dict):
        """
        Send alert when take profit is hit
        """
        message = f"""
🟢 TAKE PROFIT ACHIEVED

Symbol: {position_info['symbol']}
Entry: ${position_info['entry_price']:.2f}
Exit: ${position_info['exit_price']:.2f}
Profit: {position_info['pnl']:.2f}%
Time: {datetime.now().strftime('%H:%M:%S')}

Action: Position closed automatically
        """
        
        self._send_alert(message, level='SUCCESS')
        
    def send_daily_summary(self, performance: Dict):
        """
        Send daily performance summary
        """
        message = f"""
📊 DAILY TRADING SUMMARY

Date: {datetime.now().strftime('%Y-%m-%d')}

Performance:
• Starting Value: ${performance['start_value']:,.2f}
• Ending Value: ${performance['end_value']:,.2f}
• Daily Return: {performance['return']:.2f}%
• Target: 1.5%

Trading Activity:
• Trades Executed: {performance['trades_count']}
• Positions Open: {performance['open_positions']}
• Win Rate: {performance.get('win_rate', 0):.1f}%

Status: {'✅ TARGET MET' if performance['return'] >= 0.015 else '❌ BELOW TARGET'}

Next Trading Day: {performance['next_day']}
        """
        
        self._send_alert(message, level='INFO')
        
    def send_error_alert(self, error_info: Dict):
        """
        Send alert when critical error occurs
        """
        message = f"""
🚨 CRITICAL ERROR ALERT

Error Type: {error_info['type']}
Time: {datetime.now().strftime('%H:%M:%S')}
Message: {error_info['message']}

Action Required:
1. Check trading system status
2. Verify API connections
3. Review error logs
4. Take manual action if needed

System Status: {error_info.get('system_status', 'UNKNOWN')}
        """
        
        self._send_alert(message, level='CRITICAL')
        
    def send_circuit_breaker_alert(self, reason: str):
        """
        Send alert when circuit breaker activates
        """
        message = f"""
🚫 CIRCUIT BREAKER ACTIVATED

Reason: {reason}
Time: {datetime.now().strftime('%H:%M:%S')}

Trading has been automatically halted to prevent further losses.

Manual Review Required:
• Check market conditions
• Review recent trades
• Verify system health
• Reset circuit breaker when safe

System will not resume trading until manually reset.
        """
        
        self._send_alert(message, level='CRITICAL')
        
    def _send_alert(self, message: str, level: str = 'INFO'):
        """
        Send alert via multiple channels
        """
        # Log to file
        logging.log(self._get_log_level(level), message)
        
        # Send email if configured
        if self.email_config:
            self._send_email(message, level)
            
        # Send webhook if configured
        if self.webhook_url:
            self._send_webhook(message, level)
            
        # Store in history
        self.alert_history.append({
            'timestamp': datetime.now(),
            'level': level,
            'message': message
        })
        
    def _send_email(self, message: str, level: str):
        """
        Send email alert
        """
        try:
            msg = MIMEText(message)
            msg['Subject'] = f"Trading Alert: {level}"
            msg['From'] = self.email_config.get('from')
            msg['To'] = self.email_config.get('to')
            
            server = smtplib.SMTP(self.email_config.get('smtp_server'), 587)
            server.starttls()
            server.login(
                self.email_config.get('username'),
                self.email_config.get('password')
            )
            server.send_message(msg)
            server.quit()
            
        except Exception as e:
            logging.error(f"Failed to send email alert: {e}")
            
    def _send_webhook(self, message: str, level: str):
        """
        Send webhook alert (Slack, Discord, etc.)
        """
        try:
            payload = {
                'text': message,
                'level': level,
                'timestamp': datetime.now().isoformat()
            }
            
            requests.post(self.webhook_url, json=payload, timeout=10)
            
        except Exception as e:
            logging.error(f"Failed to send webhook alert: {e}")
            
    def _get_log_level(self, level: str) -> int:
        """
        Convert string level to logging level
        """
        levels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
            'SUCCESS': 25  # Custom level between INFO and WARNING
        }
        return levels.get(level, logging.INFO)

# PROPOSED CONFIGURATION:
# Add to aggressive_config.py:
#
# # Alert Configuration
# ALERT_EMAIL_CONFIG = {
#     'smtp_server': 'smtp.gmail.com',
#     'username': 'your_email@gmail.com',
#     'password': 'your_app_password',
#     'from': 'your_email@gmail.com',
#     'to': 'your_phone@sms.gateway.com'  # For SMS alerts
# }
#
# ALERT_WEBHOOK_URL = 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
#
# ENABLE_TRADE_ALERTS = True
# ENABLE_ERROR_ALERTS = True
# ENABLE_DAILY_SUMMARY = True
