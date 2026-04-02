import time
import threading
import pandas as pd
import requests
from datetime import datetime
from flask import Flask

# ============= ВСТАВЬ СВОИ КЛЮЧИ =============
API_KEY = "CiEfuxenwEgXPwWQYsDdu09fT2uvXGnq7iH5zZiZvuVKOVa23Im6PJFldJMoOWOQMcDdz8Z6xytOSMaNritQ"
API_SECRET = "pxYOrOORA413kWJ4u9zdanJZcLdg4hxJYXpWwORIdRhHtfqb2ok7CtNsB58jgnTDeHfsiMERl7KtLQtQg"
BOT_TOKEN = "8677995560:AAH10i9hTA4yRpFf9S6_d-IlgLNHJexmbAY"
CHAT_ID = 970067275
# =============================================

SYMBOL = "BTCUSDT"
TIMEFRAME = "15m"
TIMEFRAME_HIGHER = "1h"

app = Flask(__name__)

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("✅ Telegram sent", flush=True)
    except Exception as e:
        print(f"❌ Telegram error: {e}", flush=True)

def get_candles(timeframe, limit=200):
    """BingX Spot API"""
    url = "https://open-api.bingx.com/openApi/spot/v1/market/kline"
    params = {"symbol": SYMBOL, "interval": timeframe, "limit": limit}
    headers = {"X-BX-APIKEY": API_KEY}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        
        if data.get("code") != 0:
            print(f"API error: {data.get('msg')}", flush=True)
            return None
        
        candles = data.get("data")
        if not candles:
            print("No data", flush=True)
            return None
        
        rows = []
        for c in candles:
            rows.append({
                'time': c[0],
                'close': float(c[4])
            })
        
        print(f"Got {len(rows)} candles for {timeframe}", flush=True)
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Error: {e}", flush=True)
        return None

def sma_shifted(df, period, shift):
    ma = df["close"].rolling(window=period).mean()
    if shift > 0:
        ma = ma.shift(shift)
    return ma

def check_signal(df_15m):
    if df_15m is None or len(df_15m) < 60:
        return None, None, None, None
    
    df = df_15m.copy()
    fast = sma_shifted(df, 5, 0)
    slow = sma_shifted(df, 20, 5)
    
    df["fast"] = fast
    df["slow"] = slow
    df = df.dropna().reset_index(drop=True)
    
    if len(df) < 2:
        return None, None, None, None
    
    now_fast = df["fast"].iloc[-1]
    now_slow = df["slow"].iloc[-1]
    prev_fast = df["fast"].iloc[-2]
    prev_slow = df["slow"].iloc[-2]
    price = df["close"].iloc[-1]
    
    if prev_fast <= prev_slow and now_fast > now_slow:
        return "golden", now_fast, now_slow, price
    elif prev_fast >= prev_slow and now_fast < now_slow:
        return "death", now_fast, now_slow, price
    else:
        return None, None, None, None

def get_h1_trend():
    df = get_candles(TIMEFRAME_HIGHER, 150)
    if df is None:
        return None
    
    slow = sma_shifted(df, 20, 5)
    df = df.dropna()
    
    if len(df) < 2:
        return None
    
    price = df["close"].iloc[-1]
    ma = slow.iloc[-1]
    
    if price > ma:
        return "up"
    elif price < ma:
        return "down"
    else:
        return "neutral"

def monitor():
    print("🚀 Bot started", flush=True)
    send_telegram("✅ Bot is running!")
    
    last_signal = None
    
    while True:
        try:
            df_15m = get_candles(TIMEFRAME, 200)
            if df_15m is None:
                time.sleep(60)
                continue
            
            signal, fast_val, slow_val, price = check_signal(df_15m)
            
            if signal and signal != last_signal:
                h1_trend = get_h1_trend()
                
                allow = False
                if signal == "golden" and h1_trend == "up":
                    allow = True
                elif signal == "death" and h1_trend == "down":
                    allow = True
                
                if allow and h1_trend:
                    if signal == "golden":
                        msg = f"🟢 LONG\nBTC {price:.0f}\nSMA5:{fast_val:.1f}\nSMA20:{slow_val:.1f}"
                    else:
                        msg = f"🔴 SHORT\nBTC {price:.0f}\nSMA5:{fast_val:.1f}\nSMA20:{slow_val:.1f}"
                    
                    send_telegram(msg)
                    print(f"SIGNAL: {signal} at {price}", flush=True)
                    last_signal = signal
            
            print(".", end="", flush=True)
            time.sleep(60)
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(60)

@app.route('/')
def home():
    return "Bot running"

thread = threading.Thread(target=monitor)
thread.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
