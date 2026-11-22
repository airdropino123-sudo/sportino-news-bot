import os
import json
import re
import html
import requests
import feedparser
from datetime import datetime, timezone, timedelta

# =========================
# تنظیمات ربات
# =========================

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

CHANNEL_USERNAME = "@SportinoNews"

MAX_POSTS_PER_RUN = 3
MAX_AGE_HOURS = 48
SENT_FILE = "sent_news.json"

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

# =========================
# دسته‌بندی اخبار
# =========================

KEYWORDS = {
    "استقلال": [
        "استقلال", "esteghlal"
    ],
    "پرسپولیس": [
        "پرسپولیس", "persepolis"
    ],
    "لیگ قهرمانان": [
        "لیگ قهرمانان", "champions league",
        "ucl"
    ],
    "فوتبال ایران": [
        "لیگ برتر ایران", "فوتبال ایران",
        "تیم ملی ایران", "جام حذفی",
        "تراکتور", "سپاهان"
    ],
    "فوتبال اروپا": [
        "premier league", "لالیگا",
        "la liga", "serie a", "سری آ",
        "bundesliga", "بوندسلیگا",
        "لیگ برتر انگلیس"
    ],
    "بسکتبال": [
        "بسکتبال", "basketball", "nba"
    ],
    "والیبال": [
        "والیبال", "volleyball"
    ],
    "تنیس": [
        "تنیس", "tennis"
    ],
}

BREAKING_WORDS = [
    "فوری", "لحظاتی پیش", "رسمی شد",
    "اخراج شد", "مصدومیت", "قهرمان شد",
    "صعود کرد", "شکست خورد", "breaking",
    "official", "injury", "sacked"
]

HASHTAGS = {
    "استقلال": "#استقلال #Esteghlal",
    "پرسپولیس": "#پرسپولیس #Persepolis",
    "فوتبال ایران": "#فوتبال_ایران",
    "فوتبال اروپا": "#فوتبال_اروپا",
    "لیگ قهرمانان": "#لیگ_قهرمانان",
    "بسکتبال": "#بسکتبال",
    "والیبال": "#والیبال",
    "تنیس": "#تنیس",
}

# =========================
# مدیریت اخبار تکراری
# =========================

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


# =========================
# ترجمه فارسی
# =========================

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

        translated = "".join(
            part[0] for part in data[0] if part[0]
        )

        return translated or text

    except Exception as e:
        print("Translation error:", e)
        return text


# =========================
# پاکسازی متن
# =========================

def clean_text(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# =========================
# دریافت تصویر خبر
# =========================

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

    for content in item.get("content", []):
        match = re.search(
            r'<img[^>]+src=["\']([^"\']+)',
            content.get("value", "")
        )

        if match:
            return html.unescape(match.group(1))

    description = item.get("description", "")

    match = re.search(
        r'<img[^>]+src=["\']([^"\']+)',
        description
    )

    if match:
        return html.unescape(match.group(1))

    return None


# =========================
# دسته‌بندی خبر
# =========================

def get_category(title):

    text = title.lower()

    for category, words in KEYWORDS.items():
        if any(word.lower() in text for word in words):
            return category

    return "ورزش جهان"


# =========================
# تشخیص خبر فوری
# =========================

def is_breaking(title):

    text = title.lower()

    return any(
        word.lower() in text
        for word in BREAKING_WORDS
    )


# =========================
# تاریخ خبر
# =========================

def get_date(item):

    try:
        if item.get("published_parsed"):
            return datetime(
                *item.published_parsed[:6],
                tzinfo=timezone.utc
            )

        if item.get("updated_parsed"):
            return datetime(
                *item.updated_parsed[:6],
                tzinfo=timezone.utc
            )

    except Exception:
        pass

    return None


def is_recent(item):

    date = get_date(item)

    if date is None:
        return True

    now = datetime.now(timezone.utc)

    return now - date <= timedelta(hours=MAX_AGE_HOURS)


# =========================
# ساخت کپشن حرفه‌ای
# =========================

def create_caption(title, summary, link, category, breaking):

    title_fa = translate_to_farsi(title)
    summary_fa = translate_to_farsi(summary) if summary else ""

    title_fa = title_fa[:300]

    summary_fa = summary_fa[:450]

    if breaking:
        header = "🚨 <b>خبر فوری | اسپورتینو</b>"
    else:
        header = "⚽ <b>اسپورتینو | اخبار ورزشی</b>"

    hashtag = HASHTAGS.get(
        category,
        "#فوتبال #اخبار_ورزشی"
    )

    caption = (
        f"{header}\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🏷️ <b>دسته:</b> {html.escape(category)}\n\n"
        f"🔥 <b>{html.escape(title_fa)}</b>\n\n"
    )

    if summary_fa and summary_fa != title_fa:
        caption += (
            "📝 <b>جزئیات خبر:</b>\n"
            f"{html.escape(summary_fa)}\n\n"
        )

    caption += (
        f'🔗 <a href="{html.escape(link, quote=True)}">'
        "مشاهده منبع خبر</a>\n\n"
        "━━━━━━━━━━━━━━\n"
        "⚡ <b>سریع‌تر از همه، باخبر شو!</b>\n"
        "🌍 اخبار فوتبال ایران و جهان\n\n"
        "📡 <b>عضویت در اسپورتینو:</b>\n"
        f"👉 {CHANNEL_USERNAME}\n\n"
        f"{hashtag}"
    )

    return caption


# =========================
# ارسال خبر به تلگرام
# =========================

def send_news(
    title,
    link,
    category,
    breaking,
    image_url=None,
    summary=""
):

    caption = create_caption(
        title,
        summary,
        link,
        category,
        breaking
    )

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    # ارسال همراه تصویر
    if image_url:

        try:
            response = requests.post(
                f"{base_url}/sendPhoto",
                data={
                    "chat_id": CHANNEL_ID,
                    "photo": image_url,
                    "caption": caption,
                    "parse_mode": "HTML"
                },
                timeout=30
            )

            response.raise_for_status()

            print("Photo news sent successfully")
            return True

        except Exception as e:
            print("Photo sending failed:", e)

    # ارسال متنی در صورت نبود تصویر
    response = requests.post(
        f"{base_url}/sendMessage",
        data={
            "chat_id": CHANNEL_ID,
            "text": caption,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        },
        timeout=30
    )

    response.raise_for_status()

    print("Text news sent successfully")
    return True


# =========================
# اجرای اصلی ربات
# =========================

def main():

    sent = load_sent()

    news_list = []

    print("Sportino bot started...")
    print("Checking RSS sources...")

    # دریافت خبرها
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

                summary = clean_text(
                    item.get("summary", "")
                )

                if not summary:
                    summary = clean_text(
                        item.get("description", "")
                    )

                news_list.append({
                    "title": title,
                    "link": link,
                    "image": get_image(item),
                    "summary": summary,
                    "date": get_date(item),
                    "category": get_category(title),
                    "breaking": is_breaking(title)
                })

        except Exception as e:
            print("RSS error:", e)

    # حذف خبرهای تکراری
    unique_news = []
    seen_links = set()

    for news in news_list:

        if news["link"] not in seen_links:
            seen_links.add(news["link"])
            unique_news.append(news)

    # اول خبر فوری، سپس جدیدترین
    unique_news.sort(
        key=lambda x: (
            x["breaking"],
            x["date"] or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True
    )

    # ارسال حداکثر ۳ خبر
    new_sent = []

    for news in unique_news[:MAX_POSTS_PER_RUN]:

        try:

            send_news(
                title=news["title"],
                link=news["link"],
                category=news["category"],
                breaking=news["breaking"],
                image_url=news["image"],
                summary=news["summary"]
            )

            new_sent.append(news["link"])

            print("Posted:", news["title"])

        except Exception as e:

            print("Send error:", e)

    # ذخیره تاریخچه
    save_sent(sent + new_sent)

    print("======================")
    print("News sent:", len(new_sent))
    print("Sportino bot finished.")
    print("======================")


if __name__ == "__main__":
    main()
