# Koyeb.com ga deploy qilish (Bepul, 24/7)

## 1. GitHub ga yuklash

1. [github.com](https://github.com) ga kiring (bepul ro'yxatdan o'ting)
2. "New repository" bosing → nom bering (masalan: `trading-bot`)
3. Quyidagi 3 ta faylni yuklang:
   - `bot.py`
   - `Dockerfile`
   - `requirements.txt`

## 2. Koyeb.com da deploy

1. [koyeb.com](https://koyeb.com) ga kiring → **"Sign up for free"**
2. Dashboard → **"Create Service"** bosing
3. **"GitHub"** tanlang → repozitoriyangizni tanlang
4. Runtime: **"Docker"** avtomatik aniqlanadi
5. **"Environment variables"** bo'limiga quyidagilarni kiriting:

   | Key | Value |
   |-----|-------|
   | BOT_TOKEN | (Telegram bot tokeningiz) |
   | CHAT_ID | (Telegram chat ID) |

6. **"Deploy"** bosing — tayyor!

## Natija
- Bot 24/7 ishlaydi
- Bepul (Koyeb hobby plan)
- To'xtamaydi, uxlamaydi
