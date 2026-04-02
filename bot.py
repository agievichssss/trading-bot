import time
import threading
import pandas as pd
import requests
from datetime import datetime
from flask import Flask

# ============= ВСТАВЬ СВОИ КЛЮЧИ =============
API_KEY = "YbfZY3ZlejMJePdVGJUlc50HpaRpNSRSyBlsdnHJXgJBkkSE0fVbu41TPbI6vwFDEdZspc4jpB450LTXA"
API_SECRET = "MiGWRJ9THxLRSLVzF0Dzg5QPKU7UuFUIKZEIMYiizypvy7pVAPbU9YkksOMZLhVTrd1mRCF4djGKp4igMrA"
BOT_TOKEN = "8677995560:AAH10i9hTA4yRpFf9S6_d-IlgLNHJexmbAY"
CHAT_ID = 970067275
# =============================================

# Пробуй оба варианта символа:
SYMBOL = "BTCUSDT"        # Без дефиса (попробуй сначала этот)
# SYMBOL = "BTC-USDT"     # С дефисом (если первый не работает)
TIMEFRAME = "15m"

app = Flask(__name__)

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("✅ Telegram sent", flush=True)
    except Exception as e:
        print(f"❌ Telegram error: {e}", flush=True)

def get_candles(timeframe, limit=200):
    """BingX Futures API с полной отладкой"""
    url = "https://open-api.bingx.com/openApi/swap/v3/quote/klines"
    params = {
        "symbol": SYMBOL,
        "interval": timeframe,
        "limit": limit
    }
    headers = {"X-BX-APIKEY": API_KEY}
    
    print(f"\n🔍 DEBUG: Запрос к API", flush=True)
    print(f"   URL: {url}", flush=True)
    print(f"   Symbol: {SYMBOL}", flush=True)
    print(f"   Interval: {timeframe}", flush=True)
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"   HTTP Status: {r.status_code}", flush=True)
        
        data = r.json()
        
        # ПОЛНАЯ ОТЛАДКА: печатаем весь ответ
        print(f"📦 FULL API RESPONSE:", flush=True)
        print(data, flush=True)
        
        if data.get("code") != 0:
            print(f"❌ API error code: {data.get('code')}", flush=True)
            print(f"   Message: {data.get('msg')}", flush=True)
            return None
        
        candles = data.get("data")
        if not candles:
            print("❌ No data in 'data' field", flush=True)
            print(f"   Response keys: {data.keys()}", flush=True)
            return None
        
        print(f"✅ Got {len(candles)} candles", flush=True)
        if len(candles) > 0:
            print(f"   First candle: {candles[0]}", flush=True)
            print(f"   Last candle: {candles[-1]}", flush=True)
        
        rows = []
        for c in candles:
            rows.append({
                'time': c[0],
                'close': float(c[4])
            })
        
        return pd.DataFrame(rows)
        
    except Exception as e:
        print(f"❌ Exception: {e}", flush=True)
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
    
    print(f"📊 fast={now_fast:.2f} slow={now_slow:.2f}", flush=True)
    
    if prev_fast <= prev_slow and now_fast > now_slow:
        print("🟢 GOLDEN CROSS", flush=True)
        return "golden", now_fast, now_slow, price
    elif prev_fast >= prev_slow and now_fast < now_slow:
        print("🔴 DEATH CROSS", flush=True)
        return "death", now_fast, now_slow, price
    else:
        return None, None, None, None

def monitor():
    print("🚀 Bot started (Futures API with DEBUG)", flush=True)
    send_telegram("✅ Bot is running! (отладочная версия)")
    
    last_signal = None
    
    while True:
        try:
            df = get_candles(TIMEFRAME, 200)
            if df is None:
                print("⚠️ No data, waiting...", flush=True)
                time.sleep(60)
                continue
            
            signal, fast_val, slow_val, price = check_signal(df)
            
            if signal and signal != last_signal:
                if signal == "golden":
                    msg = f"🟢 LONG\nBTC {price:.0f}\nSMA5:{fast_val:.1f}\nSMA20:{slow_val:.1f}"
                else:
                    msg = f"🔴 SHORT\nBTC {price:.0f}\nSMA5:{fast_val:.1f}\nSMA20:{slow_val:.1f}"
                
                send_telegram(msg)
                print(f"✅ SIGNAL: {signal} at {price}", flush=True)
                last_signal = signal
            
            print(".", end="", flush=True)
            time.sleep(60)
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(60)

@app.route('/')
def home():
    return "OK"

thread = threading.Thread(target=monitor)
thread.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
