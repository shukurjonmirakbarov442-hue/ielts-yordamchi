import os
import asyncio
import logging
import json
import random
import re
import tempfile

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
HISTORY_FILE = os.environ.get("HISTORY_FILE", "user_history.json")
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

TASK_2_TOPICS = [
    "Some people believe that technology makes life more complicated. To what extent do you agree or disagree?",
    "Many cities are becoming increasingly congested. What problems does this cause, and how can they be solved?",
    "Some people think children should learn a foreign language at primary school. Do the advantages outweigh the disadvantages?",
    "In many countries, people are choosing to live alone. Why is this happening, and is it a positive or negative development?",
    "Some people believe that university education should be free for everyone. To what extent do you agree or disagree?",
    "People are using cars more than ever before. What are the reasons, and what measures can reduce car use?",
    "Some people think governments should spend more money on public transport than on roads. Discuss both views and give your opinion.",
    "Online shopping is becoming more popular than shopping in stores. Is this a positive or negative development?",
    "Some people believe that students should study a wide range of subjects, while others prefer specialization. Discuss both views and give your opinion.",
    "Many people do not exercise enough. What are the causes, and how can this problem be addressed?",
]


def get_language(context: ContextTypes.DEFAULT_TYPE, user_id: int | None = None) -> str:
    language = context.user_data.get("language")
    if language:
        return language
    if user_id is not None:
        languages = load_history().get("_languages", {})
        return languages.get(str(user_id), "uz")
    return "uz"


def save_language(user_id: int, language: str) -> None:
    history = load_history()
    history.setdefault("_languages", {})[str(user_id)] = language
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as history_file:
            json.dump(history, history_file, ensure_ascii=False, indent=2)
    except OSError:
        logger.exception("Foydalanuvchi tilini saqlab bo‘lmadi")


def load_history() -> dict:
    try:
        if os.path.getsize(HISTORY_FILE) == 0:
            return {}
        with open(HISTORY_FILE, encoding="utf-8") as history_file:
            history = json.load(history_file)
            return history if isinstance(history, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError):
        logger.exception("Foydalanuvchi tarixini o‘qib bo‘lmadi")
        return {}


def record_band_score(user_id: int, score: float) -> float | None:
    history = load_history()
    user_scores = history.get(str(user_id), [])
    previous_score = user_scores[-1].get("score") if user_scores else None
    user_scores.append({"score": score})
    history[str(user_id)] = user_scores[-20:]
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as history_file:
            json.dump(history, history_file, ensure_ascii=False, indent=2)
    except OSError:
        logger.exception("Foydalanuvchi tarixini saqlab bo‘lmadi")
    return previous_score


def history_summary(user_id: int, language: str) -> str:
    scores = load_history().get(str(user_id), [])
    if not scores:
        return "Hozircha baholash natijalari yo‘q." if language == "uz" else "Пока нет результатов оценки."
    recent_scores = scores[-5:]
    heading = "So‘nggi natijalaringiz:" if language == "uz" else "Ваши последние результаты:"
    score_label = "Band" if language == "uz" else "Оценка"
    return heading + "\n" + "\n".join(
        f"{index}. {score_label} {entry['score']:.1f}"
        for index, entry in enumerate(reversed(recent_scores), start=1)
    )


def score_change_message(previous_score: float, score: float, language: str) -> str:
    if score > previous_score:
        return (
            f"\n\nO‘tgan safar {previous_score:.1f} edi, bu safar {score:.1f} — ajoyib o‘sish!"
            if language == "uz"
            else f"\n\nВ прошлый раз было {previous_score:.1f}, сейчас {score:.1f} — отличный прогресс!"
        )
    if score < previous_score:
        return (
            f"\n\nO‘tgan safar {previous_score:.1f} edi, bu safar {score:.1f}. Mashq qilishda davom eting."
            if language == "uz"
            else f"\n\nВ прошлый раз было {previous_score:.1f}, сейчас {score:.1f}. Продолжайте практиковаться."
        )
    return (
        f"\n\nNatijangiz o‘zgarmadi: {score:.1f}."
        if language == "uz"
        else f"\n\nРезультат не изменился: {score:.1f}."
    )


# =========================
# /START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uz_message = (
        "👋 Salom! Men IELTS Yordamchi botiman.\n\n"
        "📝 Writing Task 2 inshongizni yuboring. Kamida 250 so‘z yozishga harakat qiling. "
        "Men Task Response, Coherence & Cohesion, Lexical Resource va Grammar mezonlari "
        "bo‘yicha baholab, umumiy Band hamda muhim tuzatishlarni beraman.\n\n"
        "Qanday foydalaniladi:\n"
        "• Inshoni oddiy xabar sifatida yuboring.\n"
        "• /mavzu — tasodifiy IELTS mavzusi.\n"
        "• /tarix — oxirgi natijalaringiz.\n"
        "• /til uz yoki /til ru — javob tilini tanlash.\n"
        "• Speaking uchun ovozli xabar yuboring.\n\n"
        "Namuna mavzu: Some people think working from home is better than working in an office. Do you agree or disagree?\n\n"
        "Namuna kirish: Nowadays, many employees have the option to work from home. "
        "Although this arrangement can reduce commuting time, I believe that office work "
        "is still valuable because it encourages collaboration."
    )
    ru_message = (
        "👋 Здравствуйте! Я IELTS Yordamchi.\n\n"
        "📝 Отправьте эссе IELTS Writing Task 2. Рекомендуемый объем — не менее 250 слов. "
        "Я оценю Task Response, Coherence & Cohesion, Lexical Resource и Grammar, укажу "
        "общий Band и важные исправления.\n\n"
        "Как пользоваться:\n"
        "• Отправьте эссе обычным сообщением.\n"
        "• /mavzu — случайная тема IELTS.\n"
        "• /tarix — последние результаты.\n"
        "• /til uz или /til ru — выбрать язык ответа.\n"
        "• Для Speaking отправьте голосовое сообщение.\n\n"
        "Пример темы: Some people think working from home is better than working in an office. Do you agree or disagree?\n\n"
        "Пример вступления: Nowadays, many employees have the option to work from home. "
        "Although this arrangement can reduce commuting time, I believe that office work "
        "is still valuable because it encourages collaboration."
    )
    await update.message.reply_text(
        ru_message if get_language(context, update.effective_user.id) == "ru" else uz_message
    )


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = context.args[0].lower() if context.args else ""
    if language not in {"uz", "ru"}:
        await update.message.reply_text(
            "Tilni tanlang: /til uz yoki /til ru"
            if get_language(context, update.effective_user.id) == "uz"
            else "Выберите язык: /til uz или /til ru"
        )
        return
    context.user_data["language"] = language
    save_language(update.effective_user.id, language)
    await update.message.reply_text(
        "Javob tili o‘zbekcha qilib belgilandi."
        if language == "uz"
        else "Язык ответов установлен: русский."
    )


async def suggest_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    topic = random.choice(TASK_2_TOPICS)
    intro = (
        "📝 Bugungi IELTS Writing Task 2 mavzusi:"
        if get_language(context, update.effective_user.id) == "uz"
        else "📝 Тема IELTS Writing Task 2:"
    )
    await update.message.reply_text(f"{intro}\n\n{topic}")


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        history_summary(update.effective_user.id, get_language(context, update.effective_user.id))
    )


# =========================
# ESSAY EVALUATION
# =========================
async def evaluate_essay(update: Update, context: ContextTypes.DEFAULT_TYPE):

    essay = update.message.text.strip()
    word_count = len(essay.split())
    language = get_language(context, update.effective_user.id)

    if word_count < 50:
        await update.message.reply_text(
            "⚠️ Эссе слишком короткое. Отправьте полное эссе IELTS Writing Task 2, "
            "рекомендуемый объем — не менее 250 слов."
            if language == "ru"
            else "⚠️ Insho juda qisqa. To‘liq IELTS Writing Task 2 inshosini yuboring. "
            "Tavsiya: kamida 250 so‘z."
        )
        return

    await update.message.reply_text(
        (
            f"Sizning inshoyingiz: {word_count} so‘z.\n\n"
            if language == "uz"
            else f"В вашем эссе: {word_count} слов.\n\n"
        )
        + ("⏳ Inshongiz baholanmoqda..." if language == "uz" else "⏳ Ваше эссе оценивается...")
    )

    prompt = f"""
You are an experienced IELTS Writing Task 2 examiner. Evaluate this essay using Task Response, Coherence & Cohesion, Lexical Resource, and Grammatical Range & Accuracy. Give each criterion a band score from 1 to 9 and a brief explanation. Then provide the Overall Band Score and the three most important corrections in Original -> Corrected format. Reply in {"Uzbek" if language == "uz" else "Russian"}; do not translate English sentences and keep the response concise. End with exactly one machine-readable line: OVERALL_BAND: X.X (use a valid IELTS half-band score).

ESSAY:
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

        result = response.text or ""
        score_match = re.search(r"(?m)^OVERALL_BAND:\s*([1-8](?:\.0|\.5)?|9(?:\.0)?)\s*$", result)
        score = float(score_match.group(1)) if score_match else None
        if score_match:
            result = result[:score_match.start()].rstrip()
        if score is not None:
            previous_score = record_band_score(update.effective_user.id, score)
            if previous_score is not None:
                result += score_change_message(float(previous_score), score, language)
        fallback = "Natija olinmadi." if language == "uz" else "Результат не получен."
        await update.message.reply_text(result or fallback)

    except Exception as e:

        logger.exception("Gemini xatosi")

        error_text = str(e)

        if "429" in error_text:
            await update.message.reply_text(
                "⚠️ ИИ сейчас занят. Попробуйте снова примерно через минуту."
                if language == "ru"
                else "⚠️ AI hozir band. Taxminan 1 daqiqadan keyin qayta urinib ko‘ring."
            )
        else:
            await update.message.reply_text(
                "❌ При оценке произошла ошибка. Попробуйте позже."
                if language == "ru"
                else "❌ Baholash vaqtida xatolik yuz berdi. Birozdan keyin qayta urinib ko‘ring."
            )


async def evaluate_speaking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    language = get_language(context, update.effective_user.id)
    status = "⏳ Ovozli javobingiz baholanmoqda..." if language == "uz" else "⏳ Ваш ответ оценивается..."
    await update.message.reply_text(status)
    gemini_file = None
    try:
        telegram_file = await update.message.voice.get_file() if update.message.voice else await update.message.audio.get_file()
        mime_type = update.message.voice.mime_type if update.message.voice else update.message.audio.mime_type
        mime_type = mime_type or "audio/ogg"
        with tempfile.NamedTemporaryFile(suffix=".audio") as audio_file:
            await telegram_file.download_to_drive(custom_path=audio_file.name)
            gemini_file = await asyncio.to_thread(
                genai.upload_file, audio_file.name, mime_type=mime_type
            )
        prompt = (
            "Evaluate this spoken IELTS response using Fluency & Coherence, Lexical Resource, "
            "Grammatical Range & Accuracy, and Pronunciation. Give a band from 1 to 9 and "
            "brief actionable feedback. Reply in Uzbek. End with exactly one machine-readable "
            "line: OVERALL_BAND: X.X (use a valid IELTS half-band score)."
            if language == "uz"
            else "Оцените этот устный ответ IELTS по критериям Fluency & Coherence, Lexical Resource, "
            "Grammatical Range & Accuracy и Pronunciation. Укажите балл от 1 до 9 и краткие "
            "практические рекомендации. Ответьте по-русски. В конце добавьте ровно одну строку "
            "для обработки: OVERALL_BAND: X.X (допустимый шаг оценки IELTS — 0,5)."
        )
        response = await asyncio.to_thread(model.generate_content, [prompt, gemini_file])
        result = response.text or ""
        score_match = re.search(r"(?m)^OVERALL_BAND:\s*([1-8](?:\.0|\.5)?|9(?:\.0)?)\s*$", result)
        score = float(score_match.group(1)) if score_match else None
        if score_match:
            result = result[:score_match.start()].rstrip()
        if score is not None:
            previous_score = record_band_score(update.effective_user.id, score)
            if previous_score is not None:
                result += score_change_message(float(previous_score), score, language)
        fallback = "Nutq aniqlanmadi." if language == "uz" else "Не удалось распознать речь."
        await update.message.reply_text(result or fallback)
    except Exception:
        logger.exception("Speaking baholashda xatolik")
        await update.message.reply_text(
            "❌ Ovozli javobni baholashda xatolik yuz berdi."
            if language == "uz"
            else "❌ Не удалось оценить голосовой ответ."
        )
    finally:
        if gemini_file is not None:
            try:
                await asyncio.to_thread(genai.delete_file, gemini_file.name)
            except Exception:
                logger.exception("Gemini audio faylini o‘chirishda xatolik")


# =========================
# MAIN
# =========================
def main():

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(CommandHandler("til", choose_language))
    application.add_handler(CommandHandler("mavzu", suggest_topic))
    application.add_handler(CommandHandler("tarix", show_history))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            evaluate_essay
        )
    )

    application.add_handler(
        MessageHandler(filters.VOICE | filters.AUDIO, evaluate_speaking)
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