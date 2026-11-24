#!/usr/bin/env python3
"""
Daily stock picks updater.
Run at 6:30 AM PST Mon-Fri via GitHub Actions.
Fetches top sub-$1 movers from Finviz and writes picks.json.
"""

import json
import urllib.request
import urllib.parse
import re
from datetime import datetime
import pytz

PST = pytz.timezone("America/Los_Angeles")
now = datetime.now(PST)

ACCOUNT_SIZE = 300
MAX_LOSS = 100

def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")

def fetch_sub1_movers():
    """Fetch sub-$1 gainers from Finviz screener."""
    url = "https://finviz.com/screener.ashx?v=111&f=sh_price_u1&o=-change"
    html = fetch_url(url)

    rows = re.findall(
        r'<a[^>]+class="screener-link-primary"[^>]*>([A-Z]+)</a>.*?'
        r'class="screener-link"[^>]*>([\d.]+)</.*?'
        r'([-+][\d.]+)%.*?'
        r'([\d,]+)',
        html, re.DOTALL
    )

    stocks = []
    for ticker, price, change, volume in rows[:20]:
        try:
            p = float(price)
            c = float(change)
            v = int(volume.replace(",", ""))
            if p < 1.0 and c > 10 and v > 500000:
                stocks.append({"ticker": ticker, "price": p, "change": c, "volume": v})
        except Exception:
            continue

    return sorted(stocks, key=lambda x: x["change"], reverse=True)[:3]

def calc_position(price, stop_price):
    risk_per_share = price - stop_price
    if risk_per_share <= 0:
        return 0, 0
    shares = int(min(MAX_LOSS / risk_per_share, ACCOUNT_SIZE / price))
    cost = round(shares * price, 2)
    max_loss = round(shares * risk_per_share, 2)
    return shares, cost, max_loss

def build_pick(stock):
    p = stock["price"]
    stop = round(p * 0.88, 2)        # 12% stop
    entry = round(p * 1.03, 2)       # 3% above current = breakout trigger
    target_lo = round(p * 1.15, 2)
    target_hi = round(p * 1.25, 2)
    shares = int(min(MAX_LOSS / (p - stop), ACCOUNT_SIZE / p))
    cost = round(shares * p, 2)
    max_loss_val = round(shares * (p - stop), 2)
    profit = f"${round(shares*(target_lo-p))}–${round(shares*(target_hi-p))}"

    return {
        "ticker": stock["ticker"],
        "company": stock.get("company", stock["ticker"]),
        "price": str(p),
        "change": f"+{stock['change']}",
        "setup": "Momentum Breakout / Sub-$1 Catalyst",
        "entry": f"Break above ${entry} with volume",
        "stop": f"${stop}",
        "target": f"${target_lo}–${target_hi}",
        "shares": str(shares),
        "cost": str(cost),
        "max_loss": f"${max_loss_val}",
        "profit_target": profit,
        "catalyst": f"Top gainer today — +{stock['change']}% on {stock['volume']:,} volume"
    }

def main():
    stocks = fetch_sub1_movers()

    picks = [build_pick(s) for s in stocks]

    date_str = now.strftime("%A, %b %d, %Y")
    updated_str = now.strftime("%I:%M %p PST")

    output = {
        "date": date_str,
        "updated": updated_str,
        "picks": picks if picks else []
    }

    with open("picks.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Done — {len(picks)} picks written for {date_str}")

if __name__ == "__main__":
    main()
