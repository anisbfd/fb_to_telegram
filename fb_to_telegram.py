import json
import os
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

PAGE = os.environ["FB_PAGE"]          # page username, e.g. "myschool"
TOKEN = os.environ["TG_TOKEN"]        # bot token from @BotFather
CHAT = os.environ["TG_CHAT_ID"]       # your chat id or @channelname
STATE_FILE = "state.json"
FAIL_ALERT_AT = 3                     # alert after this many empty runs in a row

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def tg(text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT, "text": text},
        timeout=30,
    )


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"seen": [], "fails": 0, "init": False}


def save_state(state):
    state["seen"] = state["seen"][-300:]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def fetch_posts():
    base = "https://mbasic.facebook.com"
    r = requests.get(f"{base}/{PAGE}", headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    posts = {}
    for a in soup.find_all("a", href=True):
        m = re.search(r"(?:story_fbid=|/posts/)(pfbid\w+|\d+)", a["href"])
        if not m or m.group(1) in posts:
            continue
        box = a.find_parent("article") or a.find_parent("div", attrs={"data-ft": True})
        text = box.get_text(" ", strip=True)[:600] if box else ""
        link = urljoin(base, a["href"]).replace("mbasic.", "www.")
        posts[m.group(1)] = (link, text)
    return posts


def main():
    state = load_state()
    try:
        posts = fetch_posts()
    except Exception as e:
        print("fetch error:", e)
        posts = {}

    if not posts:
        state["fails"] += 1
        if state["fails"] == FAIL_ALERT_AT:
            tg("⚠️ FB bridge: no posts found for several runs. Facebook may be blocking GitHub.")
        save_state(state)
        return

    state["fails"] = 0
    new = [(pid, v) for pid, v in posts.items() if pid not in state["seen"]]

    # first run: just remember what's there, don't spam old posts
    if not state["init"]:
        state["init"] = True
        state["seen"] += [pid for pid, _ in new]
        save_state(state)
        tg(f"✅ FB bridge running. Tracking {len(new)} existing posts.")
        return

    for pid, (link, text) in reversed(new):
        tg(f"{text}\n\n{link}" if text else link)
        state["seen"].append(pid)
    save_state(state)


if __name__ == "__main__":
    main()
