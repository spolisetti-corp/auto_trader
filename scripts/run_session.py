#!/usr/bin/env python3
"""
Bounded trading session runner for GitHub Actions.

Runs all scheduled tasks for SESSION_DURATION minutes then exits cleanly.
Each GitHub Actions job calls this script — no daemon/infinite loop needed.

Usage:
    SESSION_DURATION=350 python scripts/run_session.py
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import AggressiveSwingTrader

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('trading.log'),
    ]
)
logger = logging.getLogger(__name__)


def register_schedules(trader):
    """Mirror the schedule from AggressiveSwingTrader.run_aggressive_system."""

    # Pre-market scans 7:00 AM - 9:45 AM
    pre_market = [
        "07:00", "07:15", "07:30", "07:45",
        "08:00", "08:15", "08:30", "08:45",
        "09:25", "09:30", "09:45",
    ]
    for t in pre_market:
        schedule.every().day.at(t).do(trader.aggressive_morning_scan)

    # Regular hours monitoring every 15 min 10:00 - 15:55
    for h in range(10, 16):
        for m in [0, 15, 30, 45]:
            schedule.every().day.at(f"{h:02d}:{m:02d}").do(trader.aggressive_monitoring)
    schedule.every().day.at("15:55").do(trader.aggressive_monitoring)

    # Post-market monitoring 16:05 - 19:15
    post_market = [
        "16:05", "16:15", "16:30", "16:45",
        "17:00", "17:15", "17:30", "17:45",
        "18:00", "18:15", "18:30", "18:45",
        "19:00", "19:15",
    ]
    for t in post_market:
        schedule.every().day.at(t).do(trader.aggressive_monitoring)

    # End of day report
    schedule.every().day.at("19:30").do(trader.end_of_day_report)

    # Options scanner (alert only) every 30 min
    options_scan_times = [
        "09:45", "10:15", "10:45", "11:15", "11:45",
        "12:15", "12:45", "13:15", "13:45", "14:15",
        "14:45", "15:15", "15:45", "16:15", "16:45",
    ]
    for t in options_scan_times:
        schedule.every().day.at(t).do(trader.scan_options_opportunities)

    # 80% options auto-trader every 30 min
    options_trade_times = [
        "09:30", "10:00", "10:30", "11:00", "11:30",
        "12:00", "12:30", "13:00", "13:30", "14:00",
        "14:30", "15:00", "15:30", "16:00", "16:30", "17:00",
    ]
    for t in options_trade_times:
        schedule.every().day.at(t).do(trader.execute_80_percent_options)

    # Self-improvement reports every 2 hours
    for t in ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00"]:
        schedule.every().day.at(t).do(trader.generate_self_improvement_report)

    # Auto-save state every 15 minutes
    schedule.every(15).minutes.do(lambda: trader.state_manager.save_current_state(trader))


def main():
    duration = int(os.getenv('SESSION_DURATION', 350))
    end_time = datetime.now() + timedelta(minutes=duration)

    logger.info("=" * 60)
    logger.info("PAPER TRADER SESSION STARTING")
    logger.info(f"Duration : {duration} min")
    logger.info(f"Ends at  : {end_time.strftime('%Y-%m-%d %H:%M %Z')}")
    logger.info(f"Timezone : {os.getenv('TZ', 'system default')}")
    logger.info("=" * 60)

    trader = AggressiveSwingTrader()
    if not trader.initialize():
        logger.error("Initialization failed — check API keys in GitHub Secrets")
        sys.exit(1)

    register_schedules(trader)

    # Run initial tasks immediately on startup
    trader.aggressive_morning_scan()
    trader.scan_options_opportunities()
    if trader.adaptive_trading:
        trader.generate_self_improvement_report()

    logger.info("Scheduler running — tasks will fire at their scheduled ET times")

    while datetime.now() < end_time:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
            time.sleep(60)

    logger.info("Session complete — saving state")
    try:
        trader.state_manager.save_current_state(trader)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

    logger.info("Session ended cleanly")


if __name__ == "__main__":
    main()
