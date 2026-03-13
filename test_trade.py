"""
TEST TRADE EXECUTION
Place one paper trade to verify system works
"""

import logging
import sys
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_trade.log')
    ]
)

logger = logging.getLogger(__name__)

def place_test_trade():
    """Place one test trade on Alpaca paper account"""
    from swing_trading_engine import SwingTradingEngine
    from aggressive_config import config
    
    logger.info("=" * 60)
    logger.info("🚀 PLACING TEST TRADE")
    logger.info("=" * 60)
    
    # Initialize engine
    engine = SwingTradingEngine(paper_trading=True)
    
    if not engine.initialize():
        logger.error("❌ Failed to initialize trading engine")
        return False
    
    # Get account info
    account = engine.api.get_account()
    portfolio_value = float(account.equity)
    
    logger.info(f"💰 Portfolio Value: ${portfolio_value:,.2f}")
    logger.info(f"💵 Buying Power: ${float(account.buying_power):,.2f}")
    
    # Check PDT status
    can_trade = engine.check_pdt_limit()
    logger.info(f"📊 PDT Status: {'CAN TRADE' if can_trade else 'BLOCKED'}")
    
    if not can_trade:
        logger.warning("⚠️ PDT limit reached - cannot place test trade")
        return False
    
    # Test trade parameters - Use a liquid stock
    symbol = "AAPL"  # Apple - highly liquid
    current_price = 180.0  # Approximate current price
    
    # Calculate position size (small test position)
    position_value = portfolio_value * 0.05  # 5% for test (smaller than normal 25%)
    shares = int(position_value / current_price)
    
    if shares < 1:
        shares = 1  # Minimum 1 share
    
    logger.info(f"📈 Test Trade: {symbol}")
    logger.info(f"   Price: ${current_price:.2f}")
    logger.info(f"   Shares: {shares}")
    logger.info(f"   Total: ${shares * current_price:.2f}")
    
    # Place market order (no extended hours for test)
    try:
        order = engine.api.submit_order(
            symbol=symbol,
            qty=shares,
            side='buy',
            type='market',
            time_in_force='day'
        )
        
        logger.info(f"✅ ORDER PLACED SUCCESSFULLY!")
        logger.info(f"   Order ID: {order.id}")
        logger.info(f"   Symbol: {order.symbol}")
        logger.info(f"   Qty: {order.qty}")
        logger.info(f"   Side: {order.side}")
        logger.info(f"   Status: {order.status}")
        
        # Update PDT tracking
        engine.daily_trades += 1
        today = datetime.now().date()
        for day_data in engine.five_day_trades:
            if day_data['date'] == today:
                day_data['trades'] += 1
                break
        
        # Verify order status
        import time
        time.sleep(2)  # Wait for fill
        
        updated_order = engine.api.get_order(order.id)
        logger.info(f"📋 Order Status After 2s: {updated_order.status}")
        
        if updated_order.filled_qty:
            logger.info(f"   Filled Qty: {updated_order.filled_qty}")
            logger.info(f"   Filled Avg Price: ${updated_order.filled_avg_price}")
        
        # Check positions
        positions = engine.api.list_positions()
        logger.info(f"📊 Current Positions: {len(positions)}")
        for pos in positions:
            logger.info(f"   {pos.symbol}: {pos.qty} shares @ ${float(pos.avg_entry_price):.2f}")
        
        logger.info("=" * 60)
        logger.info("🎉 TEST TRADE COMPLETE")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ ERROR placing order: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = place_test_trade()
    sys.exit(0 if success else 1)
