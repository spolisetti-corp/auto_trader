import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AggressiveSwingConfig:
    def __init__(self):
        # Alpaca & Polygon API Configuration
        self.APCA_API_KEY_ID = os.getenv('APCA_API_KEY_ID')
        self.APCA_API_SECRET_KEY = os.getenv('APCA_API_SECRET_KEY')
        self.POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')
        self.FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
        self.EODHD_API_KEY = os.getenv('EODHD_API_KEY')

        # --- AGGRESSIVE SWING PARAMETERS ---
        self.AGGRESSIVE_POSITION_SIZE = 0.25  # 25% per position
        self.AGGRESSIVE_STOP_LOSS = 0.10      # 10% stop loss
        self.AGGRESSIVE_TAKE_PROFIT = 0.08    # 8% take profit
        self.MAX_POSITIONS = 4                # Maximum aggressive positions

        # --- RISK MANAGEMENT & CIRCUIT BREAKERS ---
        self.MAX_PORTFOLIO_RISK = 0.40        # 40% max portfolio risk
        self.MAX_DAILY_LOSS = 0.03            # 3% max daily loss limit
        self.MAX_SLIPPAGE_PCT = 0.005         # 0.5% max allowable slippage
        self.MIN_WIN_RATE = 0.70              # Required for negative R/R ratio

        # --- PDT & LIQUIDITY FILTERS ---
        self.AVOID_PDT = True                 # Block 4th trade in 5-day window
        self.MIN_DAILY_DOLLAR_VOLUME = 2000000 # $2M min daily liquidity
        self.MAX_SPREAD_PCT = 0.01            # 1% max bid/ask spread

        # --- SCANNING PARAMETERS ---
        self.MIN_MARKET_CAP = int(os.getenv('MIN_MARKET_CAP', '100000000'))
        self.MIN_MOMENTUM = float(os.getenv('MIN_MOMENTUM', '15.0'))
        self.MAX_RSI = float(os.getenv('MAX_RSI', '80'))
        self.MIN_VOLUME_RATIO = float(os.getenv('MIN_VOLUME_RATIO', '3.0'))

        # --- TARGETS ---
        self.QUARTERLY_PROFIT_TARGET = 0.875
        self.QUARTERLY_MAX_LOSS = 0.20
        self.MONTHLY_PROFIT_TARGET = 0.29
        self.WEEKLY_TARGET = round(self.MONTHLY_PROFIT_TARGET / 4, 4)  # ~7.25% per week
        self.DAILY_TARGET = 0.015

        # High-Growth Sectors
        self.AGGRESSIVE_SECTORS = [
            'Biotechnology', 'Software', 'Electric Vehicles',
            'Solar Energy', 'Cryptocurrency', 'Cloud Computing',
            'AI/Machine Learning', 'Semiconductors', 'Fintech', 'E-commerce'
        ]

        # --- MARKET SCHEDULE ---
        self.TIMEZONE = "America/New_York"
        self.SCAN_TIMES = ["07:00", "09:25", "10:30", "14:00", "15:30", "16:05"]
        self.REVIEW_TIMES = ["07:30", "12:00", "15:30", "19:30"]

        # --- ALERTING ---
        self.ALERT_WEBHOOK_URL = os.getenv('ALERT_WEBHOOK_URL', '')
        self.ALERT_EMAIL_CONFIG = {
            'smtp_server': os.getenv('ALERT_SMTP_SERVER', ''),
            'username': os.getenv('ALERT_EMAIL_USER', ''),
            'password': os.getenv('ALERT_EMAIL_PASS', ''),
            'from': os.getenv('ALERT_EMAIL_FROM', ''),
            'to': os.getenv('ALERT_EMAIL_TO', ''),
        } if os.getenv('ALERT_EMAIL_USER') else {}
        self.ENABLE_TRADE_ALERTS = True
        self.ENABLE_ERROR_ALERTS = True
        self.ENABLE_DAILY_SUMMARY = True

    def validate(self):
        """Enhanced validation for aggressive strategies"""
        errors = []
        if not all([self.APCA_API_KEY_ID, self.APCA_API_SECRET_KEY, self.POLYGON_API_KEY]):
            errors.append("Missing API Keys in .env")

        # R/R Ratio Warning (since your TP < SL)
        rr_ratio = self.AGGRESSIVE_TAKE_PROFIT / self.AGGRESSIVE_STOP_LOSS
        if rr_ratio < 1.0 and self.MIN_WIN_RATE < 0.65:
            errors.append(f"Mathematical failure: Win rate {self.MIN_WIN_RATE} too low for R/R {rr_ratio}")

        if self.AGGRESSIVE_POSITION_SIZE * self.MAX_POSITIONS > 1.0:
            errors.append("Position sizes exceed 100% of capital")

        if errors:
            raise ValueError("Config Errors: " + " | ".join(errors))
        return True

    def is_aggressive_candidate(self, stock_data):
        """Includes Liquidity and Spread checks"""
        return (
            stock_data['momentum_20d'] > self.MIN_MOMENTUM and
            stock_data['rsi'] < self.MAX_RSI and
            stock_data['volume_momentum'] > self.MIN_VOLUME_RATIO and
            stock_data['market_cap'] > self.MIN_MARKET_CAP and
            stock_data.get('dollar_volume', 0) > self.MIN_DAILY_DOLLAR_VOLUME and
            stock_data.get('spread_pct', 1.0) < self.MAX_SPREAD_PCT
        )

# Initialize and validate
config = AggressiveSwingConfig()
try:
    config.validate()
except ValueError as e:
    print(f"CRITICAL: {e}")
    exit(1)
