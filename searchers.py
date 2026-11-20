"""
Модули поиска для Eye of God OSINT Bot
Использует только открытые API и публичные источники
"""

import aiohttp
import asyncio
import json
import re
from typing import Optional

# ══════════════════════════════════════════════════════════════════
# 1. ПОИСК ПО НОМЕРУ ТЕЛЕФОНА
# ══════════════════════════════════════════════════════════════════

async def search_by_phone(phone: str) -> str:
    phone = re.sub(r"[^\d+]", "", phone)
    if not phone.startswith("+"):
        phone = "+" + phone

    results = [f"📱 *Поиск по номеру:* `{phone}`\n"]

    tasks = [
        _numverify(phone),
        _truecaller_lookup(phone),
        _hlr_lookup(phone),
        _callerid_scrape(phone),
        _leakcheck_phone(phone),
    ]
    data = await asyncio.gather(*tasks, return_exceptions=True)
    labels = ["NumVerify", "TrueCaller-style", "HLR/Carrier", "CallerID", "Утечки"]

    for label, res in zip(labels, data):
        if isinstance(res, Exception):
            results.append(f"• {label}: ошибка ({res})")
        elif res:
            results.append(res)

    return "\n".join(results) if len(results) > 1 else "❌ Информация не найдена"


async def _numverify(phone: str) -> Optional[str]:
    """
    Numverify — бесплатный tier (100 req/month).
    https://numverify.com/
    """
    # Без API-ключа работает в demo-режиме (только формат)
    url = f"http://apilayer.net/api/validate?access_key=FREE_TIER&number={phone}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                d = await r.json()
        if not d.get("valid"):
            return "• NumVerify: номер не прошёл валидацию"
        lines = [
            f"• 🌍 Страна: {d.get('country_name', '?')} ({d.get('country_code', '?')})",
            f"• 🏢 Оператор: {d.get('carrier', '?')}",
            f"• 📶 Тип: {d.get('line_type', '?')}",
            f"• 🔢 Формат: {d.get('international_format', phone)}",
        ]
        return "\n".join(lines)
    except Exception:
        return None


async def _truecaller_lookup(phone: str) -> Optional[str]:
    """
    Имитация Truecaller-стиля через публичные endpoint'ы.
    Реальный Truecaller требует авторизации — здесь паттерн запроса.
    """
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    # Используем opencnam (бесплатный caller-ID)
    url = f"https://api.opencnam.com/v3/phone/{phone}?format=json"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers,
                             timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    d = await r.json()
                    name = d.get("name")
                    if name:
                        return f"• 👤 CallerID имя: *{name}*"
    except Exception:
        pass
    return None


async def _hlr_lookup(phone: str) -> Optional[str]:
    """
    HLR lookup через hlr-lookups.com (есть бесплатный trial).
    Возвращает оператора и статус (активен/нет).
    """
    # Демо-запрос без ключа
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://www.hlrlookup.com/api/synlookup?msisdn={phone.lstrip('+')}"
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                text = await r.text()
                if "mccmnc" in text.lower() or "imsi" in text.lower():
                    return f"• 📡 HLR: номер активен"
    except Exception:
        pass
    return None


async def _callerid_scrape(phone: str) -> Optional[str]:
    """
    Scrape publicных сервисов типа who-called.ru / telefonnyi-spravochnik.
    """
    clean = phone.replace("+", "").replace(" ", "")
    urls_to_try = [
        f"https://www.getcontact.com/en/search?q={clean}",
        f"https://nomerorg.app/{clean}",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    for url in urls_to_try:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, headers=headers,
                                 timeout=aiohttp.ClientTimeout(total=6),
                                 allow_redirects=True) as r:
                    if r.status == 200:
                        text = await r.text()
                        # ищем имена в мета-тегах
                        m = re.search(r'<title>([^<]{3,80})</title>', text)
                        if m and phone.replace("+", "") not in m.group(1):
                            return f"• 📋 Публичные базы: {m.group(1).strip()}"
        except Exception:
            continue
    return None


async def _leakcheck_phone(phone: str) -> Optional[str]:
    """
    Проверка телефона в утечках через LeakCheck.io (free tier 10 req/day).
    """
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://leakcheck.io/api/public?check={phone}"
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                d = await r.json()
                if d.get("found", 0) > 0:
                    sources = ", ".join(d.get("sources", [])[:5])
                    return (f"• ⚠️ Найден в *{d['found']}* утечках!\n"
                            f"  Источники: {sources}")
                elif d.get("found") == 0:
                    return "• ✅ В известных утечках не найден"
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════
# 2. ПОИСК ПО USERNAME
# ══════════════════════════════════════════════════════════════════

SOCIAL_PLATFORMS = {
    "GitHub":       "https://github.com/{u}",
    "Twitter/X":    "https://twitter.com/{u}",
    "Instagram":    "https://www.instagram.com/{u}/",
    "TikTok":       "https://www.tiktok.com/@{u}",
    "Reddit":       "https://www.reddit.com/user/{u}",
    "Telegram":     "https://t.me/{u}",
    "VK":           "https://vk.com/{u}",
    "YouTube":      "https://www.youtube.com/@{u}",
    "Twitch":       "https://www.twitch.tv/{u}",
    "Pinterest":    "https://www.pinterest.com/{u}/",
    "Flickr":       "https://www.flickr.com/people/{u}",
    "Snapchat":     "https://www.snapchat.com/add/{u}",
    "SoundCloud":   "https://soundcloud.com/{u}",
    "Steam":        "https://steamcommunity.com/id/{u}",
    "GitLab":       "https://gitlab.com/{u}",
    "Bitbucket":    "https://bitbucket.org/{u}",
    "DeviantArt":   "https://www.deviantart.com/{u}",
    "Patreon":      "https://www.patreon.com/{u}",
    "Medium":       "https://medium.com/@{u}",
    "Keybase":      "https://keybase.io/{u}",
    "HackerNews":   "https://news.ycombinator.com/user?id={u}",
    "ProductHunt":  "https://www.producthunt.com/@{u}",
    "Replit":       "https://replit.com/@{u}",
    "Codepen":      "https://codepen.io/{u}",
    "Habr":         "https://habr.com/en/users/{u}/",
}

async def _check_url(session: aiohttp.ClientSession, platform: str,
                     url: str, username: str) -> Optional[str]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    try:
        async with session.get(url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=6),
                               allow_redirects=True) as r:
            if r.status == 200:
                text = await r.text()
                # Проверяем что страница реальная (не заглушка 404 с кодом 200)
                not_found_patterns = [
                    "page not found", "user not found", "404",
                    "doesn't exist", "не существует", "не найден"
                ]
                text_lower = text[:2000].lower()
                if not any(p in text_lower for p in not_found_patterns):
                    return f"✅ [{platform}]({url})"
    except Exception:
        pass
    return None


async def search_by_username(username: str) -> str:
    username = username.strip().lstrip("@")
    results = [f"👤 *Поиск username:* `{username}`\n"]
    found = []

    async with aiohttp.ClientSession() as session:
        tasks = {
            platform: _check_url(session, platform,
                                  url.format(u=username), username)
            for platform, url in SOCIAL_PLATFORMS.items()
        }
        responses = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for platform, res in zip(tasks.keys(), responses):
        if isinstance(res, str):
            found.append(res)

    if found:
        results.append(f"🔎 Найден на *{len(found)}* платформах:\n")
        results.extend(found)
    else:
        results.append("❌ Username не найден ни на одной из платформ")

    return "\n".join(results)


async def search_social_networks(username: str) -> str:
    """То же что search_by_username, но с более подробным выводом."""
    return await search_by_username(username)


# ══════════════════════════════════════════════════════════════════
# 3. ПОИСК ПО ИМЕНИ
# ══════════════════════════════════════════════════════════════════

async def search_by_name(full_name: str) -> str:
    results = [f"📛 *Поиск по имени:* `{full_name}`\n"]
    tasks = [
        _search_vk_by_name(full_name),
        _search_google_dork(full_name),
        _search_pipl_style(full_name),
    ]
    data = await asyncio.gather(*tasks, return_exceptions=True)
    for res in data:
        if isinstance(res, str) and res:
            results.append(res)

    return "\n".join(results)


async def _search_vk_by_name(name: str) -> Optional[str]:
    """VK search без токена (публичный поиск через веб)."""
    query = name.replace(" ", "+")
    url = f"https://vk.com/search?c[q]={query}&c[section]=people"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers,
                             timeout=aiohttp.ClientTimeout(total=7)) as r:
                if r.status == 200:
                    return f"• 🔵 VK: [Поиск по имени]({url})"
    except Exception:
        pass
    return None


async def _search_google_dork(name: str) -> Optional[str]:
    """Генерация Google Dork запросов для ручного поиска."""
    encoded = name.replace(" ", "+")
    dorks = [
        f"https://www.google.com/search?q=%22{encoded}%22+site:vk.com",
        f"https://www.google.com/search?q=%22{encoded}%22+site:facebook.com",
        f"https://www.google.com/search?q=%22{encoded}%22+%22телефон%22+OR+%22email%22",
    ]
    lines = ["• 🔍 Google Dorks (кликай):"]
    for d in dorks:
        lines.append(f"  [Поиск]({d})")
    return "\n".join(lines)


async def _search_pipl_style(name: str) -> Optional[str]:
    """Поиск в открытых агрегаторах персональных данных."""
    encoded = name.replace(" ", "+")
    url = f"https://www.truepeoplesearch.com/results?name={encoded}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers,
                             timeout=aiohttp.ClientTimeout(total=7)) as r:
                text = await r.text()
                count_m = re.search(r'(\d+)\s+Result', text)
                if count_m:
                    return (f"• 🇺🇸 TruePeopleSearch: "
                            f"найдено *{count_m.group(1)}* записей\n"
                            f"  [Смотреть]({url})")
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════
# 4. ПОИСК ПО EMAIL
# ══════════════════════════════════════════════════════════════════

async def search_email(email: str) -> str:
    email = email.strip().lower()
    results = [f"📧 *Поиск email:* `{email}`\n"]

    tasks = [
        _hibp_check(email),
        _hunter_io_check(email),
        _leakcheck_email(email),
        _gravatar_check(email),
        _email_socials(email),
    ]
    data = await asyncio.gather(*tasks, return_exceptions=True)

    for res in data:
        if isinstance(res, str) and res:
            results.append(res)

    return "\n".join(results) if len(results) > 1 else "❌ Информация не найдена"


async def _hibp_check(email: str) -> Optional[str]:
    """
    HaveIBeenPwned — проверка утечек.
    Публичный API (без ключа — только aggregated data).
    """
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    headers = {
        "User-Agent": "EyeOfGodOSINT/1.0",
        "hibp-api-key": "FREE",  # заменить на реальный ключ
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, headers=headers,
                             timeout=aiohttp.ClientTimeout(total=7)) as r:
                if r.status == 200:
                    breaches = await r.json()
                    names = [b["Name"] for b in breaches[:10]]
                    return (f"• ⚠️ HIBP: найден в *{len(breaches)}* утечках!\n"
                            f"  {', '.join(names)}")
                elif r.status == 404:
                    return "• ✅ HIBP: в утечках не найден"
    except Exception:
        pass
    # Fallback — ссылка для ручной проверки
    return f"• 🔍 [Проверить на HIBP](https://haveibeenpwned.com/account/{email})"


async def _hunter_io_check(email: str) -> Optional[str]:
    """Hunter.io email verification (free tier)."""
    domain = email.split("@")[-1]
    url = f"https://api.hunter.io/v2/email-verifier?email={email}&api_key=FREE_TIER"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                d = await r.json()
                status = d.get("data", {}).get("status", "unknown")
                score = d.get("data", {}).get("score", "?")
                return f"• 🎯 Hunter.io: статус `{status}`, достоверность `{score}`"
    except Exception:
        pass
    return None


async def _leakcheck_email(email: str) -> Optional[str]:
    """LeakCheck.io free public API."""
    try:
        async with aiohttp.ClientSession() as s:
            url = f"https://leakcheck.io/api/public?check={email}"
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
                d = await r.json()
                if d.get("found", 0) > 0:
                    sources = ", ".join(d.get("sources", [])[:5])
                    return (f"• ⚠️ LeakCheck: найден в *{d['found']}* утечках\n"
                            f"  Источники: {sources}")
                elif d.get("found") == 0:
                    return "• ✅ LeakCheck: в утечках не найден"
    except Exception:
        pass
    return None


async def _gravatar_check(email: str) -> Optional[str]:
    """Gravatar — проверка аватара (если есть — email активен)."""
    import hashlib
    h = hashlib.md5(email.encode()).hexdigest()
    url = f"https://www.gravatar.com/{h}.json"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                if r.status == 200:
                    d = await r.json()
                    entry = d.get("entry", [{}])[0]
                    display = entry.get("displayName", "")
                    avatar = f"https://www.gravatar.com/avatar/{h}?s=200"
                    result = f"• 🖼 Gravatar: аккаунт существует"
                    if display:
                        result += f", имя: *{display}*"
                    result += f"\n  [Аватар]({avatar})"
                    return result
    except Exception:
        pass
    return None


async def _email_socials(email: str) -> Optional[str]:
    """Поиск email в соцсетях."""
    encoded = email.replace("@", "%40").replace(".", "%2E")
    lines = ["• 🌐 Поиск email в соцсетях:"]
    links = {
        "Google": f"https://www.google.com/search?q=%22{email}%22",
        "VK":     f"https://vk.com/search?c[q]={email}&c[section]=people",
        "GitHub": f"https://github.com/search?q={email}&type=users",
    }
    for name, url in links.items():
        lines.append(f"  [{name}]({url})")
    return "\n".join(lines)
