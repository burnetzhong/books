#!/usr/bin/env python3
"""从微信读书拉取书架、笔记和阅读统计，生成 docs/data/weread.json。

用法：source ~/.zshrc && python3 scripts/refresh_weread.py
需要环境变量 WEREAD_API_KEY。Key 只在本机使用，不会写进任何文件。
"""
import datetime
import glob
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "data", "weread.json")
GATEWAY = "https://i.weread.qq.com/api/agent/gateway"
SKILL_DIRS = ["~/.agents/skills/weread-skills", "~/.claude/skills/weread-skills"]


def skill_version():
    for d in SKILL_DIRS:
        for f in glob.glob(os.path.join(os.path.expanduser(d), "SKILL.md")):
            m = re.search(r"^version:\s*(\S+)", open(f, encoding="utf-8").read(), re.M)
            if m:
                return m.group(1)
    return "1.0.5"


KEY = os.environ.get("WEREAD_API_KEY")
VERSION = skill_version()


def call(api, **params):
    body = json.dumps({"api_name": api, "skill_version": VERSION, **params}).encode()
    req = urllib.request.Request(GATEWAY, data=body, headers={
        "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if "upgrade_info" in d:
        sys.exit(f"微信读书 skill 需要升级：{d['upgrade_info'].get('message')}")
    if d.get("errcode"):
        sys.exit(f"{api} 调用失败：{d}")
    return d


def year_ts(y):
    return int(datetime.datetime(y, 6, 1).timestamp())


def main():
    if not KEY:
        sys.exit("缺少 WEREAD_API_KEY，先运行 source ~/.zshrc")

    shelf = call("/shelf/sync")
    notebooks, last = [], None
    while True:
        page = call("/user/notebooks", count=100, **({"lastSort": last} if last else {}))
        notebooks += page.get("books", [])
        if page.get("hasMore") != 1 or not page.get("books"):
            break
        last = page["books"][-1]["sort"]
        time.sleep(0.3)

    overall = call("/readdata/detail", mode="overall")
    this_year = datetime.date.today().year
    years = {}
    for y in range(2019, this_year + 1):
        years[y] = call("/readdata/detail", mode="annually", baseTime=year_ts(y))
        time.sleep(0.3)

    # 每本书在任一统计周期里的最长阅读时长（秒）
    longest = {}
    for d in [overall, *years.values()]:
        for x in d.get("readLongest", []):
            b = x.get("book")
            if b:
                longest[b["bookId"]] = max(longest.get(b["bookId"], 0), x["readTime"])

    nb = {b["bookId"]: b for b in notebooks}
    books, seen = [], set()

    def add(bid, title, author, category, finished, read_ts):
        n = nb.get(bid)
        notes = (n["reviewCount"] + n["noteCount"]) if n else 0
        prog = n.get("readingProgress") if n else None
        mins = longest.get(bid, 0) // 60
        f = 1 if finished or prog == 100 else 0
        books.append({
            "id": re.sub(r"[^A-Za-z0-9_\-.~:@+]", "_", str(bid)),
            "t": title, "a": author or "", "c": (category or "").split("-")[0], "cc": category or "",
            "f": f, "n": notes, "p": prog, "r": read_ts or 0, "h": mins,
            "s": round(notes * 2 + f * 10 + mins / 30, 2),
        })
        seen.add(bid)

    for b in shelf.get("books", []):
        add(b["bookId"], b["title"], b.get("author"), b.get("category"),
            b.get("finishReading") == 1, b.get("readUpdateTime"))
    for bid, n in nb.items():
        if bid not in seen:
            bk = n["book"]
            add(bid, bk.get("title", ""), bk.get("author"), "", False, n.get("sort"))
    books.sort(key=lambda b: -b["s"])

    summary = {
        "regist": overall.get("registTime"),
        "total": overall.get("totalReadTime"),
        "days": overall.get("readDays"),
        "stat": [[x["stat"], x["counts"]] for x in overall.get("readStat", [])],
        "cats": [[c["categoryTitle"], c["readingTime"], c["readingCount"]]
                 for c in overall.get("preferCategory", [])],
        "authors": [[a["name"], a["count"], a["readTime"]] for a in overall.get("preferAuthor", [])],
        "time": overall.get("preferTime"),
        "timeWord": overall.get("preferTimeWord"),
        "years": [[y, d.get("totalReadTime"), d.get("readDays")] for y, d in years.items()],
        "longest": [[(x.get("book") or {}).get("title") or (x.get("albumInfo") or {}).get("name"),
                     x["readTime"]] for x in overall.get("readLongest", [])],
        "readRate": overall.get("readRate"),
        "shelfCount": len(shelf.get("books", [])) + len(shelf.get("albums", [])) + (1 if shelf.get("mp") else 0),
    }
    out = {"generatedAt": datetime.date.today().isoformat(), "summary": summary, "books": books}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"已生成 {os.path.relpath(OUT, ROOT)}：{len(books)} 本书，"
          f"累计 {round((summary['total'] or 0) / 3600)} 小时")


if __name__ == "__main__":
    main()
