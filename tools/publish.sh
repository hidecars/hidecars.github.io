#!/bin/bash
# 応用情報 Podcast v2 公開スクリプト（Mac用 / Automatorの「シェルスクリプトを実行」からも呼べる）
#
# 使い方:
#   1) NotebookLMからダウンロードした音声を inbox/ に置く。
#      ファイル名は「<ID>.<拡張子>」にする（例: 2025r07h-infosec.wav / .m4a / .mp3）
#   2) 学習ノート（Markdown）を podcast/ap/notes_src/<ID>.md として保存
#   3) このスクリプトを実行:  bash tools/publish.sh
#
# 環境変数:
#   REPO=...           リポジトリの場所（既定: Googleドライブ「マイドライブ/GitHub/hidecars.github.io」→無ければiCloud）
#   AUDIO_HOST=releases releases(既定・音声をGitHub Releasesに置く) | pages
#   BITRATE=64k        AAC モノラルのビットレート
#   DRY_RUN=1          git push を行わない（動作確認用）
#
# 必要: ffmpeg（brew install ffmpeg）、git、python3、（AUDIO_HOST=releases の場合 gh CLI）
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# リポジトリの場所：Googleドライブ（パソコン版）の「マイドライブ/GitHub/hidecars.github.io」を優先。
# 見つからなければ旧の iCloud Drive。REPO=... で直接指定も可。
find_repo() {
  local d
  for d in "$HOME"/Library/CloudStorage/GoogleDrive-*/"マイドライブ" "$HOME"/Library/CloudStorage/GoogleDrive-*/"My Drive"; do
    [ -d "$d/GitHub/hidecars.github.io/.git" ] && { echo "$d/GitHub/hidecars.github.io"; return; }
  done
  echo "$HOME/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io"
}
REPO="${REPO:-$(find_repo)}"
INBOX="$REPO/inbox"
EP_DIR="$REPO/podcast/ap/episodes"
AUDIO_HOST="${AUDIO_HOST:-releases}"
BITRATE="${BITRATE:-64k}"
DRY_RUN="${DRY_RUN:-0}"

cd "$REPO"
mkdir -p "$INBOX/done" "$EP_DIR" podcast/ap/notes_src

# Chromeのダウンロード先（Googleドライブの「マイドライブ/Download」）も音声の受け口にする。
# ファイル名が「<ID>.m4a」（例: 2025r07h-network.m4a）のものだけ取り込み、それ以外は触らない。
DL="${DL:-}"
if [ -z "$DL" ]; then
  for d in "$HOME"/Library/CloudStorage/GoogleDrive-*/"マイドライブ"/Download "$HOME"/Library/CloudStorage/GoogleDrive-*/"My Drive"/Download; do
    [ -d "$d" ] && { DL="$d"; break; }
  done
fi

converted=""
for src in "$INBOX"/* ${DL:+"$DL"/*}; do
  [ -f "$src" ] || continue
  name="${src##*/}"
  ext="$(echo "${name##*.}" | tr 'A-Z' 'a-z')"
  case "$ext" in wav|m4a|mp3|mp4|aac) ;; *) continue ;; esac
  id="${name%.*}"
  if ! grep -q "^${id}," tools/episodes.csv; then
    [ "${src%/*}" = "$INBOX" ] && echo "スキップ（episodes.csv に無いID）: $name"
    continue
  fi
  out="$EP_DIR/${id}.m4a"
  echo "変換中: $name -> ${id}.m4a"
  ffmpeg -nostdin -y -loglevel error -i "$src" -vn -ac 1 -ar 44100 -c:a aac -b:a "$BITRATE" -movflags +faststart "$out.tmp.m4a"
  mv "$out.tmp.m4a" "$out"
  rm -f "$src"   # 変換済みなので元の音声データは削除（inbox / Googleドライブ「Download」とも）
  converted="$converted $id"
done

if [ "$AUDIO_HOST" = "releases" ] && [ -n "$converted" ]; then
  # 試験回ごとに Release を作り、音声をアセットとして登録（Pagesの容量を使わない）
  for id in $converted; do
    tag="ap-${id%%-*}"
    gh release view "$tag" >/dev/null 2>&1 || gh release create "$tag" --title "$tag" --notes "AP午後Podcast 音声 ${tag}"
    gh release upload "$tag" "$EP_DIR/${id}.m4a" --clobber
  done
  grep -qx "podcast/ap/episodes/" .gitignore 2>/dev/null || echo "podcast/ap/episodes/" >> .gitignore
fi

AUDIO_HOST="$AUDIO_HOST" python3 tools/build_feed.py

git add -A podcast/ap tools
[ -f .gitignore ] && git add .gitignore
if git diff --cached --quiet; then
  echo "変更なし"; exit 0
fi
git commit -q -m "AP podcast v2:${converted:- feed update}"
if [ "$DRY_RUN" = "1" ]; then
  echo "DRY_RUN=1 のため push しません"; exit 0
fi
git pull --rebase -q origin main
git push -q origin main

osascript -e 'display dialog "公開しました。
RSS: https://hidecars.github.io/podcast/ap/feed.xml" buttons {"OK"} default button 1' >/dev/null 2>&1 || true
