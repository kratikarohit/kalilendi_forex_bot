import logging
import ccxt
import pandas as pd
import pandas_ta as ta
from telegram import Bot
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime
import pytz
import os

# Load credentials from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
bot = Bot(token=BOT_TOKEN)

# Set timezone
ist = pytz.timezone('Asia/Kolkata')

# Forex Pairs to Scan
pairs = ['EUR/USD', 'GBP/USD', 'USD/JPY', 'USD/CHF', 'AUD/USD', 'USD/CAD', 'NZD/USD', 'XAU/USD']
symbol_map = {p: p.replace('/', '') + '=X' for p in pairs}

def fetch_data(symbol):
    exchange = ccxt.yahoo()  # Free data workaround
    bars = exchange.fetch_ohlcv(symbol, timeframe='5m', limit=100)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def analyze(pair_name, df):
    df.ta.rsi(length=14, append=True)
    df['sma_20'] = df['close'].rolling(20).mean()

    last = df.iloc[-1]
    rsi = last['RSI_14']
    price = last['close']

    signals = []

    # SCALPING SIGNAL
    if rsi < 30 and price > last['sma_20']:
        signals.append({
            'type': 'Buy (Scalping)',
            'reason': f'RSI oversold ({rsi:.2f}) + Above SMA',
            'entry': price,
            'sl': price - (price * 0.0025),
            'tp': price + (price * 0.005)
        })

    # SWING SIGNAL
    elif rsi > 70 and price < last['sma_20']:
        signals.append({
            'type': 'Sell (Swing)',
            'reason': f'RSI overbought ({rsi:.2f}) + Below SMA',
            'entry': price,
            'sl': price + (price * 0.005),
            'tp': price - (price * 0.01)
        })

    return signals

def send_alert(pair, signal):
    now = datetime.now(ist).strftime('%d-%b %H:%M')
    message = (
        f"📢 *{signal['type']}* – {pair}\n"
        f"🎯 Entry: `{round(signal['entry'], 4)}`\n"
        f"🛑 SL: `{round(signal['sl'], 4)}`\n"
        f"🎯 TP: `{round(signal['tp'], 4)}`\n"
        f"🧠 Reason: {signal['reason']}\n"
        f"🕐 Time: {now} IST"
    )
    bot.send_message(chat_id=CHANNEL_ID, text=message, parse_mode='Markdown')

def scan_all_pairs():
    for pair, symbol in symbol_map.items():
        try:
            df = fetch_data(symbol)
            signals = analyze(pair, df)
            for sig in signals:
                send_alert(pair, sig)
        except Exception as e:
            print(f"Error on {pair}: {e}")

# Scheduler runs every 15 mins
sched = BlockingScheduler()
sched.add_job(scan_all_pairs, 'interval', minutes=15)
print("📡 Bot is running...")
scan_all_pairs()  # Run once at startup
sched.start()
