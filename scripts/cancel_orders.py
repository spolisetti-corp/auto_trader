import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

"""
CANCEL ALL UNEXECUTED (PENDING) ORDERS
Clean up any pending orders before live trading
"""

import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def cancel_all_pending_orders():
    """Cancel all pending orders on Alpaca paper account"""
    from core.trading_engine import SwingTradingEngine
    
    logger.info("=" * 60)
    logger.info("CANCELING ALL PENDING ORDERS")
    logger.info("=" * 60)
    
    # Initialize engine
    engine = SwingTradingEngine(paper_trading=True)
    
    if not engine.initialize():
        logger.error("Failed to initialize trading engine")
        return False
    
    # Get all orders
    try:
        # Get all open (pending) orders
        open_orders = engine.api.list_orders(status='open')
        pending_orders = engine.api.list_orders(status='pending')
        accepted_orders = engine.api.list_orders(status='accepted')
        new_orders = engine.api.list_orders(status='new')
        
        all_pending = list(open_orders) + list(pending_orders) + list(accepted_orders) + list(new_orders)
        
        # Remove duplicates by order ID
        seen_ids = set()
        unique_pending = []
        for order in all_pending:
            if order.id not in seen_ids:
                seen_ids.add(order.id)
                unique_pending.append(order)
        
        logger.info(f"Found {len(unique_pending)} pending/unexecuted orders")
        
        if not unique_pending:
            logger.info("No pending orders to cancel")
            return True
        
        # List all pending orders
        logger.info("\nPending Orders:")
        logger.info("-" * 60)
        for i, order in enumerate(unique_pending, 1):
            logger.info(f"{i}. {order.symbol}")
            logger.info(f"   Order ID: {order.id}")
            logger.info(f"   Side: {order.side}")
            logger.info(f"   Qty: {order.qty}")
            logger.info(f"   Status: {order.status}")
            logger.info(f"   Submitted: {order.submitted_at}")
            logger.info("")
        
        # Cancel all pending orders
        canceled_count = 0
        failed_count = 0
        
        logger.info("Canceling orders...")
        logger.info("-" * 60)
        
        for order in unique_pending:
            try:
                engine.api.cancel_order(order.id)
                logger.info(f"✓ Canceled: {order.symbol} ({order.id[:8]}...)")
                canceled_count += 1
            except Exception as e:
                logger.error(f"✗ Failed to cancel {order.symbol}: {e}")
                failed_count += 1
        
        # Verify all canceled
        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION")
        logger.info("=" * 60)
        
        remaining_open = list(engine.api.list_orders(status='open'))
        remaining_pending = list(engine.api.list_orders(status='pending'))
        remaining_accepted = list(engine.api.list_orders(status='accepted'))
        
        total_remaining = len(remaining_open) + len(remaining_pending) + len(remaining_accepted)
        
        if total_remaining == 0:
            logger.info("✓ All pending orders successfully canceled")
            logger.info(f"  Canceled: {canceled_count}")
            logger.info(f"  Failed: {failed_count}")
        else:
            logger.warning(f"⚠ {total_remaining} orders still pending:")
            for order in remaining_open + remaining_pending + remaining_accepted:
                logger.warning(f"  - {order.symbol}: {order.status}")
        
        logger.info("\n" + "=" * 60)
        logger.info("CLEANUP COMPLETE")
        logger.info("=" * 60)
        
        # Show current positions
        positions = engine.api.list_positions()
        logger.info(f"\nCurrent Positions: {len(positions)}")
        for pos in positions:
            logger.info(f"  {pos.symbol}: {pos.qty} shares @ ${float(pos.avg_entry_price):.2f}")
        
        return failed_count == 0
        
    except Exception as e:
        logger.error(f"Error listing/canceling orders: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = cancel_all_pending_orders()
    sys.exit(0 if success else 1)
