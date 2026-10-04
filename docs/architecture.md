# Architecture

## 概要

本アプリは、Electron + React + TypeScript で構築する。

Python CLI `subtitle.py` の引数・出力形式との互換性を維持し、Electron Main Process から subprocess として起動する。

## 全体構成

```text
Electron Main Process
  ├─ ファイル選択
  ├─ フォルダ選択
  ├─ Python CLI 実行
  └─ IPC

Preload
  └─ contextBridge による API 公開

Renderer
  ├─ React UI
  ├─ フォーム入力
  ├─ ログ表示
  └─ 実行状態管理

Python
  └─ subtitle.py
```

## 技術スタック

- Electron
- React
- TypeScript
- Vite
- Tailwind CSS
- Python
- faster-whisper

## Electron Main Process

Main Process は以下を担当する。

- 音声ファイル選択ダイアログ
- 出力先フォルダ選択ダイアログ
- Python CLI 実行
- stdout / stderr の監視
- Renderer へのログ通知

## Renderer Process

Renderer は以下を担当する。

- UI 表示
- フォーム入力
- 入力値のバリデーション
- 実行ボタン制御
- ログ表示
- 実行状態表示

Renderer から Node.js API を直接呼び出してはならない。

## Preload

`contextBridge` を使い、Renderer に必要最小限の API を公開する。

## セキュリティ設定

Electron の BrowserWindow は以下を守る。

```ts
webPreferences: {
  preload: preloadPath,
  nodeIntegration: false,
  contextIsolation: true,
}
```

## Python実行

Node.js の `child_process.spawn` を使用する。

`shell: true` は使用しない。

悪い例:

```ts
exec(`python subtitle.py --input ${inputPath}`)
```

良い例:

```ts
spawn("python", [
  "subtitle.py",
  "--input", inputPath,
  "--output", outputDir,
  "--title", title,
  "--model", model,
  "--format", format,
  "--language", language,
  ...(wordTimestamps ? ["--word-timestamps"] : []),
])
```

## パスの扱い

ファイルパスには以下が含まれる可能性がある。

- 空白
- 日本語
- 記号

そのため、コマンド文字列を組み立てず、必ず `spawn` の配列引数として渡す。

## IPC API 案

Renderer 側では以下の API を利用できる想定。

```ts
window.subtitle.selectAudioFile()
window.subtitle.selectOutputDirectory()
window.subtitle.generateSubtitle(options)
window.subtitle.onLog(callback)
```

## 型定義案

```ts
export type SubtitleModel =
  | "tiny"
  | "base"
  | "small"
  | "medium"
  | "large-v3";

export type SubtitleFormat =
  | "srt"
  | "vtt"
  | "txt";

export type SubtitleLanguage =
  | "ja"
  | "en";

export type GenerateSubtitleOptions = {
  input: string;
  output: string;
  title: string;
  model: SubtitleModel;
  format: SubtitleFormat;
  language: SubtitleLanguage;
  wordTimestamps: boolean;
};
```

## ログ通知

Python の stdout / stderr を受け取り、Renderer に送信する。

ログは時系列で表示できること。

## v1.0.6 の字幕生成

1. Rendererは「単語ごとの時刻を取得する」の状態を `wordTimestamps: boolean` としてPreload経由で送信する。初回・既存設定の項目欠損時はfalse。
2. Main Processはbooleanであることを検証し、trueならCLI引数に `--word-timestamps` を追加する。IPCの項目省略時はfalseとして扱い、文字列・数値・nullなどは拒否する。
3. Pythonは `args.word_timestamps` を `model.transcribe()` に渡す。CLI引数省略時もFalse。
4. SRT / VTTは共通の `_display_cues()` でsegmentの本文・時刻をそのままcueに変換して出力する。TXTは元の本文を直接出力する。

v1.0.5の独自分割、本文と単語時刻の対応付け、表示用句読点加工、フォールバック、それらだけが利用する関数・クラス・定数は削除する。`word_timestamps=True` でも、取得した語を独自の再分割には使わない。

追加依存はなく、既存のPyInstallerエントリーポイント・Electronのspawn構成を維持する。詳細は [字幕出力仕様](subtitle-segmentation.md) を参照する。

## 終了コード

Python プロセス終了時に終了コードを確認する。

- `0`: 成功
- `0` 以外: 失敗

失敗時は stderr を UI に表示する。
