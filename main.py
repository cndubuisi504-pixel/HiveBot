Import os
import random
import anthropic
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MONGO_URI = os.environ.get("MONGO_URI")

client_mongo = MongoClient(MONGO_URI)
db = client_mongo["hive_bot_db"]
collection = db["user_memories"]
client_claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are Hive 🐝, a brilliant Web3 Professor. 
1. Use analogies to explain complex crypto topics.
2. Use LaTeX for technical math: $$Total = Gas \times Price$$.
3. End every response with a Socratic question to test the student.
4. You have 'Forever Memory'. Reference past context to build knowledge.
5. Keep responses concise and use Markdown headers."""

QUIZ_TOPICS = ["Bitcoin", "Ethereum", "DeFi", "NFTs", "Web3", "Blockchain", "Gas", "Wallets"]

STARTER_BUTTONS = [
    [InlineKeyboardButton("⚡ Bitcoin", callback_data="q_bitcoin"), InlineKeyboardButton("🔷 Ethereum", callback_data="q_ethereum")],
    [InlineKeyboardButton("🏦 DeFi", callback_data="q_defi"), InlineKeyboardButton("🖼️ NFTs", callback_data="q_nfts")],
    [InlineKeyboardButton("🎯 Test Me", callback_data="q_quiz")]
]

BUTTON_QUESTIONS = {
    "q_bitcoin": "Explain Bitcoin scarcity and the Halving.",
    "q_ethereum": "What is the role of a Validator?",
    "q_defi": "How does a Liquidity Pool work?",
    "q_nfts": "Explain NFT metadata vs the token.",
}

def get_history(user_id):
    user_doc = collection.find_one({"user_id": user_id})
    return user_doc["history"] if user_doc else []

def save_history(user_id, history):
    collection.update_one(
        {"user_id": user_id},
        {"$set": {"history": history[-30:]}}, # Keep last 30 turns
        upsert=True
    )

async def ask_claude(user_id, message):
    history = get_history(user_id)
    messages = history + [{"role": "user", "content": message}]
    
    response = client_claude.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=messages
    )
    
    reply = response.content[0].text
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    save_history(user_id, history)
    return reply

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Gm! ☀️ I'm *Hive* 🐝 — your Web3 mentor.\n\n"
        "I'll remember our progress forever. Use /new to reset.\n\n"
        "What shall we master today?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(STARTER_BUTTONS)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = await ask_claude(update.effective_user.id, update.message.text)
    await update.message.reply_text(reply, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    prompt = BUTTON_QUESTIONS.get(query.data)
    if query.data == "q_quiz":
        prompt = f"Give me a quiz question about {random.choice(QUIZ_TOPICS)}. A/B/C/D options only."
    
    if prompt:
        reply = await ask_claude(query.from_user.id, prompt)
        await context.bot.send_message(chat_id=query.message.chat_id, text=reply, parse_mode="Markdown")

async def reset_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    collection.delete_one({"user_id": update.effective_user.id})
    await update.message.reply_text("🔄 Memory wiped. Send /start to begin again.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("new", reset_chat))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
