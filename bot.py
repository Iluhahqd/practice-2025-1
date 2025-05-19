import sqlite3
import logging
from datetime import datetime, timedelta
from random import shuffle
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# === Настройки ===
TOKEN = "7509476167:AAHSQmcyuGTc45fXIaYNbvPK5Kl0vT2nKvI"
DB_NAME = "quiz_bot.db"
logging.basicConfig(level=logging.INFO)

# === Инициализация базы данных ===
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT,
                        registration_date TEXT,
                        level INTEGER DEFAULT 1,
                        xp INTEGER DEFAULT 0,
                        total_correct INTEGER DEFAULT 0,
                        total_wrong INTEGER DEFAULT 0
                    )''')
        c.execute('''CREATE TABLE IF NOT EXISTS questions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        question TEXT,
                        correct_answer TEXT,
                        wrong_answer1 TEXT,
                        wrong_answer2 TEXT,
                        wrong_answer3 TEXT
                    )''')
        conn.commit()

def seed_questions():
    sample = [
        ("Сколько планет в Солнечной системе?", "8", "7", "9", "10"),
        ("Столица Австралии?", "Канберра", "Сидней", "Мельбурн", "Перт"),
    ]
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        for q in sample:
            c.execute("INSERT OR IGNORE INTO questions (question, correct_answer, wrong_answer1, wrong_answer2, wrong_answer3) VALUES (?, ?, ?, ?, ?)", q)
        conn.commit()

# === /start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''INSERT OR IGNORE INTO users (user_id, username, registration_date)
                     VALUES (?, ?, ?)''', (user.id, user.username, datetime.now().isoformat()))
        conn.commit()

    keyboard = [
        [InlineKeyboardButton("🎮 Начать викторину", callback_data="start_quiz")]
    ]
    await update.message.reply_text(
        "Добро пожаловать в викторину!\nНажмите кнопку, чтобы начать:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# === Задание вопроса ===
async def send_question(user_id, query_or_message):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, question, correct_answer, wrong_answer1, wrong_answer2, wrong_answer3 FROM questions ORDER BY RANDOM() LIMIT 1")
        question_row = c.fetchone()

    if not question_row:
        await query_or_message.reply_text("Нет доступных вопросов.")
        return

    q_id, question, correct, w1, w2, w3 = question_row
    answers = [correct, w1, w2, w3]
    shuffle(answers)
    buttons = [[InlineKeyboardButton(a, callback_data=f"answer_{q_id}_{a}")] for a in answers]

    await query_or_message.reply_text(
        f"❓ {question}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# === Обработка начала викторины ===
async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await send_question(query.from_user.id, query.message)

# === Ответ пользователя ===
async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, q_id, selected = query.data.split("_", 2)

    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT correct_answer FROM questions WHERE id = ?", (q_id,))
        correct = c.fetchone()[0]

        if selected == correct:
            c.execute('''UPDATE users
                         SET xp = xp + 10, total_correct = total_correct + 1
                         WHERE user_id = ?''', (query.from_user.id,))
            result_text = f"✅ Правильно! +10 XP"
        else:
            c.execute('''UPDATE users
                         SET total_wrong = total_wrong + 1
                         WHERE user_id = ?''', (query.from_user.id,))
            result_text = f"❌ Неправильно! Правильный ответ: {correct}"

        conn.commit()

    await query.edit_message_text(result_text)
    await send_question(query.from_user.id, query.message)

# === /stats ===
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT xp, total_correct, total_wrong FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()

    if row:
        xp, correct, wrong = row
        await update.message.reply_text(
            f"📊 Ваша статистика:\nXP: {xp}\n✅ Правильных: {correct}\n❌ Неправильных: {wrong}")
    else:
        await update.message.reply_text("Вы ещё не играли!")

# === Главная функция ===
def main():
    init_db()
    seed_questions()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(start_quiz, pattern="^start_quiz"))
    app.add_handler(CallbackQueryHandler(handle_answer, pattern="^answer_"))

    app.run_polling()

if __name__ == "__main__":
    main()
