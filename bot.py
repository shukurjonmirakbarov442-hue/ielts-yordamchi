import os
import asyncio
import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
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
RENDER_EXTERNAL_URL = os.environ.get(
    "RENDER_EXTERNAL_URL",
    "https://ielts-yordamchi.onrender.com"
)

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN topilmadi")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY topilmadi")


# =========================
# GEMINI
# =========================
genai.configure(api_key=GEMINI_API_KEY)

GEMINI_MODEL_NAME = "gemini-3.8-flash"
model = genai.GenerativeModel(GEMINI_MODEL_NAME)


# =========================
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Salom! Men IELTS Yordamchi botiman.\n\n"
        "📝 Writing Task 2 inshongizni yuboring.\n\n"
        "Men sizga:\n"
        "• Task Response\n"
        "• Coherence & Cohesion\n"
        "• Lexical Resource\n"
        "• Grammar\n"
        "• Overall Band\n"
        "• Muhim xatolar va tuzatishlar\n\n"
        "bo‘yicha baho beraman."
    )


# =========================
# ESSAY EVALUATION
# =========================
async def evaluate_essay(update: Update, context: ContextTypes.DEFAULT_TYPE):

    essay = update.message.text.strip()
    word_count = len(essay.split())

    if word_count < 50:
        await update.message.reply_text(
            "⚠️ Insho juda qisqa.\n\n"
            "To‘liq IELTS Writing Task 2 inshosini yuboring.\n"
            "Tavsiya: kamida 250 so‘z."
        )
        return

    await update.message.reply_text(
        "⏳ Inshongiz baholanmoqda..."
    )

    prompt = f"""
Sen tajribali IELTS Writing Task 2 examinerisan.

Quyidagi inshoni IELTS mezonlari bo‘yicha bahola.

1. Task Response
2. Coherence & Cohesion
3. Lexical Resource
4. Grammatical Range & Accuracy

Har bir mezon uchun:
- 1 dan 9 gacha band score ber.
- Juda qisqa va tushunarli izoh ber.

Keyin:
- Overall Band Score ber.
- Eng muhim 3 ta xatoni ko‘rsat.
- Har bir xato uchun:
  Original → Corrected
  formatidan foydalan.

Javob o‘zbek tilida bo‘lsin.
Inglizcha jumlalarni tarjima qilma.
Javobni ortiqcha cho‘zma.

INSHO:

{essay}
"""

    try:
        response = await asyncio.to_thread(
            model.generate_content,
            prompt,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 1200,
            },
        )

        await update.message.reply_text(response.text)

    except Exception as e:

        logger.exception("Gemini xatosi")

        error_text = str(e)

        if "429" in error_text:
            await update.message.reply_text(
                "⚠️ AI hozir band. Taxminan 1 daqiqadan keyin qayta urinib ko‘ring."
            )
        else:
            await update.message.reply_text(
                "❌ Baholash vaqtida xatolik yuz berdi.\n\n"
                "Birozdan keyin qayta urinib ko‘ring."
            )


# =========================
# MAIN
# =========================
def main():

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            evaluate_essay
        )
    )

    port = int(os.environ.get("PORT", 10000))

    webhook_url = RENDER_EXTERNAL_URL.rstrip("/")

    logger.info("IELTS bot ishga tushmoqda...")
    logger.info("Webhook URL: %s", webhook_url)
    logger.info("Gemini modeli: %s", GEMINI_MODEL_NAME)

    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="",
        webhook_url=webhook_url,
    )


if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()