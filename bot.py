import os
import time
import threading
import telebot
import yfinance as yf
import pandas as pd
import ta
from flask import Flask

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi!")
if not CHAT_ID:
    raise ValueError("CHAT_ID topilmadi!")

bot = telebot.TeleBot(TOKEN)

ASSETS = {
    "XAU/USD": {"ticker": "GC=F",    "tp_gap": 8,   "sl_gap": 4},
    "BTC/USD": {"ticker": "BTC-USD", "tp_gap": 400, "sl_gap": 200},
}

last_signal = {name: {"direction": None, "time": 0} for name in ASSETS}
market_cache = {}
COOLDOWN = 3600


def get_data(ticker):
    try:
        df = yf.download(tickers=ticker, period="10d", interval="5m", progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df.dropna(subset=["Close"])
    except Exception as e:
        print(f"[{ticker}] Ma'lumot xatosi: {e}")
        return None


def analyze(name, cfg):
    df = get_data(cfg["ticker"])
    if df is None or len(df) < 55:
        print(f"[{name}] Ma'lumot yetarli emas")
        return

    close = df["Close"].squeeze()

    rsi_val  = float(ta.momentum.RSIIndicator(close=close, window=14).rsi().iloc[-1])
    ema50_v  = float(ta.trend.EMAIndicator(close=close, window=50).ema_indicator().iloc[-1])
    macd_obj = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    ml       = macd_obj.macd()
    ms       = macd_obj.macd_signal()
    macd_c, macd_s   = float(ml.iloc[-1]), float(ms.iloc[-1])
    macd_pc, macd_ps = float(ml.iloc[-2]), float(ms.iloc[-2])

    price = float(close.iloc[-1])
    atr   = float(ta.volatility.AverageTrueRange(
        df["High"].squeeze(), df["Low"].squeeze(), close, window=14
    ).average_true_range().iloc[-1])

    market_cache[name] = {"price": price, "rsi": rsi_val, "ema50": ema50_v}

    print(f"[{name}] Narx: {price:.2f} | RSI: {rsi_val:.1f} | ATR: {atr:.2f}")

    buy_score  = int(rsi_val < 42) + int(price > ema50_v) + int(macd_pc < macd_ps and macd_c > macd_s)
    sell_score = int(rsi_val > 58) + int(price < ema50_v) + int(macd_pc > macd_ps and macd_c < macd_s)

    now = time.time()
    tp_gap = max(cfg["tp_gap"], round(atr * 1.5, 2))
    sl_gap = max(cfg["sl_gap"], round(atr * 0.8, 2))

    if buy_score >= 2:
        if last_signal[name]["direction"] != "BUY" or (now - last_signal[name]["time"]) > COOLDOWN:
            tp = round(price + tp_gap, 2)
            sl = round(price - sl_gap, 2)
            rr = round(tp_gap / sl_gap, 1)
            msg = (
                f"🟢 *{name} — BUY SIGNAL*\n\n"
                f"📍 Kirish: `{price:.2f}`\n"
                f"🎯 TP: `{tp:.2f}` (+{tp_gap:.1f})\n"
                f"🛑 SL: `{sl:.2f}` (-{sl_gap:.1f})\n"
                f"⚖️ Risk/Reward: 1:{rr}\n\n"
                f"📊 RSI: `{rsi_val:.1f}` | Ball: {buy_score}/3"
            )
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            last_signal[name] = {"direction": "BUY", "time": now}
            print(f"[{name}] ✅ BUY signal yuborildi!")

    elif sell_score >= 2:
        if last_signal[name]["direction"] != "SELL" or (now - last_signal[name]["time"]) > COOLDOWN:
            tp = round(price - tp_gap, 2)
            sl = round(price + sl_gap, 2)
            rr = round(tp_gap / sl_gap, 1)
            msg = (
                f"🔴 *{name} — SELL SIGNAL*\n\n"
                f"📍 Kirish: `{price:.2f}`\n"
                f"🎯 TP: `{tp:.2f}` (-{tp_gap:.1f})\n"
                f"🛑 SL: `{sl:.2f}` (+{sl_gap:.1f})\n"
                f"⚖️ Risk/Reward: 1:{rr}\n\n"
                f"📊 RSI: `{rsi_val:.1f}` | Ball: {sell_score}/3"
            )
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            last_signal[name] = {"direction": "SELL", "time": now}
            print(f"[{name}] ✅ SELL signal yuborildi!")
    else:
        print(f"[{name}] Signal yo'q (BUY:{buy_score}/3 SELL:{sell_score}/3)")


@bot.message_handler(commands=["status", "start"])
def handle_status(message):
    lines = ["📊 *Hozirgi holat:*\n"]
    for name, d in market_cache.items():
        if d:
            sig = last_signal.get(name, {}).get("direction") or "—"
            lines.append(f"*{name}*: `{d['price']:.2f}` | RSI: `{d['rsi']:.1f}` | Signal: {sig}")
    bot.reply_to(message, "\n".join(lines) or "Hali ma'lumot yo'q", parse_mode="Markdown")


@bot.message_handler(commands=["help"])
def handle_help(message):
    bot.reply_to(message,
        "🤖 *Bot buyruqlari:*\n\n"
        "/status — hozirgi narx va RSI\n"
        "/help — yordam\n\n"
        "Bot har 5 daqiqada signal tekshiradi.\n"
        "Signal kelganda: Kirish, TP va SL yuboriladi.",
        parse_mode="Markdown"
    )


flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "Bot ishlayapti!", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

def polling_thread():
    bot.infinity_polling(timeout=20, long_polling_timeout=10)


if __name__ == "__main__":
    print("Bot ishga tushdi...")
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=polling_thread, daemon=True).start()

    try:
        bot.send_message(CHAT_ID,
            "✅ *Bot yangilandi va ishga tushdi!*\n\n"
            "Signal formati:\n"
            "📍 Kirish narxi\n"
            "🎯 TP (foyda)\n"
            "🛑 SL (zarar)\n\n"
            "Har 5 daqiqada XAU/USD va BTC/USD tekshiriladi.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Start xabar: {e}")

    while True:
        for name, cfg in ASSETS.items():
            try:
                analyze(name, cfg)
            except Exception as e:
                print(f"[{name}] Xato: {e}")
        time.sleep(300)
