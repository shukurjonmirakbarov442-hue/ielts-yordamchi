"""
IELTS Writing Task 2 AI baholovchi Telegram bot
Foydalanuvchi insho yuboradi -> bot Gemini orqali baholaydi -> band ball va tuzatishlarni qaytaradi
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Muhit oʻzgaruvchilaridan tokenlarni olamiz (xavfsizlik uchun kodga yozmaymiz)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

EVALUATION_PROMPT = """Sen tajribali IELTS examiner san. Foydalanuvchi yuborgan Writing Task 2
inshosini rasmiy IELTS mezonlari boʻyicha baholaysan:

1. Task Response (mavzuga javob toʻliqligi)
2. Coherence & Cohesion (fikrlar bogʻlanishi, paragraflar tuzilishi)
3. Lexical Resource (soʻz boyligi)
4. Grammatical Range & Accuracy (grammatika)

Har bir mezon boʻyicha 1-9 band ball ber, qisqa izoh yoz (nima yaxshi, nima yomon).
Oxirida umumiy band ball (4 mezon oʻrtachasi) va ENG MUHIM 3 ta tuzatish kerak
boʻlgan joyni aniq misol bilan koʻrsat (original jumla -> tuzatilgan jumla).

Javobni oʻzbek tilida yoz, lekin insho ingliz tilida qoladi.
Qisqa va aniq boʻl - talaba darhol tushunadigan tilda yoz.

Foydalanuvchining inshosi:
{essay}
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! Men IELTS Writing Task 2 inshongizni baholayman.\n\n"
        "Inshoyingizni shu yerga yuboring (kamida 150 soʻz), men band ball va "
        "tuzatishlarni qaytaraman."
    )


async def evaluate_essay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    essay = update.message.text
    word_count = len(essay.split())

    if word_count < 50:
        await update.message.reply_text(
            "Insho juda qisqa koʻrinyapti. Toʻliq Writing Task 2 inshongizni yuboring "
            "(kamida 250 soʻz tavsiya etiladi)."
        )
        return

    await update.message.reply_text("Baholamoqdaman, biroz kuting...")

    try:
        response = model.generate_content(
            EVALUATION_PROMPT.format(essay=essay)
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        logger.error(f"Xatolik: {e}")
        await update.message.reply_text(
            "Kechirasiz, xatolik yuz berdi. Birozdan keyin qayta urinib koʻring."
        )


def main():
    if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
        raise ValueError("TELEGRAM_BOT_TOKEN va GEMINI_API_KEY muhit oʻzgaruvchilarini sozlang")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, evaluate_essay))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
