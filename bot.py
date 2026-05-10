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
    "XAU/USD 🥇": {"ticker": "GC=F",    "tp_gap": 8,   "sl_gap": 4},
    "BTC/USD 🪙":  {"ticker": "BTC-USD", "tp_gap": 400, "sl_gap": 200},
}

last_signal = {name: {"direction": None, "time": 0} for name in ASSETS}
market_cache = {name: {} for name in ASSETS}
COOLDOWN = 3600
last_status_time = 0
STATUS_INTERVAL = 1800  # 30 daqiqada bir holat xabari


def get_data(ticker):
    try:
        df = yf.download(tickers=ticker, period="10d", interval="5m", progress=False)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close"])
        return df
    except Exception as e:
        print(f"[{ticker}] Ma'lumot xatosi: {e}")
        return None


def compute_indicators(name, cfg):
    df = get_data(cfg["ticker"])
    if df is None or len(df) < 55:
        print(f"[{name}] Yetarli ma'lumot yo'q ({0 if df is None else len(df)} qator)")
        return None

    close = df["Close"].squeeze()

    rsi_val  = float(ta.momentum.RSIIndicator(close=close, window=14).rsi().iloc[-1])
    ema50_v  = float(ta.trend.EMAIndicator(close=close, window=50).ema_indicator().iloc[-1])

    macd_obj  = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    macd_line = macd_obj.macd()
    macd_sig  = macd_obj.macd_signal()
    macd_c    = float(macd_line.iloc[-1])
    macd_s    = float(macd_sig.iloc[-1])
    macd_pc   = float(macd_line.iloc[-2])
    macd_ps   = float(macd_sig.iloc[-2])

    price = float(close.iloc[-1])
    prev_price = float(close.iloc[-2])
    price_change = price - prev_price

    trend = "📈 BULLISH" if price > ema50_v else "📉 BEARISH"
    macd_cross_up   = macd_pc < macd_ps and macd_c > macd_s
    macd_cross_down = macd_pc > macd_ps and macd_c < macd_s

    # Ball tizimi: 3 dan 2 ta shart yetarli
    buy_score  = int(rsi_val < 42) + int(price > ema50_v) + int(macd_cross_up)
    sell_score = int(rsi_val > 58) + int(price < ema50_v) + int(macd_cross_down)

    return {
        "price": price,
        "price_change": price_change,
        "rsi": rsi_val,
        "ema50": ema50_v,
        "macd_c": macd_c,
        "macd_s": macd_s,
        "trend": trend,
        "macd_cross_up": macd_cross_up,
        "macd_cross_down": macd_cross_down,
        "buy_score": buy_score,
        "sell_score": sell_score,
    }


def analyze(name, cfg):
    global last_signal

    data = compute_indicators(name, cfg)
    if data is None:
        return

    market_cache[name] = data

    price     = data["price"]
    rsi_val   = data["rsi"]
    ema50_v   = data["ema50"]
    trend     = data["trend"]
    buy_score = data["buy_score"]
    sell_score = data["sell_score"]

    print(f"[{name}] Narx: {price:.2f} | RSI: {rsi_val:.1f} | {trend} | BUY ball: {buy_score}/3 | SELL ball: {sell_score}/3")

    now = time.time()
    tp_gap = cfg["tp_gap"]
    sl_gap = cfg["sl_gap"]

    # BUY — 3 dan kamida 2 ta shart
    if buy_score >= 2:
        if (last_signal[name]["direction"] != "BUY"
                or (now - last_signal[name]["time"]) > COOLDOWN):
            tp = price + tp_gap
            sl = price - sl_gap
            checks = (
                f"{'✅' if rsi_val < 42 else '❌'} RSI: `{rsi_val:.1f}` (< 42)\n"
                f"{'✅' if price > ema50_v else '❌'} Narx EMA50 ustida\n"
                f"{'✅' if data['macd_cross_up'] else '❌'} MACD bullish kesishdi"
            )
            msg = (f"🟢 *SIGNAL: {name}*\n\n"
                   f"📈 Yo'nalish: *BUY* ({buy_score}/3 shart)\n"
                   f"📍 Kirish: `{price:.2f}`\n"
                   f"🎯 TP: `{tp:.2f}`\n"
                   f"🛑 SL: `{sl:.2f}`\n\n"
                   f"📊 *Indikatorlar:*\n{checks}\n\n"
                   f"📉 Trend: {trend}")
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            last_signal[name] = {"direction": "BUY", "time": now}
            print(f"[{name}] ✅ BUY signali yuborildi! (ball: {buy_score}/3)")

    # SELL — 3 dan kamida 2 ta shart
    elif sell_score >= 2:
        if (last_signal[name]["direction"] != "SELL"
                or (now - last_signal[name]["time"]) > COOLDOWN):
            tp = price - tp_gap
            sl = price + sl_gap
            checks = (
                f"{'✅' if rsi_val > 58 else '❌'} RSI: `{rsi_val:.1f}` (> 58)\n"
                f"{'✅' if price < ema50_v else '❌'} Narx EMA50 ostida\n"
                f"{'✅' if data['macd_cross_down'] else '❌'} MACD bearish kesishdi"
            )
            msg = (f"🔴 *SIGNAL: {name}*\n\n"
                   f"📉 Yo'nalish: *SELL* ({sell_score}/3 shart)\n"
                   f"📍 Kirish: `{price:.2f}`\n"
                   f"🎯 TP: `{tp:.2f}`\n"
                   f"🛑 SL: `{sl:.2f}`\n\n"
                   f"📊 *Indikatorlar:*\n{checks}\n\n"
                   f"📈 Trend: {trend}")
            bot.send_message(CHAT_ID, msg, parse_mode="Markdown")
            last_signal[name] = {"direction": "SELL", "time": now}
            print(f"[{name}] ✅ SELL signali yuborildi! (ball: {sell_score}/3)")

    else:
        print(f"[{name}] Signal yo'q.")


def send_status():
    lines = ["📊 *Bozor holati (30 daqiqalik yangilanish)*\n"]
    for name, data in market_cache.items():
        if not data:
            lines.append(f"*{name}*: ma'lumot yo'q\n")
            continue
        ch = data.get("price_change", 0)
        ch_emoji = "🔼" if ch > 0 else "🔽"
        sig = last_signal[name]["direction"] or "—"
        lines.append(
            f"*{name}*\n"
            f"  💰 Narx: `{data['price']:.2f}` {ch_emoji} ({ch:+.2f})\n"
            f"  📊 RSI: `{data['rsi']:.1f}` | {data['trend']}\n"
            f"  🔔 Oxirgi signal: {sig}\n"
        )
    bot.send_message(CHAT_ID, "\n".join(lines), parse_mode="Markdown")


@bot.message_handler(commands=["status", "start"])
def handle_status(message):
    if not market_cache.get("XAU/USD 🥇"):
        bot.reply_to(message, "⏳ Ma'lumot hali yuklanmoqda, biroz kuting...")
        return
    send_status()


@bot.message_handler(commands=["help"])
def handle_help(message):
    msg = ("🤖 *Bot buyruqlari:*\n\n"
           "/status — hozirgi bozor holati\n"
           "/help — yordam\n\n"
           "Bot har 5 daqiqada XAU/USD va BTC/USD tekshiradi.\n"
           "Shart: 3 indikatordan 2 tasi signal bersa xabar yuboradi.")
    bot.reply_to(message, msg, parse_mode="Markdown")


def polling_thread():
    bot.infinity_polling(timeout=20, long_polling_timeout=10)


flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "Bot ishlayapti!", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    print("Bot ishga tushdi (RSI + EMA50 + MACD | ball tizimi 2/3)...")

    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=polling_thread, daemon=True).start()

    try:
        start_msg = (
            "✅ *Trading Bot qayta ishga tushdi!*\n\n"
            "📊 Strategiya: RSI + EMA50 + MACD (2/3 shart yetarli)\n"
            "⏱ Har 5 daqiqada tekshiriladi\n"
            "📢 Har 30 daqiqada holat xabari\n\n"
            "Juftliklar:\n"
            "  • 🥇 XAU/USD (Oltin)\n"
            "  • 🪙 BTC/USD (Bitcoin)\n\n"
            "/status — hozirgi holat\n"
            "/help — yordam"
        )
        bot.send_message(CHAT_ID, start_msg, parse_mode="Markdown")
        print("Boshlang'ich xabar yuborildi.")
    except Exception as e:
        print(f"Start xabar xatosi: {e}")

    while True:
        for name, cfg in ASSETS.items():
            try:
                analyze(name, cfg)
            except Exception as e:
                print(f"[{name}] Xato: {e}")

        if time.time() - last_status_time > STATUS_INTERVAL:
            try:
                send_status()
                last_status_time = time.time()
            except Exception as e:
                print(f"Status xabar xatosi: {e}")

        time.sleep(300)
