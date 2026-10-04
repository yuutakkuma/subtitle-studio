# Subtitle Studio

Faster Whisper を利用して音声ファイルから字幕ファイルを生成する CLI ツールです。

現在のバージョン: **v1.0.5**

## 機能

- 音声ファイルから字幕生成
- 出力ファイル名指定
- 出力ディレクトリ指定
- モデル（認識精度）指定
- 出力フォーマット指定
- 言語指定
- SRT / VTT / TXT 出力対応
- SRT / VTT 字幕を句読点・発話の間・日本語のまとまりに沿って分割（固定文字数制限なし）
- 単語の開始・終了時刻に基づく字幕表示

---

## 動作環境

- Python 3.10+
- ffmpeg
- faster-whisper

---

## セットアップ

### 仮想環境作成

```bash
python3 -m venv .venv
```

### 仮想環境有効化

```bash
source .venv/bin/activate
```

### 依存関係インストール

```bash
pip install faster-whisper
```

デスクトップアプリをビルドする場合は PyInstaller も必要です。

```bash
pip install pyinstaller
```

---

## 実行方法

```bash
python3 subtitle.py \
  --input "/path/to/audio.wav" \
  --output "/path/to/output" \
  --title "subtitle" \
  --model "large-v3" \
  --format "srt" \
  --language "ja"
```

---

## オプション

### --input

入力音声ファイルパス

例

```bash
--input "./voice.wav"
```

対応フォーマットは ffmpeg がサポートする音声形式に準拠します。

例

- wav
- mp3
- m4a
- aac
- flac

---

### --output

出力ディレクトリ

例

```bash
--output "./subtitles"
```

存在しない場合は自動作成されます。

---

### --title

出力ファイル名

例

```bash
--title "episode001"
```

生成結果

```text
episode001.srt
```

---

### --model

認識モデルを指定します。

例

```bash
--model "large-v3"
```

利用可能な値

| モデル | 精度 | 速度 |
|----------|----------|----------|
| tiny | 低 | 最速 |
| base | 普通 | 速い |
| small | 良 | 実用的 |
| medium | 高 | やや遅い |
| large-v3 | 最高 | 遅い |

推奨

```text
large-v3
```

---

### --format

出力フォーマット

例

```bash
--format "srt"
```

利用可能な値

| フォーマット | 用途 |
|-------------|------|
| srt | DaVinci Resolve |
| vtt | YouTube |
| txt | 文字起こし確認 |

---

### --language

認識言語

例

```bash
--language "ja"
```

主な指定例

| 言語 | コード |
|--------|--------|
| 日本語 | ja |
| 英語 | en |
| 中国語 | zh |
| 韓国語 | ko |

---

## 出力例

SRT / VTT は共通の処理で、発話に合わせて字幕を生成します。

- 固定文字数による強制分割は行いません。20文字を超えても文字数だけでは分割しません。
- `word_timestamps=True` で取得した `segment.words` と、句読点を含む原文を対応付けます。
- 文末を優先し、読点は発話の間や節の発話時間と組み合わせて判断します。
- 「について」の途中や助詞・助動詞の前などを保護し、短い断片は隣接字幕との区切りを調整します。短い返答・文末・長い無音での区切りは維持します。
- 各字幕は最初の語の開始時刻から最後の語の終了時刻まで表示します。文字数比による時刻の補間は行いません。
- 単語時刻の欠損・不正、原文との不一致は、理由をログに残し、そのsegmentの原文と元の時刻を使った分割なしの字幕へフォールバックします。
- 表示用の句読点除去と空白整理は分割後に行います。`1.5万円`、`10:30`、`1,000円` などの表記を保持します。
- TXTは従来どおり `segment.text` をそのまま出力し、各segmentの末尾に改行を追加します。

閾値は `subtitle.py` の `SegmentationConfig` に集約しています。既定値は通常の間 **0.5秒**、読点の間 **0.25秒**、長い無音 **1.0秒**、読点で区切る節の発話時間 **3.0秒**、短い断片の発話時間 **0.8秒未満**です。

追加依存はありません。日本語の境界判定は保守的な規則であり、形態素解析辞書は使用していません。未知語や曖昧なつながりでは分割を控えるため、長い字幕が残る場合があります。詳細・例外・調整方法は [字幕分割仕様](docs/subtitle-segmentation.md) を参照してください。

### SRT

```srt
1
00:00:00,000 --> 00:00:02,500
拝啓

2
00:00:02,500 --> 00:00:05,800
YouTubeの皆様
```

### VTT

```vtt
WEBVTT

00:00:00.000 --> 00:00:02.500
拝啓
```

### TXT

```text
拝啓
如何お過ごしでしょうか
```

---

## 実行例

---

## デスクトップアプリ

Electron + React + TypeScript + Vite + Tailwind CSS による GUI から、
既存の `subtitle.py` を実行できます。

### 依存関係インストール

```bash
npm install
```

Python 側の依存関係も別途必要です。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install faster-whisper
```

### 開発起動

```bash
npm run dev
```

開発起動では Vite dev server と Electron を起動します。
Electron Main Process から `subtitle.py` を `child_process.spawn` で実行します。

Python コマンドを明示したい場合は `PYTHON_PATH` を指定できます。

```bash
PYTHON_PATH=.venv/bin/python npm run dev
```

現在の開発設定では `.venv/bin/python` が存在する場合、自動的にそれを優先して使います。

### ビルド

```bash
npm run build
```

Renderer は `dist/`、Electron Main / Preload は `dist-electron/` に出力されます。

### デスクトップアプリのビルド

Python CLI を PyInstaller で単体実行ファイル化し、Electron アプリに同梱します。

```bash
npm run build:app
```

生成物は Apple Silicon Mac では `release/mac-arm64/Subtitle Studio.app` に出力されます。
同梱された `subtitle-cli` を Electron Main Process から `spawn` で実行するため、
利用者側の Python 環境に `faster-whisper` をインストールする必要はありません。

v1.0.5 の字幕分割は Python 標準ライブラリのみを追加使用します。新しい辞書・外部API・PyInstallerの追加収集設定は不要です。

### テスト

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m py_compile subtitle.py scripts/subtitle_cli_entry.py
npm run typecheck
npm run build
```

Pythonテストは合成した認識結果と単語時刻を使用し、音声・モデルのダウンロードは不要です。実音声での認識精度・同期精度や処理速度を実証するテストではありません。

### DaVinci Resolve用字幕生成

```bash
python subtitle.py \
  --input "./voice.wav" \
  --output "./output" \
  --title "haikei001" \
  --model "large-v3" \
  --format "srt" \
  --language "ja"
```

出力

```text
output/
└── haikei001.srt
```

---

## 仮想環境の終了

```bash
deactivate
```

---
