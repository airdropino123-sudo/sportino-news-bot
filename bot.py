
    import os
import json
import re
import html
import requests
import feedparser

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

RSS_URLS = [
    # BBC - اخبار ورزشی و فوتبال
    "https://feeds.bbci.co.uk/sport/rss.xml",
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://feeds.bbci.co.uk/sport/football/premier-league/rss.xml",
    "https://feeds.bbci.co.uk/sport/football/champions-league/rss.xml",

    # اخبار استقلال و پرسپولیس
    "https://news.google.com/rss/search?q=%D8%A7%D8%B3%D8%AA%D9%82%D9%84%D8%A7%D9%84+OR+%D9%BE%D8%B1%D8%B3%D9%BE%D9%88%D9%84%DB%8C%D8%B3&hl=fa&gl=IR&ceid=IR:fa",

    # فوتبال ایران
    "https://news.google.com/rss/search?q=%D9%81%D9%88%D8%AA%D8%A8%D8%A7%D9%84+%D8%A7%DB%8C%D8%B1%D8%A7%D9%86&hl=fa&gl=IR&ceid=IR:fa",

    # لیگ برتر ایران
    "https://news.google.com/rss/search?q=%D9%84%DB%8C%DA%AF+%D8%A8%D8%B1%D8%AA%D8%B1+%D8%A7%DB%8C%D8%B1%D8%A7%D9%86&hl=fa&gl=IR&ceid=IR:fa",

    # اخبار ورزشی جهان
    "https://news.google.com/rss/search?q=%D8%A7%D8%AE%D8%A8%D8%A7%D8%B1+%D9%88%D8%B1%D8%B2%D8%B4&hl=fa&gl=IR&ceid=IR:fa",
]

SENT_FILE = "sent_news.json"

# حداکثر تعداد پست در هر اجرا
MAX_POSTS_PER_RUN = 3


def load_sent():
    if os.path.exists(SENT_FILE):
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_sent(sent):
    with open(SENT_FILE, "w", encoding="utf-8") as f:
        json.dump(sent[-500:], f, ensure_ascii=False)


def translate_to_farsi(text):
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

        return translated if translated else text

    except Exception:
        return text


def get_image(item):
    # تصاویر Media RSS
    for media in item.get("media_content", []):
        if media.get("url"):
            return media["url"]

    # Thumbnail
    for thumb in item.get("media_thumbnail", []):
        if thumb.get("url"):
            return thumb["url"]

    # تصاویر ضمیمه
    for enclosure in item.get("enclosures", []):
        if enclosure.get("type", "").startswith("image"):
            return enclosure.get("href") or enclosure.get("url")

    # استخراج تصویر از محتوای HTML
    contents = item.get("content", [])

    for content in contents:
        value = content.get("value", "")
        match = re.search(r'<img[^>]+src=["\']([^"\']+)', value)

        if match:
            return html.unescape(match.group(1))

    description = item.get("description", "")
    match = re.search(r'<img[^>]+src=["\']([^"\']+)', description)

    if match:
        return html.unescape(match.group(1))

    return None


def send_news(title, link, image_url=None):

    persian_title = translate_to_farsi(title)

    message = (
        "⚽ <b>اسپورتینو | اخبار ورزشی</b>\n\n"
        f"📰 {html.escape(persian_title)}\n\n"
        f'🔗 <a href="{html.escape(link, quote=True)}">'
        "مشاهده منبع خبر</a>\n\n"
        "━━━━━━━━━━━━━━\n"
        "🏆 اخبار روز ورزش"
    )

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    # ارسال عکس و کپشن
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

    # اگر عکس ارسال نشد، متن ارسال شود
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

    # جمع‌آوری خبرها از تمام منابع
    for rss_url in RSS_URLS:

        try:
            feed = feedparser.parse(rss_url)

            for item in feed.entries:

                link = item.get("link", "")
                title = item.get("title", "")

                if not link or not title:
                    continue

                if link in sent:
                    continue

                news_list.append({
                    "title": title,
                    "link": link,
                    "image": get_image(item),
                    "date": item.get("published_parsed")
                })

        except Exception:
            continue

    # حذف خبرهای تکراری
    unique_news = []
    seen_links = set()

    for news in news_list:
        if news["link"] not in seen_links:
            seen_links.add(news["link"])
            unique_news.append(news)

    # جدیدترین خبرها در اولویت
    unique_news.sort(
        key=lambda x: x["date"] or (0, 0, 0, 0, 0, 0, 0, 0, 0),
        reverse=True
    )

    # ارسال حداکثر ۳ خبر در هر اجرا
    new_sent = []

    for news in unique_news[:MAX_POSTS_PER_RUN]:

        try:
            send_news(
                news["title"],
                news["link"],
                news["image"]
            )

            new_sent.append(news["link"])

        except Exception as e:
            print("Send error:", e)

    save_sent(sent + new_sent)

    print("News sent:", len(new_sent))


if __name__ == "__main__":
    main()
