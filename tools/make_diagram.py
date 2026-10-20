#!/usr/bin/env python3
"""
学習ノート用の図（SVG）を、簡単なJSON定義から作る（標準ライブラリのみ）。
スマホの縦長画面で読みやすいよう、上から下へ流れる配置にする。

使い方:
  python3 tools/make_diagram.py podcast/ap/notes_src/img/<ID>.json   # 同名の .svg を出力
  python3 tools/make_diagram.py --all                                 # img/*.json を全部変換

JSONの書き方:
{
  "title": "図のタイトル（任意）",
  "rows": [                                  # 上から順に「段」。1段に1〜3個の箱
    [{"id": "a", "label": "営業部"}],
    [{"id": "b", "label": "夜間バッチ", "sub": "注文→生産計画", "style": "key"}],
    [{"id": "c", "label": "製造部"}, {"id": "d", "label": "監視", "style": "dash"}]
  ],
  "edges": [{"from": "a", "to": "b", "label": "注文情報"}],
  "note": "図の下に出す注記（任意）"
}
空き枠: {"spacer": true}（列の位置をそろえる）
style: 省略=通常 / key=強調（問題の焦点） / dash=点線（監視・管理など補助） / risk=注意（障害・リスク）
"""
import glob, html, json, os, sys

W = 360          # 図の幅（viewBox）。表示時は画面幅いっぱいに縮尺される
PAD = 12
BOX_H = 44
GAP_Y = 46       # 段と段の間（矢印とラベルを置く）
TITLE_H = 26


def esc(s):
    return html.escape(str(s), quote=True)


def layout(spec):
    pos, y = {}, PAD + (TITLE_H if spec.get("title") else 0)
    for row in spec["rows"]:
        n = len(row)
        bw = (W - PAD * (n + 1)) / n
        for i, node in enumerate(row):
            if node.get("spacer"):          # 空き枠（列をそろえるため）
                continue
            h = BOX_H + (14 if node.get("sub") else 0)
            pos[node["id"]] = dict(x=PAD + i * (bw + PAD), y=y, w=bw, h=h, node=node)
        y += max(BOX_H + (14 if nd.get("sub") else 0) for nd in row if not nd.get("spacer")) + GAP_Y
    return pos, y - GAP_Y + PAD


def render(spec):
    pos, height = layout(spec)
    note_lines = spec.get("note", "")
    note_lines = [l for l in note_lines.split("\n") if l] if note_lines else []
    height += len(note_lines) * 16 + (6 if note_lines else 0)
    out = [f'<svg class="dg" viewBox="0 0 {W} {height:.0f}" role="img" aria-label="{esc(spec.get("title", "図"))}" '
           f'xmlns="http://www.w3.org/2000/svg">',
           '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path d="M0,0 L10,5 L0,10 z" class="dg-ah"/></marker></defs>']
    if spec.get("title"):
        out.append(f'<text x="{W/2}" y="{PAD + 14}" class="dg-title" text-anchor="middle">{esc(spec["title"])}</text>')

    # 矢印（箱の下に描く）
    for e in spec.get("edges", []):
        a, b = pos[e["from"]], pos[e["to"]]
        if abs(a["y"] - b["y"]) < 1:                       # 同じ段：横向き
            if a["x"] < b["x"]:
                x1, x2 = a["x"] + a["w"], b["x"]
            else:
                x1, x2 = a["x"], b["x"] + b["w"]
            y1 = y2 = a["y"] + min(a["h"], b["h"]) / 2
        else:                                              # 別の段：縦向き
            down = b["y"] > a["y"]
            x1, x2 = a["x"] + a["w"] / 2, b["x"] + b["w"] / 2
            y1 = a["y"] + (a["h"] if down else 0)
            y2 = b["y"] + (0 if down else b["h"])
        cls = "dg-edge dash" if e.get("dash") else "dg-edge"
        both = ' marker-start="url(#ah)"' if e.get("both") else ""
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="{cls}" marker-end="url(#ah)"{both}/>')
        if e.get("label"):
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            lw = len(e["label"]) * 11 + 10
            out.append(f'<rect x="{mx - lw/2:.1f}" y="{my - 9:.1f}" width="{lw}" height="18" rx="4" class="dg-lbg"/>'
                       f'<text x="{mx:.1f}" y="{my + 4:.1f}" class="dg-lbl" text-anchor="middle">{esc(e["label"])}</text>')

    # 箱
    for p in pos.values():
        nd = p["node"]
        cls = "dg-box " + nd.get("style", "")
        out.append(f'<rect x="{p["x"]:.1f}" y="{p["y"]:.1f}" width="{p["w"]:.1f}" height="{p["h"]}" rx="8" class="{cls.strip()}"/>')
        lines = str(nd["label"]).split("\n")
        cy = p["y"] + (BOX_H / 2) - (len(lines) - 1) * 8 + 5
        for i, ln in enumerate(lines):
            out.append(f'<text x="{p["x"] + p["w"]/2:.1f}" y="{cy + i*16:.1f}" class="dg-txt" text-anchor="middle">{esc(ln)}</text>')
        if nd.get("sub"):
            out.append(f'<text x="{p["x"] + p["w"]/2:.1f}" y="{p["y"] + p["h"] - 9:.1f}" class="dg-sub" text-anchor="middle">{esc(nd["sub"])}</text>')

    for i, ln in enumerate(note_lines):
        out.append(f'<text x="{PAD}" y="{height - PAD - (len(note_lines) - 1 - i) * 16:.1f}" class="dg-note">{esc(ln)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def convert(path):
    spec = json.load(open(path, encoding="utf-8"))
    svg_path = os.path.splitext(path)[0] + ".svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(render(spec))
    return svg_path


if __name__ == "__main__":
    files = glob.glob("podcast/ap/notes_src/img/*.json") if "--all" in sys.argv else sys.argv[1:]
    for p in files:
        print("図を作成:", convert(p))
