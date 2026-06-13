# Desktop App Requirements

## 目的

既存 CLI `subtitle.py` を GUI から実行し、音声ファイルから字幕ファイルを生成できるデスクトップアプリを開発する。

## 必須機能

### 入力音声ファイル選択

- ファイル選択ダイアログを提供する。
- ドラッグ&ドロップに対応する。
- 選択されたファイルパスを UI に表示する。

対象例:

- wav
- mp3
- m4a
- aac
- flac

### 出力先フォルダ選択

- フォルダ選択ダイアログを提供する。
- 選択されたフォルダパスを UI に表示する。

### 出力ファイル名入力

- 拡張子なしのファイル名を入力する。
- 空の場合は実行できない。
- 初期値は空文字または `subtitle` とする。

例:

```text
haikei001
```

### モデル選択

選択肢:

- tiny
- base
- small
- medium
- large-v3

初期値:

```text
large-v3
```

### 出力形式選択

選択肢:

- srt
- vtt
- txt

初期値:

```text
srt
```

### 言語選択

選択肢:

- ja
- en

初期値:

```text
ja
```

### 字幕生成

GUI から `subtitle.py` を実行する。

実行例:

```bash
python subtitle.py \
  --input "/path/to/audio.wav" \
  --output "/path/to/output" \
  --title "haikei001" \
  --model "large-v3" \
  --format "srt" \
  --language "ja"
```

### ログ表示

以下をリアルタイム表示する。

- stdout
- stderr
- 終了コード
- エラー内容

表示例:

```text
Loading model...
Transcribing audio...
Detected language: ja
Generated: /path/to/output/haikei001.srt
```

### 完了表示

成功時:

```text
Subtitle generated successfully.
```

失敗時:

```text
Subtitle generation failed.
```

失敗時は stderr または例外メッセージを表示する。

### 設定保存

次回起動時に以下を復元する。

- model
- format
- language
- output directory

保存先は初期実装では `localStorage` でよい。

## バリデーション

以下の場合は字幕生成ボタンを disabled にする。

- 音声ファイルが未選択
- 出力先フォルダが未選択
- タイトルが未入力
- モデルが未選択
- フォーマットが未選択
- 言語が未選択

## 非対象

初期実装では以下は対象外とする。

- 字幕の自動整形
- フィラー除去
- 複数ファイル一括処理
- モデル管理画面
- Hugging Face Token 設定画面
- Python 仮想環境の自動作成
- faster-whisper の自動インストール