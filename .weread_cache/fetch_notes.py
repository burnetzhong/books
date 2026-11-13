#!/usr/bin/env python3
import json, os, sys, time
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://i.weread.qq.com/api/agent/gateway"
KEY = os.environ["WEREAD_API_KEY"]
VERSION = "1.0.3"
CACHE = "/Users/bytedance/Documents/Books/.weread_cache/notes"
os.makedirs(CACHE, exist_ok=True)

def call(payload):
    body = json.dumps({**payload, "skill_version": VERSION}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2: raise
            time.sleep(1 + attempt)

def fetch_book(book):
    bid = book["bookId"]
    fpath = os.path.join(CACHE, f"{bid}.json")
    if os.path.exists(fpath):
        return bid, "cached"
    out = {"bookId": bid, "title": book["title"]}
    try:
        if book["noteCount"] > 0:
            out["bookmarks"] = call({"api_name": "/book/bookmarklist", "bookId": bid})
        if book["reviewCount"] > 0:
            # paginate reviews
            all_reviews = []
            chapters_seen = None
            synckey = 0
            while True:
                r = call({"api_name": "/review/list/mine", "bookid": bid,
                          "synckey": synckey, "count": 50})
                all_reviews.extend(r.get("reviews", []))
                if not r.get("hasMore"): break
                new_sk = r.get("synckey")
                if new_sk == synckey or new_sk is None: break
                synckey = new_sk
            out["reviews"] = {"reviews": all_reviews, "totalCount": len(all_reviews)}
        with open(fpath, "w") as f:
            json.dump(out, f, ensure_ascii=False)
        return bid, "ok"
    except Exception as e:
        return bid, f"err:{e}"

with open("/Users/bytedance/Documents/Books/.weread_cache/books_with_notes.json") as f:
    books = json.load(f)

print(f"Fetching {len(books)} books...")
done = 0
errs = []
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(fetch_book, b): b for b in books}
    for fut in as_completed(futs):
        bid, status = fut.result()
        done += 1
        if status.startswith("err"):
            errs.append((bid, status))
        if done % 20 == 0:
            print(f"  {done}/{len(books)}")
print(f"Done: {done}, errors: {len(errs)}")
for bid, msg in errs[:10]:
    print(" ", bid, msg)
