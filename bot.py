"""
IELTS Writing Task 2 AI baholovchi Telegram bot
Render webhook orqali ishlaydi
"""

import os
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

import google.generativeai as genai


# =========================
# LOGGING
# =========================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================
# ENVIRONMENT VARIABLES
# =========================

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

PORT = int(os.environ.get("PORT", 10000))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")


# =========================
# GEMINI
# =========================

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-3.8-flash")


# =========================
# IELTS PROMPT
# =========================

EVALUATION_PROMPT = """Sen tajribali IELTS examiner san.

Foydalanuvchi yuborgan Writing Task 2 inshosini rasmiy IELTS mezonlari
bo‘yicha baholaysan:

1. Task Response
2. Coherence & Cohesion
3. Lexical Resource
4. Grammatical Range & Accuracy

Har bir mezon bo‘yicha 1-9 band ball ber.

Har bir mezon uchun:
- Ball
- Nima yaxshi
- Nima yomon
- Qanday yaxshilash mumkin

Keyin:
- Overall Band Score
- Taxminiy umumiy natija
- ENG MUHIM 3 ta xatoni ko‘rsat
- Har bir xato uchun:
  Original jumla -> Tuzatilgan jumla

Qo‘shimcha:
- So‘z sonini hisobga ol
- Grammatik xatolarni aniq ko‘rsat
- Kuchli vocabulary namunalarini ko‘rsat
- IELTS uchun foydali maslahat ber

Javobni O‘ZBEK tilida yoz.
Insho ingliz tilida qoladi.

Javob qisqa, aniq va talabaga tushunarli bo‘lsin.

Foydalanuvchining inshosi:

{essay}
"""


# =========================
# /START
# =========================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "👋 Salom!\n\n"
        "Men IELTS Writing Task 2 inshongizni AI yordamida baholayman.\n\n"
        "📝 Inshoyingizni shu yerga yuboring.\n"
        "📊 Men sizga IELTS band ballini va xatolarni ko‘rsataman.\n\n"
        "Kamida 250 so‘zli Writing Task 2 inshosi tavsiya etiladi."
    )


# =========================
# ESSAY EVALUATION
# =========================

async def evaluate_essay(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not update.message or not update.message.text:
        return

    essay = update.message.text.strip()

    word_count = len(essay.split())

    if word_count < 50:
        await update.message.reply_text(
            "❌ Insho juda qisqa.\n\n"
            f"📊 Hozirgi so‘zlar soni: {word_count}\n\n"
            "Iltimos, to‘liq IELTS Writing Task 2 inshosini yuboring."
        )
        return

    await update.message.reply_text(
        "⏳ Inshongiz baholanmoqda...\n"
        "Biroz kuting."
    )

    try:
        prompt = EVALUATION_PROMPT.format(
            essay=essay
        )

        response = model.generate_content(prompt)

        if response.text:
            result = response.text

            # Telegram xabar limiti uchun bo‘lib yuborish
            max_length = 4000

            for i in range(0, len(result), max_length):
                await update.message.reply_text(
                    result[i:i + max_length]
                )

        else:
            await update.message.reply_text(
                "❌ AI javob qaytarmadi. "
                "Iltimos, qaytadan urinib ko‘ring."
            )

    except Exception as e:
        logger.error(
            "Gemini xatosi: %s",
            e,
            exc_info=True
        )

        await update.message.reply_text(
            "❌ Baholash vaqtida xatolik yuz berdi.\n\n"
            "Birozdan keyin qayta urinib ko‘ring."
        )


# =========================
# MAIN
# =========================

def main():

    if not TELEGRAM_TOKEN:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN environment variable topilmadi."
        )

    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY environment variable topilmadi."
        )

    if not RENDER_EXTERNAL_URL:
        raise ValueError(
            "RENDER_EXTERNAL_URL environment variable topilmadi."
        )

    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            evaluate_essay
        )
    )

    webhook_url = (
        f"{RENDER_EXTERNAL_URL}/{TELEGRAM_TOKEN}"
    )

    logger.info(
        "IELTS bot ishga tushmoqda..."
    )

    logger.info(
        "Webhook URL: %s",
        RENDER_EXTERNAL_URL
    )

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TELEGRAM_TOKEN,
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    import asyncio

    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
