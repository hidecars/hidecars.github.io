# 🎙 hidecars.github.io Podcast 自動化スクリプト

このリポジトリは、iCloudフォルダに保存された `.wav` 音声ファイルを自動で `.m4a` に変換し、ポッドキャスト用 RSS フィードを生成し、GitHub Pages 経由で公開するための **Automatorアプリ連携スクリプト** を提供します。

## 📁 フォルダ構成

iCloudフォルダ：`~/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io/podcast/`

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

- 親フォルダ単位でRSSファイルを生成（例：`infosys_podcast.xml`, `NotebookLM_podcast.xml`）
- 各 `.wav` → `.m4a` へ変換後、自動削除
- RSSの `<pubDate>` はファイル名順で並べるよう疑似的な日時を生成

---

## 🔧 動作仕様

| 機能                           | 内容                                                                 |
|------------------------------|----------------------------------------------------------------------|
| `.wav` → `.m4a` 変換        | `ffmpeg` により自動変換。同フォルダ内に保存され、元の`.wav`は削除   |
| RSS生成                      | 親フォルダごとに1つのRSS（全サブフォルダの`.m4a`を収録）              |
| `<pubDate>`制御              | ファイル名順に並ぶよう数秒ずつずらした疑似日付を生成                 |
| GitHubアップロード           | 自動 `git add → commit → pull → push` により更新                      |
| 完了通知                     | AppleScript によりダイアログでRSSのURLを表示                          |
| iPhone連携用テキスト         | `Podcast_URL.txt` にRSS一覧を保存し、iCloud経由でiPhoneと共有可能   |

---

## 🧪 依存環境

- macOS（Automator 使用）
- `ffmpeg`（Homebrew で `brew install ffmpeg`）
- Git（GitHub認証済）
- iCloud同期環境

---

## 🛠 導入手順

### 1. 前提準備

```bash
brew install ffmpeg

GitHubリポジトリをクローンし、iCloudフォルダに以下のように設置：

~/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io/

2. .nojekyll ファイルをルートに設置

touch ~/Library/Mobile\ Documents/com~apple~CloudDocs/hidecars.github.io/.nojekyll

3. Automatorアプリ作成手順
	1.	Automatorを開く → 「アプリケーション」を選択
	2.	「シェルスクリプトを実行」を追加
	3.	スクリプトエリアに完全版スクリプトを貼り付け
	4.	ffmpeg のパス /opt/homebrew/bin を確認・修正（必要に応じて）
	5.	アプリ名をつけて保存（例：Podcast更新.app）

⸻

📤 RSS URL 確認方法

完了後、自動で表示されるダイアログまたは以下のファイルで確認できます：

~/Library/Mobile Documents/com~apple~CloudDocs/hidecars.github.io/podcast/Podcast_URL.txt


⸻

📱 iPhoneと連携するには
	1.	iCloud Driveから Podcast_URL.txt を開く
	2.	対象のRSS URLをコピー
	3.	SafariでURLを開き、RSSフィードを登録

⸻

✅ 例：生成されるRSSの一部

<item>
  <title>01.共通フレーム.m4a</title>
  <enclosure url="https://hidecars.github.io/podcast/infosys/infosec/01.%E5%85%B1%E9%80%9A%E3%83%95%E3%83%AC%E3%83%BC%E3%83%A0.m4a" type="audio/mp4" />
  <pubDate>Sun, 01 Jun 2025 00:00:01 +0900</pubDate>
  <guid>https://hidecars.github.io/podcast/infosys/infosec/01.%E5%85%B1%E9%80%9A%E3%83%95%E3%83%AC%E3%83%BC%E3%83%A0.m4a</guid>
</item>


⸻

👨‍💻 メンテナンス用コマンド例

cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/hidecars.github.io/
git status
git pull origin main


⸻

🧾 ライセンス・注意事項
	•	本スクリプトは社内利用・教育目的で自由に改変可能です
	•	公開用には音声データの権利にご注意ください
