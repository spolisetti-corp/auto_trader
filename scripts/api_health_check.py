#!/usr/bin/env python3
"""
API Health Check — verifies all 5 API keys are working with live data.
Run via GitHub Actions: Actions → API Health Check → Run workflow
"""

import os
import sys
import json
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = "PASS"
FAIL = "FAIL"
results = {}


def check_alpaca():
    try:
        import alpaca_trade_api as tradeapi
        api = tradeapi.REST(
            os.getenv("APCA_API_KEY_ID"),
            os.getenv("APCA_API_SECRET_KEY"),
            base_url="https://paper-api.alpaca.markets",
        )
        account = api.get_account()
        return PASS, f"Account status={account.status}  equity=${float(account.equity):,.2f}  buying_power=${float(account.buying_power):,.2f}"
    except Exception as e:
        return FAIL, str(e)


def check_polygon():
    try:
        import requests
        key = os.getenv("POLYGON_API_KEY")
        url = f"https://api.polygon.io/v2/aggs/ticker/AAPL/range/1/day/2024-01-01/2024-01-05?apiKey={key}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if r.status_code != 200 or data.get("status") == "ERROR":
            return FAIL, data.get("error", r.text)
        count = data.get("resultsCount", 0)
        return PASS, f"AAPL bars returned={count}  status={data.get('status')}"
    except Exception as e:
        return FAIL, str(e)


def check_finnhub():
    try:
        import requests
        key = os.getenv("FINNHUB_API_KEY")
        url = f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={key}"
        r = requests.get(url, timeout=10)
        data = r.json()
        if "error" in data:
            return FAIL, data["error"]
        price = data.get("c", 0)
        return PASS, f"AAPL current_price=${price}  high=${data.get('h')}  low=${data.get('l')}"
    except Exception as e:
        return FAIL, str(e)


def check_eodhd():
    try:
        import requests
        key = os.getenv("EODHD_API_KEY")
        end = datetime.today().strftime("%Y-%m-%d")
        start = (datetime.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        url = f"https://eodhd.com/api/eod/AAPL.US?from={start}&to={end}&api_token={key}&fmt=json"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return FAIL, f"HTTP {r.status_code}: {r.text[:200]}"
        data = r.json()
        if not data:
            return FAIL, "Empty response — check API key or plan"
        latest = data[-1]
        return PASS, f"AAPL latest_date={latest['date']}  close=${latest['close']}  volume={latest['volume']:,}"
    except Exception as e:
        return FAIL, str(e)


def check_yfinance():
    try:
        import yfinance as yf
        ticker = yf.Ticker("AAPL")
        hist = ticker.history(period="1mo")
        if hist.empty:
            return FAIL, "No data returned"
        latest = hist.iloc[-1]
        return PASS, f"AAPL latest close=${latest['Close']:.2f}  volume={int(latest['Volume']):,}  rows={len(hist)}"
    except Exception as e:
        return FAIL, str(e)


def main():
    checks = [
        ("Alpaca (paper trading)", check_alpaca),
        ("Polygon",               check_polygon),
        ("Finnhub",               check_finnhub),
        ("EODHD",                 check_eodhd),
        ("yfinance (no key)",     check_yfinance),
    ]

    print("\n" + "=" * 70)
    print(f"  API HEALTH CHECK  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)

    all_passed = True
    for name, fn in checks:
        status, detail = fn()
        icon = "✓" if status == PASS else "✗"
        print(f"\n  [{icon}] {name}: {status}")
        print(f"       {detail}")
        results[name] = {"status": status, "detail": detail}
        if status == FAIL:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("  ALL APIS HEALTHY — system ready to trade")
    else:
        failed = [k for k, v in results.items() if v["status"] == FAIL]
        print(f"  FAILED: {', '.join(failed)}")
    print("=" * 70 + "\n")

    with open("api_health_check.json", "w") as f:
        json.dump({"timestamp": datetime.utcnow().isoformat(), "results": results}, f, indent=2)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
