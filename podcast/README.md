# 🎧 Podcast 自動生成＆GitHubアップロードスクリプト

## 📝 概要

このリポジトリでは、音声学習用に `wav` ファイルを `m4a` に変換し、Podcast用のRSSフィードを自動生成・GitHub Pagesに公開する **Mac用Automatorアプリ** を提供します。

NotebookLMなどで生成した `.wav` 音声を、自動で次の処理を行います：

1. `.wav` → `.m4a` に変換（元ファイルは削除）
2. RSSファイル（カテゴリ別）を自動生成
3. GitHub Pages に push
4. 完了通知とRSS URLをダイアログ表示

---

## 📁 フォルダ構成

iCloudフォルダ上の `hidecars.github.io/podcast/` に、以下のような学習カテゴリ構成で保存してください：

hidecars.github.io/
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

- `infosys_podcast.xml` や `NotebookLM_podcast.xml` などのRSSファイルが生成され、`podcast/` フォルダに保存されます。
- すべての `.m4a` 音声ファイルは、親フォルダ配下のすべてのサブカテゴリを対象に一括収録されます。

---

## ⚙️ 必要な環境

- macOS（Automator使用）
- `ffmpeg`：Homebrewでインストール

```bash
brew install ffmpeg

	•	GitHubリポジトリ：hidecars.github.io（GitHub Pages有効）
	•	iCloud連携：以下のパスに同期

~/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io/



⸻

🚀 Automatorアプリの作成手順
	1.	Automator を開く →「アプリケーション」を選択
	2.	アクションに「シェルスクリプトを実行」を追加
	3.	次のスクリプトを貼り付けて保存（例：PodcastUpdater.app）

⸻

🧩 スクリプト（最終版）

#!/bin/bash

# 環境設定
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
BASE_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io/podcast"
GITHUB_URL="https://hidecars.github.io/podcast"

TMPFILE=$(mktemp)

# URLエンコード関数（スラッシュ除外）
urlencode_path() {
  local IFS='/'
  local segments=($1)
  local encoded_path=""
  for segment in "${segments[@]}"; do
    encoded_segment=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$segment'''))")
    encoded_path+="$encoded_segment/"
  done
  echo "${encoded_path%/}"
}

# 1. wav → m4a 変換、削除
find "$BASE_DIR" -type f -name "*.wav" | while read -r wavfile; do
    m4afile="${wavfile%.wav}.m4a"
    ffmpeg -y -i "$wavfile" -vn -acodec aac "$m4afile"
    rm -f "$wavfile"
done

# 2. RSS生成（親フォルダ単位）
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
            REL_PATH="${audio#"$BASE_DIR/"}"
            ENCODED_PATH=$(urlencode_path "$REL_PATH")
            FILE_URL="${GITHUB_URL}/${ENCODED_PATH}"
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

# 3. GitHubアップロード
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io" || exit 1
git add -A
git commit -m "Auto update podcast and RSS" 2>/dev/null
git pull --rebase > /dev/null 2>&1
git push origin main > /dev/null 2>&1

# 4. 完了通知表示
echo "✅ Podcast処理 完了！\n\nRSSフィード一覧：" > "$TMPFILE"
for parent in "$BASE_DIR"/*; do
    [ -d "$parent" ] && PARENT_NAME=$(basename "$parent") && echo "${GITHUB_URL}/${PARENT_NAME}_podcast.xml" >> "$TMPFILE"
done

osascript <<EOF
display dialog "$(cat "$TMPFILE")" buttons {"OK"} default button "OK" with title "Podcast更新スクリプト" with icon note
EOF

rm -f "$TMPFILE"
exit 0


⸻

🌐 出力されるRSSフィードURLの例
	•	https://hidecars.github.io/podcast/infosys_podcast.xml
	•	https://hidecars.github.io/podcast/NotebookLM_podcast.xml

これらのURLをiPhoneのPodcastアプリに登録することで、音声学習コンテンツを隙間時間に再生可能です。

⸻

📌 注意点
	•	m4a ファイルやフォルダ名に スペース、日本語、記号 が含まれていても自動でURLエンコードされます。
	•	git の認証設定（SSHやアクセストークン）は事前に行っておいてください。
	•	Automatorアプリは 会社と自宅のMacの両方で動作可能です（iCloud共有で同期されている場合）。

⸻

📥 今後の拡張予定
	•	Podcast_URL.txt を出力し、iPhoneとAirDropで共有
	•	タグやキーワードによるフィルタRSS
	•	mp3変換対応やApple Podcast準拠メタデータ付与

⸻

👨‍💻 作成者
	•	GitHub: @hidecars
	•	作成日: 2025年6月24日（火）