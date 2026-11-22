
import os
import json
import re
import html
import requests
import feedparser
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

RSS_URLS = [
    "https://feeds.bbci.co.uk/sport/rss.xml",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml",
    "https://feeds.bbci.co.uk/sport/football/champions-league/rss.xml",
    "https://news.google.com/rss/search?q=استقلال+OR+پرسپولیس&hl=fa&gl=IR&ceid=IR:fa",
    "https://news.google.com/rss/search?q=فوتبال+ایران&hl=fa&gl=IR&ceid=IR:fa",
    "https://news.google.com/rss/search?q=لیگ+برتر+ایران&hl=fa&gl=IR&ceid=IR:fa",
    "https://news.google.com/rss/search?q=اخبار+ورزش&hl=fa&gl=IR&ceid=IR:fa",
    "https://news.google.com/rss/search?q=فوتبال+جهان&hl=fa&gl=IR&ceid=IR:fa",
]

SENT_FILE = "sent_news.json"
MAX_POSTS_PER_RUN = 3
MAX_AGE_HOURS = 48

KEYWORDS = {
    "استقلال": ["استقلال", "esteghlal"],
    "پرسپولیس": ["پرسپولیس", "persepolis"],
    "فوتبال ایران": ["لیگ برتر", "تیم ملی ایران", "فوتبال ایران", "جام حذفی", "تراکتور", "سپاهان"],
    "فوتبال اروپا": ["لیگ برتر انگلیس", "premier league", "لالیگا", "la liga", "سری آ", "serie a", "بوندسلیگا", "bundesliga"],
    "لیگ قهرمانان": ["لیگ قهرمانان", "champions league", "ucl"],
    "بسکتبال": ["بسکتبال", "basketball", "nba"],
    "والیبال": ["والیبال", "volleyball"],
    "تنیس": ["تنیس", "tennis"],
    "ورزش جهان": ["فوتبال", "ورزش", "sport", "football"],
}

BREAKING_WORDS = [
    "فوری", "لحظاتی پیش", "رسمی شد", "اخراج شد",
    "مصدومیت", "قهرمان شد", "صعود کرد", "شکست خورد",
    "breaking", "official", "injury", "sacked"
]


def load_sent():
    if os.path.exists(SENT_FILE):
        try:
            with open(SENT_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_sent(sent):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent[-1000:], f, ensure_ascii=False)


def translate_to_farsi(text):
    if not text:
        return ""

    try:
        response = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "auto",
                "tl": "fa",
                "dt": "t",
                "q": text
            },
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        translated = "".join(part[0] for part in data[0] if part[0])
        return translated or text
    except Exception:
        return text


def clean_text(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def get_image(item):
    for media in item.get("media_content", []):
        if media.get("url"):
            return media["url"]

    for thumb in item.get("media_thumbnail", []):
        if thumb.get("url"):
            return thumb["url"]

    for enclosure in item.get("enclosures", []):
        if enclosure.get("type", "").startswith("image"):
            return enclosure.get("href") or enclosure.get("url")

    content = item.get("content", [])
    for part in content:
        match = re.search(
            r'<img[^>]+src=["\']([^"\']+)',
            part.get("value", "")
        )
        if match:
            return html.unescape(match.group(1))

    description = item.get("description", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)', description)

    if match:
        return html.unescape(match.group(1))

    return None


def get_category(title):
    text = title.lower()

    for category, words in KEYWORDS.items():
        if any(word.lower() in text for word in words):
            return category

    return "ورزش جهان"


def is_breaking(title):
    text = title.lower()
    return any(word.lower() in text for word in BREAKING_WORDS)


def get_date(item):
    try:
        if item.get("published_parsed"):
            return datetime(*item.published_parsed[:6], tzinfo=timezone.utc)

        if item.get("updated_parsed"):
            return datetime(*item.updated_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        pass

    return None


def is_recent(item):
    date = get_date(item)

    if date is None:
        return True

    now = datetime.now(timezone.utc)
    return now - date <= timedelta(hours=MAX_AGE_HOURS)


def send_news(title, link, category, breaking, image_url=None):
    persian_title = translate_to_farsi(title)

    if breaking:
        headline = "🚨 <b>خبر فوری</b>\n\n"
    else:
        headline = ""

    message = (
        "⚽ <b>اسپورتینو | اخبار ورزشی</b>\n"
        "━━━━━━━━━━━━━━\n"
        f"🏷️ <b>دسته:</b> {html.escape(category)}\n\n"
        f"{headline}"
        f"📰 {html.escape(persian_title)}\n\n"
        f'<a href="{html.escape(link, quote=True)}">🔗 مشاهده منبع خبر</a>\n\n'
        "━━━━━━━━━━━━━━\n"
        "📲 با اسپورتینو همراه باشید"
    )

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    if image_url:
        try:
            response = requests.post(
                f"{base_url}/sendPhoto",
                data={
                    "chat_id": CHANNEL_ID,
                    "photo": image_url,
                    "caption": message,
                    "parse_mode": "HTML"
                },
                timeout=30
            )

            response.raise_for_status()
            return True

        except Exception:
            pass

    response = requests.post(
        f"{base_url}/sendMessage",
        data={
            "chat_id": CHANNEL_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        },
        timeout=30
    )

    response.raise_for_status()
    return True


def main():
    sent = load_sent()
    news_list = []

    print("Checking news sources...")

    for rss_url in RSS_URLS:
        try:
            feed = feedparser.parse(rss_url)

            for item in feed.entries:
                link = item.get("link", "")
                title = clean_text(item.get("title", ""))

                if not link or not title:
                    continue

                if link in sent:
                    continue

                if not is_recent(item):
                    continue

                news_list.append({
                    "title": title,
                    "link": link,
                    "image": get_image(item),
                    "date": get_date(item),
                    "category": get_category(title),
                    "breaking": is_breaking(title)
                })

        except Exception as e:
            print("RSS error:", e)

    unique_news = []
    seen_links = set()

    for news in news_list:
        if news["link"] not in seen_links:
            seen_links.add(news["link"])
            unique_news.append(news)

    unique_news.sort(
        key=lambda x: (
            x["breaking"],
            x["date"] or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True
    )

    new_sent = []

    for news in unique_news[:MAX_POSTS_PER_RUN]:
        try:
            send_news(
                news["title"],
                news["link"],
                news["category"],
                news["breaking"],
                news["image"]
            )

            new_sent.append(news["link"])
            print("Posted:", news["title"])

        except Exception as e:
            print("Send error:", e)

    save_sent(sent + new_sent)

    print("News sent:", len(new_sent))
    print("Bot finished successfully.")


if __name__ == "__main__":
    main()
