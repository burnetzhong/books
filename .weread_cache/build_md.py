#!/usr/bin/env python3
"""Build a comprehensive WeRead notes markdown document."""
import json, os, datetime
from collections import defaultdict

CACHE = "/Users/bytedance/Documents/Books/.weread_cache"
NOTES_DIR = os.path.join(CACHE, "notes")
OUT = "/Users/bytedance/Documents/Books/微信读书笔记.md"

# load aggregated stats
with open(os.path.join(CACHE, "books_with_notes.json")) as f:
    books_meta = json.load(f)

# index meta by bookId
meta_by_id = {b["bookId"]: b for b in books_meta}

def fmt_ts(ts):
    if not ts: return ""
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""

def fmt_dur(sec):
    if not sec: return "0 分钟"
    sec = int(sec)
    h, m = sec // 3600, (sec % 3600) // 60
    if h: return f"{h} 小时 {m} 分钟"
    return f"{m} 分钟"

# load overall stats from raw cached file
def load_stats():
    return None

# Build TOC + per-book sections
def deep_link(bid, ch=None, r=None):
    if r and ch:
        s, e = r.split("-") if "-" in r else (r, r)
        return f"weread://bestbookmark?bookId={bid}&chapterUid={ch}&rangeStart={s}&rangeEnd={e}"
    if ch:
        return f"weread://reading?bId={bid}&chapterUid={ch}"
    return f"weread://reading?bId={bid}"

def build_book_section(meta):
    bid = meta["bookId"]
    fpath = os.path.join(NOTES_DIR, f"{bid}.json")
    if not os.path.exists(fpath):
        return ""
    with open(fpath) as f:
        data = json.load(f)
    title = meta["title"]
    author = meta.get("author") or ""
    translator = meta.get("translator") or ""
    progress = meta.get("readingProgress", 0)
    status_label = "已读完" if meta.get("markedStatus") == 4 else f"在读 ({progress}%)"

    # parse bookmarks
    bookmarks = data.get("bookmarks", {}).get("updated", []) or []
    chapters_map = {}
    for ch in data.get("bookmarks", {}).get("chapters", []) or []:
        chapters_map[ch["chapterUid"]] = ch
    # group bookmarks by chapter
    bm_by_chap = defaultdict(list)
    for bm in bookmarks:
        bm_by_chap[bm.get("chapterUid", 0)].append(bm)

    # parse reviews
    reviews_raw = data.get("reviews", {}).get("reviews", []) or []
    rev_by_chap = defaultdict(list)
    whole_book_reviews = []
    for rr in reviews_raw:
        rv = rr.get("review", {})
        if rv.get("type") == 4 or (rv.get("isFinish") is not None and not rv.get("chapterName")):
            whole_book_reviews.append(rv)
        else:
            ch_uid = rv.get("chapterUid", 0)
            rev_by_chap[ch_uid].append(rv)

    # also build a range index for review-on-highlight matching
    review_by_range = defaultdict(list)
    for rv in reviews_raw:
        v = rv.get("review", {})
        if v.get("range"):
            review_by_range[(v.get("chapterUid"), v.get("range"))].append(v)

    lines = []
    lines.append(f"### {title}")
    meta_parts = []
    if author: meta_parts.append(f"**作者**：{author}")
    if translator: meta_parts.append(f"**译者**：{translator}")
    meta_parts.append(f"**状态**：{status_label}")
    counts = []
    if meta.get("noteCount"): counts.append(f"划线 {meta['noteCount']}")
    if meta.get("reviewCount"): counts.append(f"想法 {meta['reviewCount']}")
    if meta.get("bookmarkCount"): counts.append(f"书签 {meta['bookmarkCount']}")
    if counts: meta_parts.append("**笔记**：" + " · ".join(counts))
    lines.append(" ｜ ".join(meta_parts))
    lines.append("")
    lines.append(f"[在微信读书中打开]({deep_link(bid)})")
    lines.append("")

    # whole-book reviews (书评)
    if whole_book_reviews:
        lines.append("#### 整本书评")
        for rv in sorted(whole_book_reviews, key=lambda x: x.get("createTime", 0)):
            star = rv.get("star", -1)
            star_txt = ""
            if star and star > 0:
                star_txt = f" · {'★' * (star // 2)}"
            ct = fmt_ts(rv.get("createTime"))
            content = (rv.get("content") or "").strip()
            if not content: continue
            lines.append(f"> 📝 {content}")
            lines.append(f"> <sub>{ct}{star_txt}</sub>")
            lines.append("")

    # chapter ordering: by chapterIdx if known
    all_chap_uids = set(bm_by_chap.keys()) | set(rev_by_chap.keys())
    def chap_order(uid):
        c = chapters_map.get(uid)
        return c["chapterIdx"] if c and "chapterIdx" in c else 9999
    sorted_chaps = sorted(all_chap_uids, key=chap_order)

    if sorted_chaps:
        lines.append("#### 划线 & 想法")
        for uid in sorted_chaps:
            ch = chapters_map.get(uid)
            ch_title = ch["title"] if ch and ch.get("title") else f"章节 {uid}"
            lines.append(f"\n**{ch_title}**\n")
            # bookmarks sorted by range start
            def range_key(item):
                r = item.get("range", "0-0")
                try: return int(r.split("-")[0])
                except: return 0
            bms = sorted(bm_by_chap.get(uid, []), key=range_key)
            shown_review_ids = set()
            for bm in bms:
                txt = (bm.get("markText") or "").strip()
                if not txt: continue
                lines.append(f"> {txt}")
                # attached review on same range
                attached = review_by_range.get((uid, bm.get("range")), [])
                for av in attached:
                    rid = av.get("reviewId")
                    if rid in shown_review_ids: continue
                    shown_review_ids.add(rid)
                    c = (av.get("content") or "").strip()
                    if c:
                        lines.append(f">> 💭 {c}")
                lines.append("")
            # chapter-level reviews not tied to a highlight
            for rv in sorted(rev_by_chap.get(uid, []), key=lambda x: x.get("createTime", 0)):
                rid = rv.get("reviewId")
                if rid in shown_review_ids: continue
                if rv.get("range") and (uid, rv.get("range")) in review_by_range and rv in review_by_range[(uid, rv.get("range"))]:
                    # was attached but bookmark missing — show standalone
                    pass
                content = (rv.get("content") or "").strip()
                abstract = (rv.get("abstract") or "").strip()
                if not content and not abstract: continue
                if abstract:
                    lines.append(f"> {abstract}")
                if content:
                    lines.append(f">> 💭 {content}")
                lines.append("")

    lines.append("---\n")
    return "\n".join(lines)


# Build document
out_lines = []
today = datetime.date.today().strftime("%Y-%m-%d")

# ===== Header =====
out_lines.append("# 微信读书笔记")
out_lines.append("")
out_lines.append(f"> 导出日期：{today}")
out_lines.append("")

# Stats summary (from cached overall stats — re-read from the saved curl)
# We don't have the raw cached file from earlier, so embed the known headline numbers.
total_books_with_notes = len(books_meta)
total_review = sum(b["reviewCount"] for b in books_meta)
total_notes = sum(b["noteCount"] for b in books_meta)
total_bm = sum(b["bookmarkCount"] for b in books_meta)
total_all = total_review + total_notes + total_bm

out_lines.append("## 一、阅读总览")
out_lines.append("")
out_lines.append("### 累计数据（自注册以来）")
out_lines.append("")
out_lines.append("| 指标 | 数值 |")
out_lines.append("|------|------|")
out_lines.append("| 注册时间 | 2016-02-22 |")
out_lines.append("| 累计阅读天数 | 1607 天 |")
out_lines.append("| 累计阅读时长 | 约 1175 小时（4,022,646 秒） |")
out_lines.append("| 有笔记的书 | 230 本 |")
out_lines.append(f"| 笔记总数 | {total_all} 条（划线 {total_notes} · 想法 {total_review} · 书签 {total_bm}） |")
out_lines.append("")

out_lines.append("### 2025 年度数据（截至导出日）")
out_lines.append("")
out_lines.append("| 指标 | 数值 |")
out_lines.append("|------|------|")
out_lines.append("| 阅读天数 | 105 天 |")
out_lines.append("| 总时长 | 约 87 小时 43 分钟 |")
out_lines.append("| 日均阅读 | 约 37 分钟 |")
out_lines.append("| 读过 | 39 本（读完 9 本） |")
out_lines.append("| 偏好分类 | 经济理财、个人成长、社会小说、文学、情感小说 |")
out_lines.append("| 文字阅读占比 | 55% （听书 45%） |")
out_lines.append("")

out_lines.append("### 2025 年阅读时长最长的 10 本")
out_lines.append("")
out_lines.append("| 排名 | 书名 | 作者 | 阅读时长 |")
out_lines.append("|------|------|------|----------|")
ranked = [
    ("The Prize", "Daniel Yergin", "12 小时 24 分钟"),
    ("The Rise of Xi Jinping and China's Superpower Future", "Chun Han Wong", "10 小时 18 分钟"),
    ("石油战争：石油政治决定世界新秩序（增订版）", "[美]威廉·恩道尔", "9 小时 32 分钟"),
    ("约会软件相亲实录", "阿菲", "8 小时 33 分钟（单日阅读最久）"),
    ("Common Knowledge and the Mysteries of Money, Power, and Everyday Life", "Steven Pinker", "6 小时 11 分钟"),
    ("【精排】补玉山居", "严歌苓", "4 小时 52 分钟"),
    ("一地鸡毛（典藏版）", "刘震云", "4 小时 4 分钟"),
    ("性心理学", "[英]霭理士／潘光旦 译", "3 小时 49 分钟"),
    ("金色笔记", "[英]多丽丝·莱辛", "3 小时 3 分钟"),
    ("The Secret Network of Nature", "Peter Wohlleben", "2 小时 45 分钟"),
]
for i, (t, a, d) in enumerate(ranked, 1):
    out_lines.append(f"| {i} | {t} | {a} | {d} |")
out_lines.append("")

# ===== Notes content =====
out_lines.append("## 二、书籍笔记 Top 排行（按笔记数）")
out_lines.append("")
out_lines.append("仅列出当前可导出内容（划线 + 想法）的书籍，按总笔记数从多到少排列。")
out_lines.append("")

# Header table for all books with notes
out_lines.append("| # | 书名 | 作者 | 划线 | 想法 | 状态 |")
out_lines.append("|---|------|------|------|------|------|")
shown_books = [b for b in books_meta if (b["reviewCount"] + b["noteCount"]) > 0]
for i, b in enumerate(shown_books, 1):
    status = "✓ 读完" if b.get("markedStatus") == 4 else f"{b.get('readingProgress',0)}%"
    title = b["title"].replace("|", "\\|")
    author = (b.get("author") or "").replace("|", "\\|")
    out_lines.append(f"| {i} | {title} | {author} | {b['noteCount']} | {b['reviewCount']} | {status} |")
out_lines.append("")

# ===== Detailed notes content — focus on books with >= 3 exportable notes =====
out_lines.append("## 三、笔记内容详录")
out_lines.append("")
out_lines.append("以下按笔记数从多到少呈现每本书的详细划线与想法（含 3 条以上笔记的书籍）。")
out_lines.append("> `>` 表示划线原文；`>>` 💭 表示对应的个人想法/点评。")
out_lines.append("")

deep_books = [b for b in shown_books if (b["reviewCount"] + b["noteCount"]) >= 3]
for b in deep_books:
    section = build_book_section(b)
    if section:
        out_lines.append(section)

# Also add a brief section for shorter-note books
short_books = [b for b in shown_books if (b["reviewCount"] + b["noteCount"]) < 3]
if short_books:
    out_lines.append("## 四、其他零散笔记书籍")
    out_lines.append("")
    out_lines.append("以下书籍仅有 1-2 条笔记，仅列出内容摘要：")
    out_lines.append("")
    for b in short_books:
        sec = build_book_section(b)
        if sec:
            out_lines.append(sec)

# Write
with open(OUT, "w") as f:
    f.write("\n".join(out_lines))

# Summary
import os
size = os.path.getsize(OUT)
print(f"Wrote: {OUT}")
print(f"Size: {size/1024:.1f} KB")
print(f"Books detailed: {len(deep_books)}")
print(f"Books listed only: {len(short_books)}")
