#!/usr/bin/env python3
"""
Daily stock picks updater.
Uses Yahoo Finance JSON API — no API key needed.
Runs at 4:00 AM PST (pre-market) and 6:45 AM PST (live open) Mon-Fri.
Adds entry status: FRESH / WATCH / ENTERING / MISSED
"""

import json
import urllib.request
from datetime import datetime
import pytz

PST        = pytz.timezone("America/Los_Angeles")
now        = datetime.now(PST)
hour       = now.hour
minute     = now.minute

ACCOUNT_SIZE = 300
MAX_LOSS     = 100

# Is this the pre-market run (4 AM) or live-market run (6:45 AM+)?
IS_PREMARKET = hour < 6 or (hour == 6 and minute < 30)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept":     "application/json",
    "Referer":    "https://finance.yahoo.com/"
}

def fetch_url(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_quotes(scr_id, count=250):
    url = (
        f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
        f"?formatted=false&scrIds={scr_id}&count={count}&region=US&lang=en-US"
    )
    data = fetch_url(url)
    return data["finance"]["result"][0]["quotes"]

def fetch_sub1_movers():
    quotes = []
    for scr in ["day_gainers", "most_actives"]:
        try:
            quotes = fetch_quotes(scr)
            if quotes:
                break
        except Exception as e:
            print(f"Screener {scr} failed: {e}")

    stocks = []
    for q in quotes:
        try:
            price   = float(q.get("regularMarketPrice", 999))
            change  = float(q.get("regularMarketChangePercent", 0))
            volume  = int(q.get("regularMarketVolume", 0))
            avg_vol = int(q.get("averageDailyVolume3Month", 1) or 1)
            rel_vol = volume / avg_vol
            day_hi  = float(q.get("regularMarketDayHigh", price))
            day_lo  = float(q.get("regularMarketDayLow",  price))
            mkt_open = float(q.get("regularMarketOpen", price))

            if price < 1.0 and change > 5 and rel_vol >= 2 and volume > 100_000:
                stocks.append({
                    "ticker":   q.get("symbol", ""),
                    "company":  q.get("shortName") or q.get("symbol", ""),
                    "price":    round(price,   4),
                    "change":   round(change,  2),
                    "volume":   volume,
                    "rel_vol":  round(rel_vol, 1),
                    "day_hi":   round(day_hi,  4),
                    "day_lo":   round(day_lo,  4),
                    "mkt_open": round(mkt_open,4),
                })
        except Exception:
            continue

    return sorted(stocks, key=lambda x: x["change"], reverse=True)[:3]

def get_status(stock):
    """
    Returns a status tag and color based on how far the stock has run.
    FRESH   = pre-market, entry window not open yet
    WATCH   = just opened, up <10% from open — get ready
    ENTERING= up 10-20% from open, breakout in progress — BUY NOW
    RUNNING = up 20-40% from open — caution, late entry
    MISSED  = up 40%+ from open — do not enter
    """
    if IS_PREMARKET:
        return "FRESH — Market opens 6:30 AM PST", "fresh"

    p        = stock["price"]
    mkt_open = stock["mkt_open"]
    if mkt_open <= 0:
        mkt_open = p

    pct_from_open = ((p - mkt_open) / mkt_open) * 100

    if pct_from_open < 10:
        return "WATCH — Entry window opening now", "watch"
    elif pct_from_open < 20:
        return "ENTERING — Breakout in progress, BUY NOW", "entering"
    elif pct_from_open < 40:
        return "RUNNING — Late entry, high risk", "running"
    else:
        return "MISSED — Move already happened, do not enter", "missed"

def build_pick(stock):
    p       = stock["price"]
    stop    = round(p * 0.88, 4)
    entry   = round(p * 1.04, 4)
    tgt_lo  = round(p * 1.15, 4)
    tgt_hi  = round(p * 1.25, 4)

    risk_per_share = p - stop
    shares   = int(min(MAX_LOSS / risk_per_share, ACCOUNT_SIZE / p))
    cost     = round(shares * p, 2)
    max_loss = round(shares * risk_per_share, 2)
    profit   = f"${round(shares * (tgt_lo - p))}–${round(shares * (tgt_hi - p))}"

    status_text, status_key = get_status(stock)

    return {
        "ticker":        stock["ticker"],
        "company":       stock["company"],
        "price":         str(p),
        "change":        f"+{stock['change']}",
        "setup":         "Momentum Breakout / Sub-$1",
        "status":        status_text,
        "status_key":    status_key,
        "entry":         f"${entry}",
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
        "day_hi":        str(stock["day_hi"]),
        "day_lo":        str(stock["day_lo"]),
    }

def main():
    stocks = fetch_sub1_movers()
    picks  = [build_pick(s) for s in stocks]

    session = "PRE-MARKET" if IS_PREMARKET else "LIVE"

    output = {
        "date":    now.strftime("%A, %b %d, %Y"),
        "updated": now.strftime("%I:%M %p PST"),
        "session": session,
        "picks":   picks,
    }

    with open("picks.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"Done [{session}] — {len(picks)} picks for {output['date']}")
    for p in picks:
        print(f"  {p['ticker']} ${p['price']} {p['change']} — {p['status']}")

if __name__ == "__main__":
    main()
