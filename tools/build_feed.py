#!/usr/bin/env python3
"""
応用情報 午後問題 Podcast v2 - RSS / 学習ノート生成スクリプト（標準ライブラリのみ）

使い方:
  python3 tools/build_feed.py            # リポジトリ直下で実行
  python3 tools/build_feed.py --check    # 生成せず、不足ファイルだけ表示

前提ディレクトリ（リポジトリ直下からの相対パス）:
  podcast/ap/episodes/<ID>.m4a      音声（ID例: 2025r07h-infosec）
  podcast/ap/notes_src/<ID>.md      学習ノート（NotebookLMのレポートをMarkdownで保存）
  podcast/ap/artwork.jpg            番組アートワーク（3000x3000推奨、任意）
  tools/episodes.csv                マスター表から書き出したエピソード一覧

生成物:
  podcast/ap/feed.xml               全分野フィード
  podcast/ap/feed_<分野コード>.xml   分野別フィード
  podcast/ap/notes/<ID>.html        iPhone閲覧用ノート
  podcast/ap/index.html             エピソード一覧ページ
"""
import csv, html, os, re, subprocess, sys, json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import quote

# ===== 設定 =====
SITE = "https://hidecars.github.io"
BASE = "podcast/ap"
SHOW_TITLE = "応用情報 午後問題 1問1解説"
SHOW_AUTHOR = "hidecars"
SHOW_DESC = "応用情報技術者試験の午後問題を1問ずつ解説する学習用Podcast。IPA公開の問題冊子・解答例・採点講評を基に生成AIで作成。"
# 音声の置き場所: "pages" = GitHub Pages内 / "releases" = GitHub Releases
AUDIO_HOST = os.environ.get("AUDIO_HOST", "releases")
GH_REPO = "hidecars/hidecars.github.io"
FIELD_ORDER = ["infosec", "network", "projmng", "servicemng", "sysaudit", "sysdev"]
FIELD_NAME = {"infosec": "情報セキュリティ", "network": "ネットワーク", "projmng": "プロジェクトマネジメント",
              "servicemng": "サービスマネジメント", "sysaudit": "システム監査", "sysdev": "情報システム開発"}
JST = timezone(timedelta(hours=9))

ROOT = os.getcwd()
EP_DIR = os.path.join(ROOT, BASE, "episodes")
SRC_DIR = os.path.join(ROOT, BASE, "notes_src")
NOTE_DIR = os.path.join(ROOT, BASE, "notes")


def load_catalog():
    path = os.path.join(ROOT, "tools", "episodes.csv")
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_shownotes():
    """tools/shownotes.csv（id, summary, keywords, doc_url）を読み込む。無ければ空。
    summary : 番組説明欄に出す問題の概要（2〜3文）
    keywords: 決め手キーワード（「／」区切り）
    doc_url : Googleドキュメントに保存した詳細ノートのURL（リンク共有＝閲覧者）"""
    path = os.path.join(ROOT, "tools", "shownotes.csv")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def duration_sec(path):
    """ffprobeで再生時間(秒)を取得。無ければ0。"""
    try:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
                             capture_output=True, text=True, timeout=30).stdout
        return int(float(json.loads(out)["format"]["duration"]))
    except Exception:
        return 0


def hms(sec):
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def pubdate(ep, index):
    """試験回の古い順に並ぶよう、試験回コードから疑似日付を作る（新しい回ほど新しい日付）。
    例: 2025r07h -> 2025-04-01, 2025r07a -> 2025-10-01。同一回内は分野順に1分ずつずらす。"""
    y = int(ep["exam"][:4])
    m = 4 if ep["exam"].endswith("h") else 10
    base = datetime(y, m, 1, 6, 0, tzinfo=JST)
    return base + timedelta(minutes=FIELD_ORDER.index(ep["field_code"]) if ep["field_code"] in FIELD_ORDER else index)


def audio_url(ep_id):
    if AUDIO_HOST == "releases":
        tag = "ap-" + ep_id.split("-")[0]
        return f"https://github.com/{GH_REPO}/releases/download/{tag}/{ep_id}.m4a"
    return f"{SITE}/{BASE}/episodes/{quote(ep_id)}.m4a"


# ---- 最小限のMarkdown→HTML変換（見出し・表・箇条書き・太字・段落） ----
def inline(s):
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    return s


def figure(src, alt):
    path = os.path.join(SRC_DIR, src)
    js = os.path.splitext(path)[0] + ".json"
    if os.path.exists(js) and (not os.path.exists(path) or os.path.getmtime(js) > os.path.getmtime(path)):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import make_diagram
        make_diagram.convert(js)
    if not os.path.exists(path):
        return f"<p>（図が見つかりません: {html.escape(src)}）</p>"
    svg = open(path, encoding="utf-8").read()
    cap = f"<figcaption>{inline(alt)}</figcaption>" if alt else ""
    return f"<figure>{svg}{cap}</figure>"


def is_quiz_heading(t):
    return any(k in t for k in ("クイズ", "セルフチェック"))


QA_RE = re.compile(r"^(Q\d*[^→]*?)\s*→\s*(.+)$")


def md_to_html(md):
    """Markdown→HTML。クイズ見出し（クイズ／セルフチェック）には id='quiz' を付け、
    その中の「- 問い → 答え」は、タップで答えが開く形（details）にする。"""
    out, lines, i, in_quiz = [], md.splitlines(), 0, False
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1; continue
        m = re.match(r"^(#{1,4})\s+(.*)", ln)
        if m:
            lv = len(m.group(1)) + (1 if len(m.group(1)) < 4 else 0)
            in_quiz = is_quiz_heading(m.group(2))
            hid = " id='quiz'" if in_quiz else f" id='s{len(out)}'"
            out.append(f"<h{lv}{hid}>{inline(m.group(2))}</h{lv}>"); i += 1; continue
        if ln.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c or "--") for c in r)]
            if rows:
                t = ["<div class='tw'><table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>"]
                t += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:]]
                out.append("".join(t) + "</tbody></table></div>")
            continue
        if re.match(r"^\s*([-*・]|\d+[.)])\s+", ln):
            tag = "ol" if re.match(r"^\s*\d+[.)]\s+", ln) else "ul"
            items = []
            while i < len(lines) and re.match(r"^\s*([-*・]|\d+[.)])\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*・]|\d+[.)])\s+", "", lines[i])); i += 1
            if in_quiz and all(QA_RE.match(x) for x in items):
                qa = []
                for n, x in enumerate(items, 1):
                    q, a = QA_RE.match(x).groups()
                    q = re.sub(r"^Q\d*\s*", "", q).strip()
                    qa.append(f"<details class='qa'><summary><b>Q{n}</b> {inline(q)}</summary><p>{inline(a)}</p></details>")
                out.append("".join(qa) + "<p class='meta'>タップすると答えが開きます。<a href='#top'>ページの先頭へ</a></p>")
            else:
                out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        m = re.match(r"^!\[(.*?)\]\((.+?)\)\s*$", ln.strip())
        if m:  # 図：notes_src/img/*.svg をHTMLに埋め込む（画面幅に合わせて縮尺、ダークモード対応）
            out.append(figure(m.group(2), m.group(1))); i += 1; continue
        if ln.startswith("```"):
            i += 1; buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre>" + html.escape("\n".join(buf)) + "</pre>"); continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,4}\s|\||```|\s*([-*・]|\d+[.)])\s)", lines[i]):
            para.append(inline(lines[i].strip())); i += 1
        out.append("<p>" + "<br>".join(para) + "</p>")
    return "\n".join(out)


PAGE_CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--sub:#6e6e73;--line:#d2d2d7;--acc:#0a66c2;--th:#f5f5f7}
@media (prefers-color-scheme:dark){:root{--bg:#000;--fg:#f5f5f7;--sub:#a1a1a6;--line:#38383a;--acc:#4ea1ff;--th:#1c1c1e}}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:16px/1.7 -apple-system,"Hiragino Sans",sans-serif;max-width:760px;margin-inline:auto}
h1{font-size:1.3rem;line-height:1.4}h2{font-size:1.1rem;border-bottom:1px solid var(--line);padding-bottom:4px;margin-top:2em}
h3{font-size:1rem}.meta{color:var(--sub);font-size:.85rem}a{color:var(--acc)}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}th,td{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}
th{background:var(--th)}pre{white-space:pre-wrap;background:var(--th);padding:10px;border-radius:6px;font-size:.85rem}
audio{width:100%;margin:12px 0}li{margin:2px 0}
.nav{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 4px}.nav a{display:inline-block;padding:6px 12px;border:1px solid var(--acc);border-radius:16px;text-decoration:none;font-size:.9rem}
.nav a.main{background:var(--acc);color:var(--bg)}
details.qa{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0}details.qa summary{cursor:pointer}
details.qa[open] summary{margin-bottom:6px}details.qa p{margin:0;color:var(--acc);font-weight:600}
h2,h3{scroll-margin-top:12px}
:root{--box:#f5f5f7;--key:#e8f1fb;--risk:#fdecea;--riskl:#c62828}
@media (prefers-color-scheme:dark){:root{--box:#1c1c1e;--key:#0d2a45;--risk:#3a1614;--riskl:#ff6b5e}}
figure{margin:12px 0}figcaption{color:var(--sub);font-size:.8rem;text-align:center}
svg.dg{width:100%;max-width:520px;height:auto;display:block;margin:0 auto;font-family:-apple-system,"Hiragino Sans",sans-serif}
.dg-box{fill:var(--box);stroke:var(--sub);stroke-width:1.2}.dg-box.key{fill:var(--key);stroke:var(--acc);stroke-width:2}
.dg-box.dash{stroke-dasharray:5 4}.dg-box.risk{fill:var(--risk);stroke:var(--riskl);stroke-width:1.6}
.dg-txt{fill:var(--fg);font-size:13px;font-weight:600}.dg-sub{fill:var(--sub);font-size:10.5px}
.dg-edge{stroke:var(--sub);stroke-width:1.4}.dg-edge.dash{stroke-dasharray:4 4}.dg-ah{fill:var(--sub)}
.dg-lbg{fill:var(--bg);stroke:var(--line)}.dg-lbl{fill:var(--fg);font-size:10.5px}
.dg-title{fill:var(--fg);font-size:13px;font-weight:700}.dg-note{fill:var(--sub);font-size:10.5px}
"""


def parse_note(md):
    """Podcast説明欄用に、記事原稿から要点を抜き出す。
    返す値: point（ひとことで）, situation（状況の箇条書き）, qa（[(設問, 問われていること, キーワード)]）, review（採点講評）"""
    info = {"point": "", "situation": [], "qa": [], "review": ""}
    sec = ""
    for ln in md.splitlines():
        t = ln.strip()
        m = re.match(r"^#{2,4}\s+(.*)", t)
        if m:
            sec = m.group(1); continue
        if not t or t.startswith("!["):
            continue
        if t.startswith("※採点講評"):
            info["review"] = t.lstrip("※").replace("採点講評：", "").strip(); continue
        if ("ひとことで" in sec or "問うこと" in sec) and not info["point"] and not t.startswith(("|", "-")):
            info["point"] = t
        elif "状況" in sec and t.startswith("- "):
            info["situation"].append(t[2:].strip())
        elif ("設問" in sec or "解答キーワード" in sec) and t.startswith("|"):
            cells = [c.strip() for c in t.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] not in ("設問",) and not re.fullmatch(r":?-{2,}:?", cells[0]):
                info["qa"].append(cells)
    return info


def plain(s):
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s)


def page(title, body):
    return (f"<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)}</title><style>{PAGE_CSS}</style></head><body>{body}</body></html>")


def ep_title(ep):
    return f"{ep['era']}{ep['season']} {ep['qno']} {ep['field']}｜{ep['theme']}"


def build():
    cat = load_catalog()
    sn = load_shownotes()
    os.makedirs(NOTE_DIR, exist_ok=True)
    have = []
    missing_notes = []
    for idx, ep in enumerate(cat):
        mp = os.path.join(EP_DIR, ep["id"] + ".m4a")
        if not os.path.exists(mp):
            continue
        ep["size"] = os.path.getsize(mp)
        ep["dur"] = duration_sec(mp)
        ep["date"] = pubdate(ep, idx)
        src = os.path.join(SRC_DIR, ep["id"] + ".md")
        ep["note_url"] = ""
        ep["md"] = {}
        if os.path.exists(src):
            md = open(src, encoding="utf-8").read()
            md = re.sub(r"\A\s*# [^\n]*\n", "", md)   # 原稿の題名はページ見出し(h1)と重なるので除く
            body = md_to_html(md)
            ep["md"] = parse_note(md)
            nav = "<nav class='nav'>"
            if "id='quiz'" in body:
                nav += "<a class='main' href='#quiz'>▶ クイズに挑戦</a>"
            for h in re.findall(r"<h[23] id='(s\d+)'>(.*?)</h[23]>", body):
                if any(k in h[1] for k in ("設問", "核心", "キーワード")):
                    label = re.sub(r"^\d+\.\s*", "", h[1])
                    nav += f"<a href='#{h[0]}'>{label}</a>"
                    break
            nav += "</nav>"
            head = (f"<a id='top'></a><p class='meta'>{html.escape(ep['exam'])}｜{html.escape(ep['kind'])}｜"
                    f"<a href='../index.html'>一覧へ</a></p><h1>{html.escape(ep_title(ep))}</h1>"
                    f"{nav}")
            with open(os.path.join(NOTE_DIR, ep["id"] + ".html"), "w", encoding="utf-8") as f:
                f.write(page(ep_title(ep), head + body))
            ep["note_url"] = f"{SITE}/{BASE}/notes/{ep['id']}.html"
        else:
            missing_notes.append(ep["id"])
        s = sn.get(ep["id"], {})
        ep["summary"] = (s.get("summary") or "").strip()
        ep["keywords"] = (s.get("keywords") or "").strip()
        ep["doc_url"] = (s.get("doc_url") or "").strip()
        have.append(ep)

    def write_feed(name, eps, subtitle):
        self_url = f"{SITE}/{BASE}/{name}"
        art = f"{SITE}/{BASE}/artwork.jpg"
        items = []
        for ep in sorted(eps, key=lambda e: e["date"], reverse=True):
            head = f"{ep['era']}{ep['season']} 午後{ep['qno']}（{ep['field']}・{ep['kind']}）テーマ：{ep['theme']}"
            # 番組の説明欄（Apple Podcasts等はHTMLの<p><a>を表示）
            parts = [f"<p>{html.escape(head)}</p>"]
            src_line = f"出典：IPA {ep['era']}度{ep['season']} 応用情報技術者試験 午後 {ep['qno']}（問題冊子・解答例・採点講評）"
            text = [head]
            if ep["summary"]:
                parts.append(f"<p>【概要】{html.escape(ep['summary'])}</p>")
                text.append(f"【概要】{ep['summary']}")
            md = ep.get("md") or {}
            if md.get("point") and not ep["summary"]:
                parts.append(f"<p>【この問題が問うこと】{html.escape(plain(md['point']))}</p>")
                text.append(f"【この問題が問うこと】{plain(md['point'])}")
            if md.get("situation"):
                parts.append("<p>【状況】<br>" + "<br>".join("・" + html.escape(plain(x)) for x in md["situation"]) + "</p>")
                text.append("【状況】\n" + "\n".join("・" + plain(x) for x in md["situation"]))
            if ep["keywords"]:
                parts.append(f"<p>【決め手キーワード】{html.escape(ep['keywords'])}</p>")
                text.append(f"【決め手キーワード】{ep['keywords']}")
            if md.get("qa"):
                rows = []
                for c in md["qa"]:
                    q = c[0] if c[0].startswith("設問") else f"設問{c[0]}"
                    rows.append(f"{q}：{plain(c[1])} → {plain(c[-1])}" if len(c) >= 3 else f"{q} → {plain(c[-1])}")
                parts.append("<p>【設問と解答のキーワード】<br>" + "<br>".join(html.escape(r) for r in rows) + "</p>")
                text.append("【設問と解答のキーワード】\n" + "\n".join(rows))
            if md.get("review"):
                parts.append(f"<p>【採点講評】{html.escape(md['review'])}</p>")
                text.append(f"【採点講評】{md['review']}")
            links = []
            if ep["doc_url"]:
                links.append(f"<a href=\"{html.escape(ep['doc_url'])}\">詳細ノート（Googleドキュメント）</a>")
                text.append(f"詳細ノート：{ep['doc_url']}")
            if ep["note_url"]:
                links.append(f"<a href=\"{ep['note_url']}\">詳細ページ（Web記事）</a>")
                links.append(f"<a href=\"{ep['note_url']}#quiz\">聴き終えたらクイズへ</a>")
                text.append(f"詳細ページ：{ep['note_url']}")
                text.append(f"クイズ：{ep['note_url']}#quiz")
            if links:
                parts.append("<p>" + "<br>".join(links) + "</p>")
            parts.append(f"<p>{html.escape(src_line)}</p>")
            text.append(src_line)
            desc_html = "".join(parts).replace("]]>", "]]&gt;")
            desc_text = "\n".join(text)
            items.append(f"""  <item>
    <title>{html.escape(ep_title(ep))}</title>
    <description><![CDATA[{desc_html}]]></description>
    <content:encoded><![CDATA[{desc_html}]]></content:encoded>
    <itunes:summary>{html.escape(desc_text)}</itunes:summary>
    <link>{html.escape(ep['doc_url'] or ep['note_url'] or self_url)}</link>
    <enclosure url="{audio_url(ep['id'])}" length="{ep['size']}" type="audio/x-m4a"/>
    <guid isPermaLink="false">ap-v2-{ep['id']}</guid>
    <pubDate>{format_datetime(ep['date'])}</pubDate>
    <itunes:duration>{hms(ep['dur'])}</itunes:duration>
    <itunes:episodeType>full</itunes:episodeType>
    <itunes:explicit>false</itunes:explicit>
  </item>""")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel>
  <title>{html.escape(SHOW_TITLE + subtitle)}</title>
  <link>{SITE}/{BASE}/index.html</link>
  <atom:link href="{self_url}" rel="self" type="application/rss+xml"/>
  <language>ja</language>
  <description>{html.escape(SHOW_DESC)}</description>
  <itunes:author>{SHOW_AUTHOR}</itunes:author>
  <itunes:image href="{art}"/>
  <itunes:category text="Education"><itunes:category text="Courses"/></itunes:category>
  <itunes:explicit>false</itunes:explicit>
  <itunes:block>Yes</itunes:block>
  <lastBuildDate>{format_datetime(datetime.now(JST))}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
"""
        with open(os.path.join(ROOT, BASE, name), "w", encoding="utf-8") as f:
            f.write(xml)

    write_feed("feed.xml", have, "")
    for fc in FIELD_ORDER:
        write_feed(f"feed_{fc}.xml", [e for e in have if e["field_code"] == fc], f"（{FIELD_NAME[fc]}）")

    # 一覧ページ
    rows = []
    for ep in sorted(have, key=lambda e: (e["exam"], FIELD_ORDER.index(e["field_code"]))):
        note = f"<a href='notes/{ep['id']}.html'>ノート</a>" if ep["note_url"] else "－"
        rows.append(f"<tr><td>{ep['exam']}</td><td>{ep['qno']}</td><td>{html.escape(ep['field'])}</td>"
                    f"<td>{html.escape(ep['theme'])}</td><td>{hms(ep['dur'])}</td><td>{note}</td></tr>")
    feeds = "".join(f"<li><a href='feed_{fc}.xml'>{FIELD_NAME[fc]}</a></li>" for fc in FIELD_ORDER)
    body = (f"<h1>{SHOW_TITLE}</h1><p class='meta'>公開 {len(have)} 本／最終更新 "
            f"{datetime.now(JST).strftime('%Y/%m/%d %H:%M')} JST</p>"
            f"<h2>購読用RSS</h2><ul><li><a href='feed.xml'>全分野</a></li>{feeds}</ul>"
            f"<h2>エピソード一覧</h2><div class='tw'><table><thead><tr><th>試験回</th><th>問</th><th>分野</th>"
            f"<th>テーマ</th><th>時間</th><th>テキスト</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>")
    with open(os.path.join(ROOT, BASE, "index.html"), "w", encoding="utf-8") as f:
        f.write(page(SHOW_TITLE, body))

    total = sum(e["size"] for e in have)
    print(f"公開エピソード: {len(have)} 本 / 音声合計 {total / 1048576:.1f} MB / AUDIO_HOST={AUDIO_HOST}")
    if missing_notes:
        print("学習ノート未作成:", ", ".join(missing_notes))


def check():
    cat = load_catalog()
    for ep in cat:
        a = os.path.exists(os.path.join(EP_DIR, ep["id"] + ".m4a"))
        n = os.path.exists(os.path.join(SRC_DIR, ep["id"] + ".md"))
        if a or n:
            print(f"{ep['id']:22s} 音声:{'○' if a else '×'} ノート:{'○' if n else '×'}")


if __name__ == "__main__":
    check() if "--check" in sys.argv else build()
