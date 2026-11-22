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
        json.dump(sent[-300:], f, ensure_ascii=False)

def send_news(title, link):
    message = (
        "⚽ <b>SPORTINO | اخبار ورزشی</b>\n\n"
        f"📰 {html.escape(title)}\n\n"
        f"🔗 <a href='{html.escape(link, quote=True)}'>مشاهده خبر اصلی</a>"
    )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(url, data={
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML"
    })

    response.raise_for_status()

def main():
    sent = load_sent()
    new_sent = []

    for rss_url in RSS_URLS:
        feed = feedparser.parse(rss_url)

        for item in feed.entries[:10]:
            link = item.get("link", "")
            title = item.get("title", "خبر ورزشی")

            if not link or link in sent:
                continue

            send_news(title, link)
            new_sent.append(link)

    save_sent(sent + new_sent)

if __name__ == "__main__":
    main()
