"""
👁 Eye of God Bot — переписан на чистом aiohttp (без python-telegram-bot)
Совместим с Python 3.13+
"""
import asyncio
import aiohttp
import json
import os
from searchers import (
    search_by_phone,
    search_by_username,
    search_by_name,
    search_email,
    search_social_networks,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# user_id -> mode
user_modes = {}

MENU_TEXT = (
    "👁 *Eye of God — OSINT Bot*\n\n"
    "Выбери режим поиска:"
)

MENU_KB = {
    "inline_keyboard": [
        [{"text": "📱 Номер телефона", "callback_data": "mode_phone"}],
        [{"text": "👤 Ник / Username",  "callback_data": "mode_username"}],
        [{"text": "📛 Имя + Фамилия",   "callback_data": "mode_name"}],
        [{"text": "📧 Email",            "callback_data": "mode_email"}],
        [{"text": "🌐 Соцсети (все)",    "callback_data": "mode_social"}],
    ]
}

BACK_KB = {
    "inline_keyboard": [[{"text": "◀️ Назад", "callback_data": "back_main"}]]
}

PROMPTS = {
    "phone":    "📱 Введи номер телефона (например +79991234567):",
    "username": "👤 Введи ник / username (без @):",
    "name":     "📛 Введи Имя Фамилию:",
    "email":    "📧 Введи email адрес:",
    "social":   "🌐 Введи ник для поиска по всем соцсетям:",
}

# ─────────────── API helpers ───────────────

async def api(session, method, **kwargs):
    async with session.post(f"{API}/{method}", json=kwargs) as r:
        return await r.json()

async def send(session, chat_id, text, reply_markup=None):
    params = {
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": "Markdown",
    }
    if reply_markup:
        params["reply_markup"] = reply_markup
    await api(session, "sendMessage", **params)

async def answer_cb(session, cb_id):
    await api(session, "answerCallbackQuery", callback_query_id=cb_id)

async def edit_msg(session, chat_id, msg_id, text, reply_markup=None):
    params = {
        "chat_id": chat_id,
        "message_id": msg_id,
        "text": text[:4096],
        "parse_mode": "Markdown",
    }
    if reply_markup:
        params["reply_markup"] = reply_markup
    await api(session, "editMessageText", **params)

async def delete_msg(session, chat_id, msg_id):
    await api(session, "deleteMessage", chat_id=chat_id, message_id=msg_id)

# ─────────────── handlers ───────────────

async def handle_message(session, msg):
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if text == "/start":
        user_modes.pop(chat_id, None)
        await send(session, chat_id, MENU_TEXT, MENU_KB)
        return

    mode = user_modes.get(chat_id)
    if not mode:
        await send(session, chat_id, MENU_TEXT, MENU_KB)
        return

    del user_modes[chat_id]
    wait = await api(session, "sendMessage",
                     chat_id=chat_id, text="🔍 Ищу, подожди...")
    wait_id = wait.get("result", {}).get("message_id")

    try:
        if mode == "phone":
            result = await search_by_phone(text)
        elif mode == "username":
            result = await search_by_username(text)
        elif mode == "name":
            result = await search_by_name(text)
        elif mode == "email":
            result = await search_email(text)
        elif mode == "social":
            result = await search_social_networks(text)
        else:
            result = "❌ Неизвестный режим"
    except Exception as e:
        result = f"❌ Ошибка: {e}"

    if wait_id:
        await delete_msg(session, chat_id, wait_id)

    # Режем на куски по 4000 символов
    for i in range(0, len(result), 4000):
        chunk = result[i:i+4000]
        kb = MENU_KB if i + 4000 >= len(result) else None
        await send(session, chat_id, chunk, kb)


async def handle_callback(session, cb):
    chat_id = cb["message"]["chat"]["id"]
    msg_id  = cb["message"]["message_id"]
    data    = cb["data"]
    cb_id   = cb["id"]

    await answer_cb(session, cb_id)

    if data == "back_main":
        user_modes.pop(chat_id, None)
        await edit_msg(session, chat_id, msg_id, MENU_TEXT, MENU_KB)
        return

    mode = data.replace("mode_", "")
    user_modes[chat_id] = mode
    await edit_msg(session, chat_id, msg_id, PROMPTS[mode], BACK_KB)


# ─────────────── polling ───────────────

async def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не задан!")
        return

    offset = 0
    print("👁 Eye of God запущен (long polling)")

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                resp = await api(session, "getUpdates",
                                 offset=offset, timeout=30,
                                 allowed_updates=["message", "callback_query"])
                updates = resp.get("result", [])
                for upd in updates:
                    offset = upd["update_id"] + 1
                    if "message" in upd:
                        asyncio.create_task(handle_message(session, upd["message"]))
                    elif "callback_query" in upd:
                        asyncio.create_task(handle_callback(session, upd["callback_query"]))
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
