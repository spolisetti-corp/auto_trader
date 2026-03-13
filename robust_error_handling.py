"""
ROBUST ERROR HANDLING MODULE
Proposed enhancement for main_aggressive_trader.py
"""

import logging
import time
from datetime import datetime
import traceback

class RobustTradingManager:
    """
    Enhanced error handling and recovery for trading system
    """
    
    def __init__(self, max_retries=3, retry_delay=5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay  # seconds
        self.error_log = []
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.circuit_breaker = False
        
    def execute_with_retry(self, func, *args, **kwargs):
        """
        Execute function with retry logic and circuit breaker
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                # Check circuit breaker
                if self.circuit_breaker:
                    logging.error("🚫 Circuit breaker active - trading halted")
                    return None
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Reset error counter on success
                self.consecutive_errors = 0
                return result
                
            except Exception as e:
                error_msg = f"Attempt {attempt}/{self.max_retries} failed: {str(e)}"
                logging.error(error_msg)
                
                # Log error details
                self.error_log.append({
                    'timestamp': datetime.now(),
                    'function': func.__name__,
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })
                
                self.consecutive_errors += 1
                
                # Circuit breaker check
                if self.consecutive_errors >= self.max_consecutive_errors:
                    self.circuit_breaker = True
                    logging.critical(f"🚨 Circuit breaker triggered after {self.max_consecutive_errors} consecutive errors")
                    self.send_alert("Circuit breaker activated - trading halted")
                    return None
                
                # Retry with exponential backoff
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** (attempt - 1))
                    logging.info(f"⏳ Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
        
        return None
    
    def safe_api_call(self, api_func, *args, **kwargs):
        """
        Safe API call with rate limiting and error handling
        """
        try:
            # Add rate limiting delay
            time.sleep(0.1)  # 100ms between API calls
            
            result = api_func(*args, **kwargs)
            return result
            
        except Exception as e:
            if "rate limit" in str(e).lower():
                logging.warning("⚠️ Rate limit hit - backing off for 60 seconds")
                time.sleep(60)
                return self.safe_api_call(api_func, *args, **kwargs)
            
            elif "unauthorized" in str(e).lower():
                logging.critical("❌ API authorization failed - check credentials")
                self.circuit_breaker = True
                return None
            
            else:
                logging.error(f"API error: {str(e)}")
                return None
    
    def send_alert(self, message):
        """
        Send alert notification (can be extended to email, SMS, etc.)
        """
        logging.critical(f"🚨 ALERT: {message}")
        # TODO: Implement actual notification (email, SMS, Slack, etc.)
        pass
    
    def get_error_report(self):
        """
        Generate error report for analysis
        """
        if not self.error_log:
            return "No errors logged"
        
        report = []
        report.append("📊 ERROR REPORT")
        report.append("=" * 50)
        report.append(f"Total Errors: {len(self.error_log)}")
        report.append(f"Circuit Breaker: {'ACTIVE' if self.circuit_breaker else 'INACTIVE'}")
        report.append(f"Consecutive Errors: {self.consecutive_errors}")
        report.append("")
        
        # Recent errors
        recent_errors = self.error_log[-5:]
        for i, error in enumerate(recent_errors, 1):
            report.append(f"Error {i}:")
            report.append(f"  Time: {error['timestamp']}")
            report.append(f"  Function: {error['function']}")
            report.append(f"  Error: {error['error'][:100]}")
            report.append("")
        
        return "\n".join(report)

# PROPOSED INTEGRATION:
# Add to main_aggressive_trader.py:
# 
# class AggressiveSwingTrader:
#     def __init__(self):
#         ...
#         self.robust_manager = RobustTradingManager()
#     
#     def aggressive_morning_scan(self):
#         return self.robust_manager.execute_with_retry(
#             self._execute_morning_scan
#         )
#     
#     def _execute_morning_scan(self):
#         # Original implementation
#         ...
