# Automated Trading System

A comprehensive automated trading system for momentum swing trading with built-in risk management and pattern day trading avoidance.

## Features

- **Momentum Stock Scanner**: Identifies high-momentum stocks using technical indicators
- **Pattern Day Trading Avoidance**: Limits trades to avoid PDT restrictions
- **Trailing Stop Loss**: Automatically sells positions at 15% drawdown from peak
- **Take Profit**: Automatically takes profits at 30% gains with trailing
- **Risk Management**: Position sizing, daily loss limits, and risk metrics
- **Real-time Monitoring**: Performance tracking, alerts, and reporting
- **Automated Execution**: Complete automation from scanning to execution

## Requirements

- Python 3.8+
- Alpaca trading account (paper or live)
- API keys for Alpaca

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

## Configuration

Edit `.env` file with your settings:

- `APCA_API_KEY_ID`: Your Alpaca API key
- `APCA_API_SECRET_KEY`: Your Alpaca secret key
- `APCA_BASE_URL`: Alpaca API URL (paper or live)
- `INITIAL_CAPITAL`: Starting capital
- `MAX_POSITION_SIZE`: Maximum position size per trade (default: 10%)
- `TRAILING_STOP_LOSS_PCT`: Trailing stop loss percentage (default: 15%)
- `TAKE_PROFIT_PCT`: Take profit percentage (default: 30%)
- `MAX_TRADES_PER_DAY`: Maximum trades per day for PDT avoidance (default: 3)

## Usage

### Start the Automated Trading System

```bash
python automated_trader.py
```

The system will:
1. Run pre-market scans at 8:00 AM
2. Execute trades at market open (9:30 AM)
3. Monitor positions every 15 minutes
4. Generate end-of-day reports at 4:00 PM

### Manual Components

#### Market Scanner
```python
from market_scanner import MarketScanner
scanner = MarketScanner()
momentum_stocks = scanner.get_momentum_stocks()
```

#### Trading Engine
```python
from trading_engine import TradingEngine
engine = TradingEngine()
engine.initialize()
```

#### Risk Manager
```python
from risk_manager import RiskManager
risk_manager = RiskManager()
```

## Trading Strategy

### Momentum Criteria
- 20-day momentum > 5%
- RSI > 50
- Volume 20% above average
- Price above 20-day moving average
- Volatility < 5%

### Risk Management
- Maximum 10% of portfolio per position
- 15% trailing stop loss
- 30% take profit with trailing
- Maximum 3 trades per day (PDT avoidance)
- 2% maximum daily loss

### Position Management
- Automatic stop loss and take profit execution
- Real-time position monitoring
- Risk-reward ratio validation

## Monitoring and Reporting

The system provides:
- Real-time logging
- Daily performance reports
- Performance charts (HTML)
- Trading alerts
- Risk metrics dashboard

## File Structure

```
├── automated_trader.py    # Main trading application
├── market_scanner.py      # Stock scanning logic
├── trading_engine.py      # Order execution and management
├── risk_manager.py        # Risk management rules
├── monitoring.py          # Performance tracking and alerts
├── config.py             # Configuration management
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Risk Warning

This system is for educational purposes. Trading involves substantial risk of loss. Always:
- Start with paper trading
- Use proper position sizing
- Monitor your positions
- Understand the risks involved

## Support

For issues or questions:
1. Check the logs in `trading.log`
2. Review your API configuration
3. Verify market hours and trading permissions

## License

This project is for educational use only. Use at your own risk.
