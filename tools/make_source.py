#!/usr/bin/env python3
"""記事(notes_src/<ID>.md)から、NotebookLM に入れる音声用のソース原稿(txt)を作る。
図の行は「記事の図N」への案内と、図の中身の説明に置き換える（音声は図を見せられないため）。
使い方: python3 tools/make_source.py <ID> [出力先ディレクトリ]   既定の出力先は Googleドライブの Download"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "podcast/ap/notes_src")
DEF_OUT = os.path.expanduser("~/Library/CloudStorage/GoogleDrive-hidecars@gmail.com/マイドライブ/Download")


def describe(img):
    js = os.path.join(SRC, os.path.splitext(img)[0] + ".json")
    if not os.path.exists(js):
        return ""
    d = json.load(open(js, encoding="utf-8"))
    parts = []
    for row in d.get("rows", []):
        parts.append(" ／ ".join((n.get("label", "") + ("（" + n["sub"] + "）" if n.get("sub") else "")).replace("\n", " ")
                                 for n in row if not n.get("spacer")))
    s = "図の中身（上から順）：" + " → ".join(parts)
    if d.get("note"):
        s += "。注記：" + d["note"].replace("\n", " ")
    return s


def main(id_, out=DEF_OUT):
    md = open(os.path.join(SRC, id_ + ".md"), encoding="utf-8").read()
    n = [0]

    def fig(m):
        n[0] += 1
        return f"【記事の図{n[0]}：{m.group(1)}】音声では「記事の図{n[0]}を開いて見てください」と案内する。{describe(m.group(2))}"

    txt = re.sub(r"^!\[(.*?)\]\((.+?)\)\s*$", fig, md, flags=re.M)
    path = os.path.join(out, f"{id_}_詳細原稿.txt")
    open(path, "w", encoding="utf-8").write(txt)
    print(path, len(txt), "字 / 図", n[0], "枚")


if __name__ == "__main__":
    main(sys.argv[1], *(sys.argv[2:3]))
