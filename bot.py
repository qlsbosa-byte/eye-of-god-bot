"""
👁 Eye of God — OSINT Telegram Bot
Аналог бота "Глаз Бога": поиск по нику, номеру, имени, соцсетям
"""

import asyncio
import aiohttp
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from config import BOT_TOKEN
from searchers import (
    search_by_phone,
    search_by_username,
    search_by_name,
    search_social_networks,
    search_email,
)

# ───────────────────────────── helpers ──────────────────────────────

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📱 Номер телефона", callback_data="mode_phone")],
        [InlineKeyboardButton("👤 Ник / Username",  callback_data="mode_username")],
        [InlineKeyboardButton("📛 Имя + Фамилия",   callback_data="mode_name")],
        [InlineKeyboardButton("📧 Email",            callback_data="mode_email")],
        [InlineKeyboardButton("🌐 Соцсети (все)",    callback_data="mode_social")],
    ])

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ Назад", callback_data="back_main")]
    ])

PROMPTS = {
    "phone":    "📱 Введи номер телефона (международный формат, например +79991234567):",
    "username": "👤 Введи ник / username (без @):",
    "name":     "📛 Введи Имя Фамилию (можно добавить город через запятую):",
    "email":    "📧 Введи email адрес:",
    "social":   "🌐 Введи ник для поиска по всем соцсетям:",
}

# ───────────────────────────── handlers ─────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    text = (
        "👁 *Eye of God — OSINT Bot*\n\n"
        "Поиск информации по открытым источникам.\n"
        "Выбери режим поиска:"
    )
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=main_menu_keyboard())

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_main":
        ctx.user_data.clear()
        await query.edit_message_text(
            "👁 *Eye of God — OSINT Bot*\n\nВыбери режим поиска:",
            parse_mode="Markdown", reply_markup=main_menu_keyboard()
        )
        return

    mode = data.replace("mode_", "")
    ctx.user_data["mode"] = mode
    await query.edit_message_text(
        PROMPTS[mode], reply_markup=back_keyboard()
    )

async def handle_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mode = ctx.user_data.get("mode")
    if not mode:
        await start(update, ctx)
        return

    query_text = update.message.text.strip()
    ctx.user_data.clear()

    msg = await update.message.reply_text("🔍 Ищу информацию, подожди...")

    try:
        if mode == "phone":
            result = await search_by_phone(query_text)
        elif mode == "username":
            result = await search_by_username(query_text)
        elif mode == "name":
            result = await search_by_name(query_text)
        elif mode == "email":
            result = await search_email(query_text)
        elif mode == "social":
            result = await search_social_networks(query_text)
        else:
            result = "❌ Неизвестный режим"
    except Exception as e:
        result = f"❌ Ошибка при поиске: {e}"

    # Telegram limit = 4096 chars
    for chunk in split_message(result):
        await update.message.reply_text(chunk, parse_mode="Markdown",
                                        reply_markup=main_menu_keyboard())
    await msg.delete()

def split_message(text: str, limit: int = 4000):
    """Режем длинные ответы на части."""
    parts = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(text[:split_at])
        text = text[split_at:].lstrip()
    parts.append(text)
    return parts

# ───────────────────────────── main ─────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    print("👁 Eye of God запущен")
    app.run_polling()

if __name__ == "__main__":
    main()
