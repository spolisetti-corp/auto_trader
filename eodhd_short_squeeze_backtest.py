import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')

# ==================== EODHD SHORT INTEREST BACKTEST ====================
class EODHDShortSqueezeBacktest:
    """
    Pull real short interest data from EODHD and backtest last week
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://eodhistoricaldata.com/api"
        self.session = requests.Session()
        # Bypass proxy: GLOBAL_AGENT_HTTP_PROXY is Node.js-only; direct connection needed for EODHD
        self.session.trust_env = False

        # Date ranges
        self.today = datetime.now()
        self.last_week_start = self.today - timedelta(days=7)
        self.last_week_end = self.today
        self.lookback_period = self.today - timedelta(days=60)

    def get_exchange_symbols(self, exchange: str = "US") -> List[str]:
        url = f"{self.base_url}/exchange-symbol-list/{exchange}"
        params = {'api_token': self.api_key, 'fmt': 'json'}

        try:
            print(f"Fetching symbols from {exchange} exchange...")
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            stocks = response.json()

            symbols = []
            for stock in stocks:
                if stock.get('Type') == 'Common Stock':
                    code = stock.get('Code', '')
                    if not any(x in code for x in ['.', '-', '^', 'W', 'U', 'R']):
                        symbols.append(code)

            print(f"Found {len(symbols)} common stocks")
            return symbols[:500]

        except Exception as e:
            print(f"Error fetching symbols: {e}")
            return []

    def get_short_interest_bulk(self, symbols: List[str]) -> Dict[str, Dict]:
        print(f"\nFetching short interest data for {len(symbols)} stocks...")

        short_data = {}
        processed = 0

        for symbol in symbols:
            if processed % 20 == 0:
                print(f"Progress: {processed}/{len(symbols)}")

            data = self.get_short_interest(symbol)
            if data and data.get('short_percent_float', 0) > 0:
                short_data[symbol] = data

            processed += 1

            if processed % 20 == 0:
                time.sleep(1)

        print(f"Found {len(short_data)} stocks with short interest data")
        return short_data

    def get_short_interest(self, symbol: str) -> Optional[Dict]:
        url = f"{self.base_url}/fundamentals/{symbol}.US"
        params = {
            'api_token': self.api_key,
            'filter': 'SharesStats,Highlights'
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            shares_stats = data.get('SharesStats', {})
            highlights = data.get('Highlights', {})

            short_float = shares_stats.get('ShortPercentOfFloat')
            short_ratio = shares_stats.get('ShortRatio')
            shares_short = shares_stats.get('SharesShort')
            shares_float = shares_stats.get('SharesFloat')
            market_cap = highlights.get('MarketCapitalization', 0)

            if short_float and short_float < 1:
                short_float = short_float * 100

            if short_float and short_float > 0:
                return {
                    'short_percent_float': short_float,
                    'short_ratio': short_ratio or 0,
                    'shares_short': shares_short or 0,
                    'shares_float': shares_float or 0,
                    'market_cap': market_cap
                }

            return None

        except Exception as e:
            return None

    def get_historical_data(self, symbol: str, start_date: datetime,
                          end_date: datetime) -> Optional[pd.DataFrame]:
        url = f"{self.base_url}/eod/{symbol}.US"
        params = {
            'api_token': self.api_key,
            'from': start_date.strftime('%Y-%m-%d'),
            'to': end_date.strftime('%Y-%m-%d'),
            'period': 'd',
            'fmt': 'json'
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data:
                return None

            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            return df

        except:
            return None

    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def backtest_stock(self, symbol: str, short_data: Dict) -> Optional[Dict]:
        hist = self.get_historical_data(symbol, self.lookback_period, self.today)

        if hist is None or len(hist) < 30:
            return None

        last_week_data = hist[hist['date'] >= self.last_week_start]
        previous_data = hist[hist['date'] < self.last_week_start]

        if len(last_week_data) < 3 or len(previous_data) < 20:
            return None

        prev_closes = previous_data['close'] if 'close' in previous_data.columns else previous_data['Close']
        prev_volumes = previous_data['volume'] if 'volume' in previous_data.columns else previous_data['Volume']

        # Normalize column names
        col_map = {c.lower(): c for c in hist.columns}
        close_col = col_map.get('close', 'close')
        open_col = col_map.get('open', 'open')
        high_col = col_map.get('high', 'high')
        low_col = col_map.get('low', 'low')
        volume_col = col_map.get('volume', 'volume')

        prev_closes = previous_data[close_col]
        prev_volumes = previous_data[volume_col]

        rsi_series = self.calculate_rsi(prev_closes)
        rsi_week_start = rsi_series.iloc[-1] if not rsi_series.empty else 50

        if len(prev_closes) >= 10:
            momentum_10d = ((prev_closes.iloc[-1] - prev_closes.iloc[-11]) / prev_closes.iloc[-11]) * 100
        else:
            momentum_10d = 0

        avg_volume = prev_volumes.iloc[-20:].mean()
        week_start_volume = last_week_data[volume_col].iloc[0]
        volume_ratio_start = week_start_volume / avg_volume if avg_volume > 0 else 0

        sma_20 = prev_closes.iloc[-20:].mean()
        sma_50 = prev_closes.iloc[-50:].mean() if len(prev_closes) >= 50 else prev_closes.mean()

        week_start_price = last_week_data[close_col].iloc[0]
        week_start_open = last_week_data[open_col].iloc[0]

        entry_criteria = {
            'rsi_ok': 30 < rsi_week_start < 70,
            'momentum_ok': momentum_10d > 8.0,
            'volume_ok': volume_ratio_start > 2.0,
            'price_ok': 5 <= week_start_price <= 300,
            'market_cap_ok': short_data['market_cap'] > 100_000_000,
            'short_float_ok': short_data['short_percent_float'] > 15,
            'days_to_cover_ok': short_data['short_ratio'] > 3,
            'above_sma20': week_start_price > sma_20
        }

        criteria_passed = sum(entry_criteria.values())
        would_enter = criteria_passed >= 6

        week_end_price = last_week_data[close_col].iloc[-1]
        week_high = last_week_data[high_col].max()
        week_low = last_week_data[low_col].min()

        week_return = ((week_end_price - week_start_price) / week_start_price) * 100
        max_gain = ((week_high - week_start_price) / week_start_price) * 100
        max_loss = ((week_low - week_start_price) / week_start_price) * 100

        week_volumes = last_week_data[volume_col]
        week_avg_volume = week_volumes.mean()
        week_max_volume = week_volumes.max()
        volume_ratio_avg = week_avg_volume / avg_volume if avg_volume > 0 else 0
        volume_ratio_max = week_max_volume / avg_volume if avg_volume > 0 else 0

        daily_returns = []
        for i in range(len(last_week_data)):
            if i == 0:
                daily_ret = ((last_week_data[close_col].iloc[i] - week_start_open) / week_start_open) * 100
            else:
                daily_ret = ((last_week_data[close_col].iloc[i] - last_week_data[close_col].iloc[i-1]) /
                           last_week_data[close_col].iloc[i-1]) * 100
            daily_returns.append(daily_ret)

        best_day = max(daily_returns)
        worst_day = min(daily_returns)

        squeeze_signals = 0
        if week_return > 20:
            squeeze_signals += 4
        elif week_return > 15:
            squeeze_signals += 3
        elif week_return > 10:
            squeeze_signals += 2
        elif week_return > 5:
            squeeze_signals += 1

        if volume_ratio_max > 5:
            squeeze_signals += 3
        elif volume_ratio_max > 3:
            squeeze_signals += 2
        elif volume_ratio_max > 2:
            squeeze_signals += 1

        if any(r > 10 for r in daily_returns):
            squeeze_signals += 2

        if max_gain > 30:
            squeeze_signals += 2

        squeeze_occurred = squeeze_signals >= 5

        if would_enter:
            entry_price = week_start_price
            stop_loss = entry_price * 0.92
            target_1 = entry_price * 1.15
            target_2 = entry_price * 1.30
            target_3 = entry_price * 1.50

            hit_stop = week_low <= stop_loss
            hit_target_1 = week_high >= target_1
            hit_target_2 = week_high >= target_2
            hit_target_3 = week_high >= target_3

            if hit_stop:
                trade_result = "STOPPED OUT"
                trade_pnl = -8.0
            elif hit_target_3:
                trade_result = "TARGET 3 HIT"
                trade_pnl = 50.0
            elif hit_target_2:
                trade_result = "TARGET 2 HIT"
                trade_pnl = 30.0
            elif hit_target_1:
                trade_result = "TARGET 1 HIT"
                trade_pnl = 15.0
            else:
                trade_result = "STILL OPEN"
                trade_pnl = week_return
        else:
            trade_result = "NO ENTRY"
            trade_pnl = 0
            hit_stop = False
            hit_target_1 = False
            hit_target_2 = False
            hit_target_3 = False

        return {
            'symbol': symbol,
            'short_float_pct': round(short_data['short_percent_float'], 2),
            'days_to_cover': round(short_data['short_ratio'], 2),
            'shares_short_m': round(short_data['shares_short'] / 1_000_000, 2),
            'market_cap_m': round(short_data['market_cap'] / 1_000_000, 2),
            'week_start_price': round(week_start_price, 2),
            'rsi_week_start': round(rsi_week_start, 1),
            'momentum_10d': round(momentum_10d, 2),
            'volume_ratio_start': round(volume_ratio_start, 2),
            'above_sma20': entry_criteria['above_sma20'],
            'criteria_passed': criteria_passed,
            'would_enter': would_enter,
            'week_end_price': round(week_end_price, 2),
            'week_return_pct': round(week_return, 2),
            'max_gain_pct': round(max_gain, 2),
            'max_loss_pct': round(max_loss, 2),
            'best_day_pct': round(best_day, 2),
            'worst_day_pct': round(worst_day, 2),
            'avg_volume_m': round(avg_volume / 1_000_000, 2),
            'week_avg_volume_m': round(week_avg_volume / 1_000_000, 2),
            'volume_ratio_avg': round(volume_ratio_avg, 2),
            'volume_ratio_max': round(volume_ratio_max, 2),
            'squeeze_signals': squeeze_signals,
            'squeeze_occurred': squeeze_occurred,
            'trade_result': trade_result,
            'trade_pnl_pct': round(trade_pnl, 2),
            'hit_stop': hit_stop,
            'hit_target_1': hit_target_1,
            'hit_target_2': hit_target_2,
            'hit_target_3': hit_target_3
        }

    def run_backtest(self, min_short_float: float = 15.0) -> pd.DataFrame:
        print(f"\n{'='*100}")
        print(f"LAST WEEK SHORT SQUEEZE BACKTEST - EODHD API")
        print(f"{'='*100}")
        print(f"Backtest Period: {self.last_week_start.strftime('%Y-%m-%d')} to {self.last_week_end.strftime('%Y-%m-%d')}")
        print(f"Minimum Short Float: {min_short_float}%")
        print(f"{'='*100}\n")

        all_symbols = self.get_exchange_symbols("US")

        if not all_symbols:
            print("Failed to fetch symbols")
            return pd.DataFrame()

        short_data_dict = self.get_short_interest_bulk(all_symbols)

        high_short_stocks = {
            symbol: data for symbol, data in short_data_dict.items()
            if data['short_percent_float'] >= min_short_float
        }

        print(f"\nFound {len(high_short_stocks)} stocks with >{min_short_float}% short float")
        print(f"\nBacktesting {len(high_short_stocks)} stocks...\n")

        results = []
        total = len(high_short_stocks)

        for i, (symbol, short_data) in enumerate(high_short_stocks.items(), 1):
            print(f"[{i}/{total}] {symbol} (Short: {short_data['short_percent_float']:.1f}%)...", end=' ')

            result = self.backtest_stock(symbol, short_data)

            if result:
                if result['would_enter']:
                    print(f"ENTRY -> {result['trade_result']} ({result['trade_pnl_pct']:+.1f}%)")
                else:
                    print(f"NO ENTRY (Criteria: {result['criteria_passed']}/8)")

                results.append(result)
            else:
                print("Insufficient data")

            if i % 10 == 0:
                time.sleep(1)

        if not results:
            print("\nNo backtest results")
            return pd.DataFrame()

        df = pd.DataFrame(results)
        return df

    def generate_report(self, df: pd.DataFrame) -> str:
        if df.empty:
            return "No backtest data"

        entered_trades = df[df['would_enter'] == True]

        total_analyzed = len(df)
        total_entered = len(entered_trades)

        if total_entered == 0:
            return "No trades met entry criteria last week"

        stopped_out = len(entered_trades[entered_trades['hit_stop'] == True])
        target1_hit = len(entered_trades[entered_trades['hit_target_1'] == True])
        target2_hit = len(entered_trades[entered_trades['hit_target_2'] == True])
        target3_hit = len(entered_trades[entered_trades['hit_target_3'] == True])

        total_pnl = entered_trades['trade_pnl_pct'].sum()
        avg_pnl = entered_trades['trade_pnl_pct'].mean()
        median_pnl = entered_trades['trade_pnl_pct'].median()
        best_trade = entered_trades['trade_pnl_pct'].max()
        worst_trade = entered_trades['trade_pnl_pct'].min()

        winners = entered_trades[entered_trades['trade_pnl_pct'] > 0]
        losers = entered_trades[entered_trades['trade_pnl_pct'] < 0]

        win_rate = len(winners) / total_entered * 100 if total_entered > 0 else 0

        squeezes = entered_trades[entered_trades['squeeze_occurred'] == True]
        squeeze_avg_return = squeezes['week_return_pct'].mean() if len(squeezes) > 0 else 0

        report = f"\n{'='*100}\n"
        report += f"BACKTEST REPORT - LAST WEEK PERFORMANCE\n"
        report += f"{'='*100}\n"
        report += f"Period: {self.last_week_start.strftime('%Y-%m-%d')} to {self.last_week_end.strftime('%Y-%m-%d')}\n\n"

        report += f"UNIVERSE STATISTICS:\n"
        report += f"  Total Stocks Analyzed: {total_analyzed}\n"
        report += f"  Met Entry Criteria: {total_entered} ({total_entered/total_analyzed*100:.1f}%)\n"
        report += f"  Confirmed Squeezes: {len(squeezes)} ({len(squeezes)/total_entered*100:.1f}%)\n\n"

        report += f"TRADE PERFORMANCE:\n"
        report += f"  Total Trades: {total_entered}\n"
        report += f"  Winners: {len(winners)} ({win_rate:.1f}%)\n"
        report += f"  Losers: {len(losers)} ({len(losers)/total_entered*100:.1f}%)\n"
        report += f"  Stopped Out: {stopped_out} ({stopped_out/total_entered*100:.1f}%)\n\n"

        report += f"TARGET HIT RATES:\n"
        report += f"  Target 1 (15%): {target1_hit}/{total_entered} ({target1_hit/total_entered*100:.1f}%)\n"
        report += f"  Target 2 (30%): {target2_hit}/{total_entered} ({target2_hit/total_entered*100:.1f}%)\n"
        report += f"  Target 3 (50%): {target3_hit}/{total_entered} ({target3_hit/total_entered*100:.1f}%)\n\n"

        report += f"P&L STATISTICS:\n"
        report += f"  Total P&L: {total_pnl:+.2f}%\n"
        report += f"  Average P&L: {avg_pnl:+.2f}%\n"
        report += f"  Median P&L: {median_pnl:+.2f}%\n"
        report += f"  Best Trade: {best_trade:+.2f}%\n"
        report += f"  Worst Trade: {worst_trade:+.2f}%\n\n"

        if len(squeezes) > 0:
            report += f"SQUEEZE PERFORMANCE:\n"
            report += f"  Squeeze Events: {len(squeezes)}\n"
            report += f"  Avg Return: {squeeze_avg_return:+.2f}%\n"
            report += f"  Squeeze Detection Rate: {len(squeezes)/total_entered*100:.1f}%\n\n"

        report += f"{'='*100}\n"
        report += f"TOP 10 WINNING TRADES\n"
        report += f"{'='*100}\n\n"

        top10 = entered_trades.sort_values('trade_pnl_pct', ascending=False).head(10)

        for idx, row in top10.iterrows():
            report += f"{'─'*80}\n"
            report += f"{row['symbol']} - {row['trade_result']} ({row['trade_pnl_pct']:+.2f}%)\n"
            report += f"{'─'*80}\n"
            report += f"Short Float: {row['short_float_pct']:.1f}% | Days to Cover: {row['days_to_cover']:.1f}\n"
            report += f"Entry: ${row['week_start_price']:.2f} -> ${row['week_end_price']:.2f}\n"
            report += f"Max Gain: {row['max_gain_pct']:+.2f}% | Max Loss: {row['max_loss_pct']:+.2f}%\n"
            report += f"Volume: {row['volume_ratio_max']:.2f}x peak\n"
            report += f"Squeeze: {'YES' if row['squeeze_occurred'] else 'NO'}\n\n"

        report += f"{'='*100}\n"
        report += f"KEY INSIGHTS\n"
        report += f"{'='*100}\n\n"

        high_short = entered_trades[entered_trades['short_float_pct'] > 20]
        if len(high_short) > 0:
            report += f"1. High Short Float (>20%) Trades:\n"
            report += f"   Count: {len(high_short)}\n"
            report += f"   Win Rate: {len(high_short[high_short['trade_pnl_pct'] > 0])/len(high_short)*100:.1f}%\n"
            report += f"   Avg Return: {high_short['trade_pnl_pct'].mean():+.2f}%\n\n"

        high_vol = entered_trades[entered_trades['volume_ratio_max'] > 3]
        if len(high_vol) > 0:
            report += f"2. High Volume (>3x) Trades:\n"
            report += f"   Count: {len(high_vol)}\n"
            report += f"   Win Rate: {len(high_vol[high_vol['trade_pnl_pct'] > 0])/len(high_vol)*100:.1f}%\n"
            report += f"   Avg Return: {high_vol['trade_pnl_pct'].mean():+.2f}%\n\n"

        best_combo = entered_trades[
            (entered_trades['short_float_pct'] > 20) &
            (entered_trades['volume_ratio_max'] > 3) &
            (entered_trades['momentum_10d'] > 8)
        ]
        if len(best_combo) > 0:
            report += f"3. Optimal Setup (Short>20%, Vol>3x, Mom>8%):\n"
            report += f"   Count: {len(best_combo)}\n"
            report += f"   Win Rate: {len(best_combo[best_combo['trade_pnl_pct'] > 0])/len(best_combo)*100:.1f}%\n"
            report += f"   Avg Return: {best_combo['trade_pnl_pct'].mean():+.2f}%\n\n"

        report += f"{'='*100}\n"

        return report


# ==================== MAIN EXECUTION ====================
def main():
    import os

    # Load API key from environment or .env file
    api_key = os.environ.get('EODHD_API_KEY', '')

    if not api_key:
        # Try reading from .env file
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('EODHD_API_KEY='):
                        api_key = line.split('=', 1)[1].strip()
                        break

    if not api_key:
        print("ERROR: EODHD_API_KEY not found in environment or .env file")
        return None

    print(f"Using EODHD API key: {api_key[:8]}...")

    min_short = 15.0

    backtest = EODHDShortSqueezeBacktest(api_key)
    results = backtest.run_backtest(min_short_float=min_short)

    if not results.empty:
        report = backtest.generate_report(results)
        print(report)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        all_file = f'backtest_all_{timestamp}.csv'
        results.to_csv(all_file, index=False)
        print(f"\nAll results saved: {all_file}")

        entered = results[results['would_enter'] == True]
        if not entered.empty:
            entered_file = f'backtest_trades_{timestamp}.csv'
            entered.to_csv(entered_file, index=False)
            print(f"Entered trades saved: {entered_file}")

            winners = entered[entered['trade_pnl_pct'] > 0]
            if not winners.empty:
                winners_file = f'backtest_winners_{timestamp}.csv'
                winners.to_csv(winners_file, index=False)
                print(f"Winners saved: {winners_file}")

        if not entered.empty:
            print(f"\n{'='*100}")
            print("QUICK SUMMARY - ENTERED TRADES")
            print(f"{'='*100}")
            summary_cols = ['symbol', 'short_float_pct', 'trade_pnl_pct',
                           'max_gain_pct', 'volume_ratio_max', 'trade_result']
            print(entered.sort_values('trade_pnl_pct', ascending=False).head(15)[summary_cols].to_string(index=False))

    return results


if __name__ == "__main__":
    results = main()
