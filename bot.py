import os
import json
import requests
import feedparser
import html

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = os.environ["CHANNEL_ID"]

RSS_URLS = [
    "https://feeds.bbci.co.uk/sport/football/rss.xml",
]

SENT_FILE = "sent_news.json"


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
        url = "https://translate.googleapis.com/translate_a/single"

        response = requests.get(
            url,
            params={
                "client": "gtx",
                "sl": "auto",
                "tl": "fa",
                "dt": "t",
                "q": text
            },
            timeout=15
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
    media = item.get("media_content", [])

    for m in media:
        if m.get("url"):
            return m["url"]

    # تصویر بندانگشتی
    thumbnails = item.get("media_thumbnail", [])

    for t in thumbnails:
        if t.get("url"):
            return t["url"]

    # تصاویر ضمیمه RSS
    enclosures = item.get("enclosures", [])

    for e in enclosures:
        if e.get("type", "").startswith("image"):
            return e.get("href") or e.get("url")

    return None


def send_news(title, link, image_url=None):

    persian_title = translate_to_farsi(title)

    message = (
        "⚽ <b>اسپورتینو | اخبار ورزشی</b>\n\n"
        f"📰 {html.escape(persian_title)}\n\n"
        f'🔗 <a href="{html.escape(link, quote=True)}">'
        "مشاهده خبر اصلی</a>\n\n"
        "━━━━━━━━━━━━━━\n"
        "📢 @Sportino"
    )

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"

    # ارسال عکس همراه خبر
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
            return

        except Exception:
            pass

    # اگر عکس قابل ارسال نبود، متن ارسال می‌شود
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


def main():
    sent = load_sent()
    new_sent = []

    for rss_url in RSS_URLS:
        feed = feedparser.parse(rss_url)

        for item in feed.entries[:5]:

            link = item.get("link", "")
            title = item.get("title", "خبر ورزشی")

            if not link or link in sent or link in new_sent:
                continue

            image_url = get_image(item)

            send_news(title, link, image_url)

            new_sent.append(link)

    save_sent(sent + new_sent)


if __name__ == "__main__":
    main()
