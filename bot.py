import asyncio
import feedparser
import json
import os
import re
import hashlib
import httpx
from datetime import datetime
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

BOT_TOKEN = "8799478930:AAHmAFB8BHev14mM8yWPczwSwP9-b7PcLeY"
TARGET_CHAT_ID = 835332127

CHANNELS = [
    "banki_oil",
    "nmshhub",
    "varlamov_news",
]

CHECK_INTERVAL = 300
SENT_FILE = "sent_posts.json"


def clean_html(text):
    text = re.sub(r'<img[^>]*>', '', text)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<(?!/?(?:b|i|a|code|pre)\b)[^>]+>', '', text)
    return text.strip()


def extract_image(entry):
    content = entry.get("summary", "") + str(entry.get("content", ""))
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)
    for enc in entry.get("enclosures", []):
        if "image" in enc.get("type", "") or "video" in enc.get("type", ""):
            return enc.get("href") or enc.get("url")
    return None


def load_sent():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE) as f:
            return set(json.load(f))
    return set()


def save_sent(sent):
    with open(SENT_FILE, "w") as f:
        json.dump(list(sent), f)


def get_post_id(entry):
    # Берём id или link, если они есть
    raw_id = entry.get("id") or entry.get("link")
    if raw_id:
        # Убираем параметры в ссылке, чтобы одинаковые посты не считались разными
        return re.sub(r'\?.*$', '', raw_id)
    # Если нет ни id, ни link – создаём уникальный хэш из содержимого
    unique_str = f"{entry.get('title','')}{entry.get('published','')}{entry.get('summary','')}"
    return hashlib.md5(unique_str.encode()).hexdigest()


async def check_feeds(bot, sent_ids):
    for channel in CHANNELS:
        url = f"https://tg.i-c-a.su/rss/{channel}"
        feed = feedparser.parse(url)
        print(f"📦 @{channel}: {len(feed.entries)} постов")

        # Обрабатываем все записи, пропуская уже отправленные
        for entry in feed.entries:
            post_id = get_post_id(entry)
            if post_id in sent_ids:
                continue

            raw = entry.get("summary", entry.get("title", ""))
            text = clean_html(raw)
            image_url = extract_image(entry)
            post_link = entry.get("link", "")

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁 Открыть в канале", url=post_link)]
            ]) if post_link else None

            try:
                if image_url:
                    await bot.send_photo(
                        chat_id=TARGET_CHAT_ID,
                        photo=image_url,
                        caption=text[:1024],
                        parse_mode="HTML",
                        reply_markup=keyboard
                    )
                else:
                    await bot.send_message(
                        chat_id=TARGET_CHAT_ID,
                        text=text[:4096],
                        parse_mode="HTML",
                        reply_markup=keyboard,
                        disable_web_page_preview=False
                    )

                sent_ids.add(post_id)
                save_sent(sent_ids)  # сохраняем сразу, чтобы не потерять при падении
                print(f"✅ Отправлено из @{channel}")
                await asyncio.sleep(1)

            except Exception as e:
                print(f"❌ Ошибка при отправке из @{channel}: {e}")


async def main():
    bot = Bot(token=BOT_TOKEN)
    sent_ids = load_sent()
    print("🤖 Бот запущен!")
    while True:
        print(f"🔍 Проверяю... {datetime.now().strftime('%H:%M')}")
        await check_feeds(bot, sent_ids)
        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())