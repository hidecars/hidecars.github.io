# 🎙 Podcast 自動処理システム - 技術ドキュメント

## ✅ 概要

このシステムは、以下の処理を1クリックで実行する **Mac用Automatorアプリ**を作成するためのドキュメントです。

- `.wav` → `.m4a` に変換（ffmpeg使用）
- 親カテゴリごとのPodcast用RSSファイルを生成
- GitHub Pagesへ自動Push
- RSS URLをダイアログで通知
- 家庭・職場両方のMacで共通運用

---

## 🗂 フォルダ構成

/Library/Mobile Documents/comapple~CloudDocs/hidecars.github.io/
└── podcast/
├── infosys/
│   ├── infosec/
│   ├── infosys/
│   ├── network/
│   ├── programming/
│   ├── projmng/
│   ├── servicemng/
│   └── sysaudit/
└── NotebookLM/

各親フォルダごとにRSSファイルを生成します（例：`infosys_podcast.xml`, `NotebookLM_podcast.xml`）。

---

## 🔧 必要なツール

- Homebrew
- ffmpeg（インストール例）:
  ```bash
  brew install ffmpeg

	•	Git（GitHub設定済）
	•	.nojekyll ファイル（GitHub Pages用）

⸻

📦 処理仕様

ステップ	処理内容
①	.wav ファイルを .m4a に変換し、元ファイルを削除
②	親カテゴリごとにRSSファイル（XML）を生成
③	GitHub Pagesへ git add → commit → pull --rebase → push
④	完了通知をAppleScriptでダイアログ表示
⑤	処理対象の親フォルダは可変（追加・削除・改名に対応）


⸻

🤖 Automatorアプリの作成手順
	1.	Macの「Automator」アプリを開く
	2.	「新規書類」→「アプリケーション」を選択
	3.	「シェルスクリプトを実行」アクションを追加
	4.	/bin/bash を指定
	5.	下記のスクリプトをコピーして貼り付け
	6.	名前を付けて保存（例：PodcastUpdater.app）

⸻

📜 完全版シェルスクリプト（最新版）

#!/bin/bash

# 環境設定
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"  # ffmpegなどを使えるように
BASE_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io/podcast"
GITHUB_URL="https://hidecars.github.io/podcast"

# 一時ファイル
TMPFILE=$(mktemp)

# 1. wav → m4a 変換、wav削除
find "$BASE_DIR" -type f -name "*.wav" | while read -r wavfile; do
    m4afile="${wavfile%.wav}.m4a"
    ffmpeg -y -i "$wavfile" -vn -acodec aac "$m4afile"
    rm -f "$wavfile"
done

# 2. RSSファイル生成（親カテゴリ単位）
for parent in "$BASE_DIR"/*; do
    [ -d "$parent" ] || continue
    PARENT_NAME=$(basename "$parent")
    RSS_FILE="$BASE_DIR/${PARENT_NAME}_podcast.xml"

    {
        echo '<?xml version="1.0" encoding="UTF-8"?>'
        echo '<rss version="2.0"><channel>'
        echo "<title>${PARENT_NAME} Podcast</title>"
        echo "<link>${GITHUB_URL}/${PARENT_NAME}_podcast.xml</link>"
        echo "<description>Auto-generated podcast RSS</description>"

        find "$parent" -type f -name "*.m4a" | while read -r audio; do
            FILE_NAME=$(basename "$audio")
            FILE_URL="${GITHUB_URL}/${PARENT_NAME}/$(basename "$(dirname "$audio")")/${FILE_NAME}"
            PUB_DATE=$(date -r "$audio" "+%a, %d %b %Y %H:%M:%S %z")
            echo "<item>"
            echo "<title>${FILE_NAME}</title>"
            echo "<enclosure url=\"$FILE_URL\" type=\"audio/mp4\" />"
            echo "<pubDate>$PUB_DATE</pubDate>"
            echo "<guid>${FILE_URL}</guid>"
            echo "</item>"
        done

        echo "</channel></rss>"
    } > "$RSS_FILE"
done

# 3. GitHubへpush
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io" || exit 1
git add -A
git commit -m "Auto update podcast and RSS" 2>/dev/null
git pull --rebase > /dev/null 2>&1
git push origin main > /dev/null 2>&1

# 4. 完了通知のダイアログ用メッセージ生成
echo "✅ Podcast処理 完了！\n\nRSSフィード一覧：" > "$TMPFILE"
for parent in "$BASE_DIR"/*; do
    [ -d "$parent" ] && PARENT_NAME=$(basename "$parent") && echo "${GITHUB_URL}/${PARENT_NAME}_podcast.xml" >> "$TMPFILE"
done

# 5. ダイアログ表示（AppleScript経由）
osascript <<EOF
display dialog "$(cat "$TMPFILE")" buttons {"OK"} default button "OK" with title "Podcast更新スクリプト" with icon note
EOF

# 6. 後処理
rm -f "$TMPFILE"
exit 0


⸻

📬 使用例と成果物
	•	infosys_podcast.xml や NotebookLM_podcast.xml が /podcast/ に作成され、
	•	各RSSファイルは以下のようなURLでアクセス可能：
	•	https://hidecars.github.io/podcast/infosys_podcast.xml
	•	https://hidecars.github.io/podcast/NotebookLM_podcast.xml

⸻

🧩 今後の拡張アイデア
	•	RSSの <itunes:...> 拡張対応
	•	タグ・カテゴリの自動抽出
	•	Slackやメールで完了通知

⸻

🧑‍💻 作成者メモ
	•	macOS Monterey以降対応確認済
	•	ffmpeg のPATHは環境により調整可能
	•	GitHub Pages のCNAME・カスタムドメイン対応も検討可

