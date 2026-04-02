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

SYMBOL = "BTC-USDT"
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
    """BingX Futures API - правильный парсинг данных"""
    url = "https://open-api.bingx.com/openApi/swap/v3/quote/klines"
    params = {
        "symbol": SYMBOL,
        "interval": timeframe,
        "limit": limit
    }
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
        
        # BingX возвращает список словарей. Преобразуем в DataFrame.
        df = pd.DataFrame(candles)
        
        # Переименуем колонки, чтобы было понятно
        df.rename(columns={'close': 'close', 'open': 'open', 'high': 'high', 'low': 'low', 'volume': 'volume', 'time': 'time'}, inplace=True)
        
        # Убедимся, что цены - числа с плавающей точкой
        df["close"] = df["close"].astype(float)
        
        print(f"✅ Got {len(df)} candles for {SYMBOL}", flush=True)
        return df
        
    except Exception as e:
        print(f"Error: {e}", flush=True)
        return None

def sma_shifted(df, period, shift):
    """Скользящая средняя со сдвигом"""
    ma = df["close"].rolling(window=period).mean()
    if shift > 0:
        ma = ma.shift(shift)
    return ma

def check_signal(df_15m):
    """Проверка пересечения SMA5(0) и SMA20(5)"""
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
        print("🟢 GOLDEN CROSS - LONG SIGNAL", flush=True)
        return "golden", now_fast, now_slow, price
    elif prev_fast >= prev_slow and now_fast < now_slow:
        print("🔴 DEATH CROSS - SHORT SIGNAL", flush=True)
        return "death", now_fast, now_slow, price
    else:
        return None, None, None, None

def monitor():
    print("🚀 Bot started (Futures API - fixed parsing)", flush=True)
    send_telegram("✅ Bot is running! (фьючерсы BingX - исправлен парсинг)")
    
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
                print(f"✅ SIGNAL SENT: {signal} at {price}", flush=True)
                last_signal = signal
            
            print(".", end="", flush=True)
            time.sleep(60)
            
        except Exception as e:
            print(f"Error in monitor: {e}", flush=True)
            time.sleep(60)

@app.route('/')
def home():
    # Минимальный ответ для пинга
    return "OK"

# Запускаем мониторинг
thread = threading.Thread(target=monitor)
thread.daemon = True
thread.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
