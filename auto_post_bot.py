import json
import os
import random
import re
import sys
import time

import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()  # shu papkadagi .env faylni o'qib, environment variable sifatida yuklaydi

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@AITechUz")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

# Postlar tarixi shu faylda saqlanadi, bir xil yangilikni ikki marta
# yozmaslik uchun
POSTED_LOG_FILE = "posted_story_ids.txt"

# Tech/AI/dasturlashga aloqasi yo'q so'zlarni chetlab o'tish uchun
IRRELEVANT_KEYWORDS = ["politics", "election", "war", "shooting"]


def _load_posted_ids() -> set[str]:
    if not os.path.exists(POSTED_LOG_FILE):
        return set()
    with open(POSTED_LOG_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def _save_posted_id(story_id: str) -> None:
    with open(POSTED_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{story_id}\n")


def _fetch_hackernews_candidates(posted_ids: set[str]) -> list[dict]:
    top_ids = requests.get(
        "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15
    ).json()

    candidates = []
    for story_id in top_ids[:40]:  # eng tepadagi 40 ta yangilikni tekshiramiz
        sid = f"hn-{story_id}"
        if sid in posted_ids:
            continue
        item = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
            timeout=15,
        ).json()
        if not item or item.get("type") != "story":
            continue
        title = item.get("title", "")
        if any(bad in title.lower() for bad in IRRELEVANT_KEYWORDS):
            continue
        if item.get("score", 0) < 30:
            continue
        candidates.append(
            {
                "id": sid,
                "title": title,
                "url": item.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
            }
        )
    return candidates


def _fetch_rss_candidates(feed_url: str, source_prefix: str, posted_ids: set[str]) -> list[dict]:
    """Istalgan standart RSS manbadan (TechCrunch, Apple Newsroom, Samsung Newsroom,
    The Robot Report, SpaceX va h.k.) yangiliklarni oladi."""
    import xml.etree.ElementTree as ET

    try:
        response = requests.get(
            feed_url,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AITechUzBot/1.0)"},
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError):
        return []

    candidates = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        if title_el is None or link_el is None or not title_el.text or not link_el.text:
            continue
        title = title_el.text.strip()
        url = link_el.text.strip()
        sid = f"{source_prefix}-{url}"
        if sid in posted_ids:
            continue
        if any(bad in title.lower() for bad in IRRELEVANT_KEYWORDS):
            continue
        candidates.append({"id": sid, "title": title, "url": url})
    return candidates


# Rasmiy va yirik manbalar: (prefiks, RSS havolasi)
OFFICIAL_RSS_SOURCES = [
    ("tc", "https://techcrunch.com/feed/"),                       # TechCrunch — umumiy tech/gadjet
    ("apple", "https://www.apple.com/newsroom/rss-feed.rss"),     # Apple — rasmiy newsroom
    ("samsung", "https://news.samsung.com/global/feed"),           # Samsung — rasmiy newsroom
    ("robot", "https://www.therobotreport.com/feed"),              # Robototexnika yangiliklari
    ("spacex", "https://www.spacex.com/news.xml"),                 # SpaceX (Ilon Musk kompaniyasi)
    ("openai", "https://openai.com/news/rss.xml"),                 # OpenAI — rasmiy
    ("deepmind", "https://deepmind.google/blog/feed/basic/"),      # Google DeepMind — rasmiy
    ("googleai", "https://blog.google/technology/ai/rss/"),        # Google AI Blog — rasmiy
]


def fetch_real_news() -> dict:
    """Hacker News va bir nechta rasmiy/yirik manbalardan (TechCrunch, Apple, Samsung,
    robototexnika, SpaceX) tasodifiy ravishda haqiqiy, hozirgi yangilikni oladi."""
    posted_ids = _load_posted_ids()

    pool: list[dict] = _fetch_hackernews_candidates(posted_ids)[:10]

    for prefix, feed_url in OFFICIAL_RSS_SOURCES:
        candidates = _fetch_rss_candidates(feed_url, prefix, posted_ids)
        pool += candidates[:5]  # har bir manbadan eng yangi 5 tadan

    if not pool:
        sys.exit("Xato: mos yangilik topilmadi (barchasi oldin joylangan bo'lishi mumkin).")

    return random.choice(pool)


PROMPT_TEMPLATE = """Sen "AI Tech Uz" telegram kanali uchun kontent yozuvchisan.
Kanal mavzusi: sun'iy intellekt, dasturlash va texnologiya yangiliklari.
Auditoriya: o'zbek tilida so'zlashuvchi, texnologiyaga qiziquvchi yoshlar.

Quyida HAQIQIY, hozirgi kundagi tech yangilik sarlavhasi berilgan:
Sarlavha: "{title}"
Manba: {url}

Vazifa: shu HAQIQIY yangilikka asoslanib, bitta QISQA, ixcham Telegram post yoz
(60-90 so'z, 2-4 gap) VA unga mos rasm qidirish uchun ingliz tilida qisqa
kalit so'z ber.

MUHIM QOIDALAR:
- Faqat berilgan sarlavhadagi faktga asoslan — o'zingdan raqam, sana yoki
  tafsilot to'qib chiqarma
- Agar sarlavha texnik yoki tushunarsiz bo'lsa, uni oddiy odam tushunadigan
  tilga o'gir, lekin ma'nosini o'zgartirma
- Nega bu yangilik muhimligini yoki nimaga foydali ekanini qisqa tushuntir

Talablar (post matni uchun):
- Sof o'zbek tilida, tushunarli va jonli uslubda
- Matn bitta uzluksiz abzats bo'lmasin — har bir alohida fikr tugagach,
  bo'sh qator (abzats) bilan ajrat (ya'ni "\\n\\n" bilan)
- Vergul, tire (—) va nuqta-vergul kabi tinish belgilaridan o'rinli foydalanib,
  gaplarni ravon va o'qish qulay qil
- Postning eng boshida, matndan oldin, mavzuga mos BITTA emoji qo'y
  (masalan AI haqida bo'lsa 🤖, telefon haqida bo'lsa 📱, kod haqida bo'lsa 💻) —
  matn ichida yoki oxirida boshqa emoji ishlatma
- Faktni tugal fikr bilan yakunla — oxirida savol yoki "izoh qoldiring" kabi chaqiruv YOZMA

Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech narsa yozma:
{{"post": "post matni shu yerda", "image_query": "ingliz tilidagi qidiruv so'zi"}}
"""


def generate_post(news: dict) -> dict:
    if not GEMINI_API_KEY:
        sys.exit("Xato: GEMINI_API_KEY o'rnatilmagan")
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = PROMPT_TEMPLATE.format(title=news["title"], url=news["url"])

    max_attempts = 4
    wait_seconds = 15
    response = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            break
        except Exception as exc:  # Gemini vaqtincha band bo'lishi mumkin (503 va h.k.)
            if attempt == max_attempts:
                sys.exit(f"Xato: Gemini {max_attempts} urinishdan keyin ham javob bermadi: {exc}")
            print(f"Ogohlantirish: Gemini xato qaytardi ({exc}), {wait_seconds}s kutib qayta uriniladi "
                  f"({attempt}/{max_attempts})...")
            time.sleep(wait_seconds)
            wait_seconds *= 2  # har safar kutish vaqtini oshiramiz

    raw = response.text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(f"Xato: modelning javobini JSON sifatida o'qib bo'lmadi:\n{raw}")
    return data


def fetch_article_video(article_url: str) -> str | None:
    """Maqolaning o'zidan (og:video meta tegidan) to'g'ridan-to'g'ri video havolasini topishga harakat qiladi."""
    if not article_url:
        return None
    try:
        response = requests.get(
            article_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AITechUzBot/1.0)"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    html = response.text
    for pattern in (
        r'<meta[^>]+property=["\']og:video(?::url)?["\'][^>]+content=["\']([^"\']+\.mp4[^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']+\.mp4[^"\']*)["\'][^>]+property=["\']og:video(?::url)?["\']',
    ):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def fetch_article_image(article_url: str) -> str | None:
    """Maqolaning o'zidan (og:image / twitter:image meta tegidan) rasm topishga harakat qiladi."""
    if not article_url:
        return None
    try:
        response = requests.get(
            article_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AITechUzBot/1.0)"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    html = response.text
    for pattern in (
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def fetch_unsplash_image(query: str) -> str | None:
    if not UNSPLASH_ACCESS_KEY:
        print("Ogohlantirish: UNSPLASH_ACCESS_KEY yo'q, rasmsiz yuboriladi.")
        return None
    response = requests.get(
        "https://api.unsplash.com/search/photos",
        params={"query": query, "per_page": 1, "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
        timeout=15,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    if not results:
        print(f"Ogohlantirish: '{query}' uchun rasm topilmadi, rasmsiz yuboriladi.")
        return None
    return results[0]["urls"]["regular"]


def fetch_image_url(article_url: str, fallback_query: str) -> str | None:
    image_url = fetch_article_image(article_url)
    if image_url:
        print(f"Rasm manbadan olindi: {image_url}")
        return image_url
    print("Manbada rasm topilmadi, Unsplash'dan qidirilmoqda...")
    return fetch_unsplash_image(fallback_query)


TELEGRAM_CAPTION_LIMIT = 1024


def _post_to_telegram(method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    response = requests.post(url, json=payload, timeout=20)
    if response.status_code >= 400:
        sys.exit(f"Telegram xatosi ({response.status_code}): {response.text}")
    result = response.json()
    if not result.get("ok"):
        sys.exit(f"Telegram xatosi: {result}")
    return result


def _try_post_to_telegram(method: str, payload: dict) -> bool:
    """_post_to_telegram bilan bir xil, lekin xato chiqsa dasturni to'xtatmaydi — False qaytaradi."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"
    try:
        response = requests.post(url, json=payload, timeout=60)
        result = response.json()
    except (requests.RequestException, ValueError):
        return False
    if response.status_code >= 400 or not result.get("ok"):
        print(f"Ogohlantirish: {method} muvaffaqiyatsiz — {result if 'result' in dir() else response.text}")
        return False
    return True


def send_to_telegram(text: str, image_url: str | None, video_url: str | None = None) -> None:
    if not TELEGRAM_BOT_TOKEN:
        sys.exit("Xato: TELEGRAM_BOT_TOKEN o'rnatilmagan")

    caption_fits = len(text) <= TELEGRAM_CAPTION_LIMIT

    # 1) Video bo'lsa, avval video sifatida yuborishga harakat qilamiz
    if video_url:
        payload = {"chat_id": TELEGRAM_CHANNEL, "video": video_url, "parse_mode": "HTML"}
        if caption_fits:
            payload["caption"] = text
        if _try_post_to_telegram("sendVideo", payload):
            if not caption_fits:
                _post_to_telegram(
                    "sendMessage",
                    {"chat_id": TELEGRAM_CHANNEL, "text": text, "parse_mode": "HTML"},
                )
            return
        print("Video yuborib bo'lmadi, rasm bilan davom etilmoqda...")

    # 2) Video yo'q yoki muvaffaqiyatsiz bo'lsa — rasm bilan yuboramiz
    if not image_url:
        _post_to_telegram(
            "sendMessage",
            {"chat_id": TELEGRAM_CHANNEL, "text": text, "parse_mode": "HTML"},
        )
        return

    if caption_fits:
        _post_to_telegram(
            "sendPhoto",
            {
                "chat_id": TELEGRAM_CHANNEL,
                "photo": image_url,
                "caption": text,
                "parse_mode": "HTML",
            },
        )
    else:
        _post_to_telegram(
            "sendPhoto",
            {"chat_id": TELEGRAM_CHANNEL, "photo": image_url},
        )
        _post_to_telegram(
            "sendMessage",
            {"chat_id": TELEGRAM_CHANNEL, "text": text, "parse_mode": "HTML"},
        )


CHANNEL_LINK = "https://t.me/AITechUz"
CHANNEL_FOOTER = f'\n\n\n📲 <a href="{CHANNEL_LINK}">TechUz</a>'


def add_footer(post_text: str) -> str:
    return post_text + CHANNEL_FOOTER


def main() -> None:
    news = fetch_real_news()
    print(f"Tanlangan yangilik: {news['title']}")
    print(f"Manba: {news['url']}\n")

    data = generate_post(news)
    post_text = add_footer(data["post"])
    image_query = data.get("image_query", "technology")

    print("Generatsiya qilingan post:\n")
    print(post_text)
    print(f"\nRasm qidiruvi: {image_query}")

    video_url = fetch_article_video(news["url"])
    if video_url:
        print(f"Videoi manbadan topildi: {video_url}")
    image_url = fetch_image_url(news["url"], image_query)
    send_to_telegram(post_text, image_url, video_url)
    _save_posted_id(news["id"])
    print("\nKanalga muvaffaqiyatli joylandi.")


if __name__ == "__main__":
    main()
