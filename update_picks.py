#!/usr/bin/env python3
"""
Daily stock picks updater.
Uses Yahoo Finance JSON API — no API key needed.
Run at 6:30 AM PST Mon-Fri via GitHub Actions.
"""

import json
import urllib.request
from datetime import datetime
import pytz

PST = pytz.timezone("America/Los_Angeles")
now = datetime.now(PST)

ACCOUNT_SIZE = 300
MAX_LOSS = 100

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://finance.yahoo.com/"
}

def fetch_url(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_sub1_movers():
    """
    Hits Yahoo Finance gainers screener (250 results),
    filters for: price < $1, change > 5%, volume > 2x avg, volume > 100k.
    """
    url = (
        "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        "?formatted=false&scrIds=day_gainers&count=250&region=US&lang=en-US"
    )
    try:
        data = fetch_url(url)
        quotes = data["finance"]["result"][0]["quotes"]
    except Exception as e:
        print(f"Primary screener failed: {e} — trying most actives")
        quotes = []

    # Fallback: most actives screener
    if not quotes:
        try:
            url2 = (
                "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
                "?formatted=false&scrIds=most_actives&count=250&region=US&lang=en-US"
            )
            data = fetch_url(url2)
            quotes = data["finance"]["result"][0]["quotes"]
        except Exception as e:
            print(f"Fallback screener also failed: {e}")
            return []

    stocks = []
    for q in quotes:
        try:
            price     = float(q.get("regularMarketPrice", 999))
            change    = float(q.get("regularMarketChangePercent", 0))
            volume    = int(q.get("regularMarketVolume", 0))
            avg_vol   = int(q.get("averageDailyVolume3Month", 1) or 1)
            rel_vol   = volume / avg_vol

            if price < 1.0 and change > 5 and rel_vol >= 2 and volume > 100_000:
                stocks.append({
                    "ticker":  q.get("symbol", ""),
                    "company": q.get("shortName") or q.get("symbol", ""),
                    "price":   round(price, 4),
                    "change":  round(change, 2),
                    "volume":  volume,
                    "rel_vol": round(rel_vol, 1),
                })
        except Exception:
            continue

    return sorted(stocks, key=lambda x: x["change"], reverse=True)[:3]

def build_pick(stock):
    p     = stock["price"]
    stop  = round(p * 0.88, 4)
    entry = round(p * 1.04, 4)
    tgt_lo = round(p * 1.15, 4)
    tgt_hi = round(p * 1.25, 4)

    risk_per_share = p - stop
    shares = int(min(MAX_LOSS / risk_per_share, ACCOUNT_SIZE / p))
    cost      = round(shares * p, 2)
    max_loss  = round(shares * risk_per_share, 2)
    profit    = f"${round(shares * (tgt_lo - p))}–${round(shares * (tgt_hi - p))}"

    return {
        "ticker":        stock["ticker"],
        "company":       stock["company"],
        "price":         str(p),
        "change":        f"+{stock['change']}",
        "setup":         "Momentum Breakout / Sub-$1 Catalyst",
        "entry":         f"Break above ${entry} with volume",
        "stop":          f"${stop}",
        "target":        f"${tgt_lo}–${tgt_hi}",
        "shares":        str(shares),
        "cost":          str(cost),
        "max_loss":      f"${max_loss}",
        "profit_target": profit,
        "catalyst":      (
            f"{stock['rel_vol']}x avg volume — "
            f"+{stock['change']}% on {stock['volume']:,} shares traded"
        ),
    }

def main():
    stocks = fetch_sub1_movers()
    picks  = [build_pick(s) for s in stocks]

    output = {
        "date":    now.strftime("%A, %b %d, %Y"),
        "updated": now.strftime("%I:%M %p PST"),
        "picks":   picks,
    }

    with open("picks.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Done — {len(picks)} picks written for {output['date']}")
    for p in picks:
        print(f"  {p['ticker']} ${p['price']} {p['change']}%")

if __name__ == "__main__":
    main()
