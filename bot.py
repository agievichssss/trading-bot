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

SYMBOL = "BTC-USDT"
TIMEFRAME = "15m"
TIMEFRAME_HIGHER = "1h"

app = Flask(__name__)

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
        print("✅ Telegram отправлено", flush=True)
    except Exception as e:
        print(f"❌ Ошибка Telegram: {e}", flush=True)

def get_candles(timeframe, limit=200):
    """Получение свечей с BingX Futures API"""
    url = "https://open-api.bingx.com/openApi/swap/v3/quote/klines"
    params = {"symbol": SYMBOL, "interval": timeframe, "limit": limit}
    headers = {"X-BX-APIKEY": API_KEY}
    
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        
        if data.get("code") != 0:
            print(f"❌ API error: {data.get('msg')}", flush=True)
            return None
        
        candles = data.get("data")
        if not candles:
            print("❌ No data", flush=True)
            return None
        
        # Прямое создание DataFrame без срезов
        df_list = []
        for c in candles:
            df_list.append({
                'time': c[0],
                'open': float(c[1]),
                'high': float(c[2]),
                'low': float(c[3]),
                'close': float(c[4])
            })
        
        df = pd.DataFrame(df_list)
        return df
        
    except Exception as e:
        print(f"❌ Ошибка: {e}", flush=True)
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
    print("🚀 Мониторинг запущен", flush=True)
    print(f"📊 {SYMBOL} | {TIMEFRAME} | SMA5(0) vs SMA20(5)", flush=True)
    print("-" * 50, flush=True)
    
    last_signal = None
    
    while True:
        try:
            df_15m = get_candles(TIMEFRAME, 200)
            if df_15m is None:
                print("⚠️ Нет данных 15m", flush=True)
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
                        msg = f"""🟢 ЗОЛОТОЙ КРЕСТ (лонг) 🟢

📊 {SYMBOL} | {TIMEFRAME}
💰 Цена: {price:.0f}

📈 SMA5(0): {fast_val:.2f}
📉 SMA20(5): {slow_val:.2f}

📊 Тренд H1: ВВЕРХ (бычий)
✅ Сигнал разрешен

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                    else:
                        msg = f"""🔴 КРЕСТ СМЕРТИ (шорт) 🔴

📊 {SYMBOL} | {TIMEFRAME}
💰 Цена: {price:.0f}

📈 SMA5(0): {fast_val:.2f}
📉 SMA20(5): {slow_val:.2f}

📊 Тренд H1: ВНИЗ (медвежий)
✅ Сигнал разрешен

🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
                    
                    send_telegram(msg)
                    print(f"✅ {signal.upper()} | Цена={price:.0f} | H1={h1_trend}", flush=True)
                    last_signal = signal
                else:
                    print(f"⚠️ {signal} заблокирован: H1={h1_trend}", flush=True)
            
            print(".", end="", flush=True)
            time.sleep(60)
            
        except Exception as e:
            print(f"\n❌ Ошибка: {e}", flush=True)
            time.sleep(60)

@app.route('/')
def home():
    return "Bot is running!"

thread = threading.Thread(target=monitor)
thread.daemon = True
thread.start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
