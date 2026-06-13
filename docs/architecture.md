# Architecture

## 概要

本アプリは、Electron + React + TypeScript で構築する。

既存の Python CLI `subtitle.py` を変更せず、Electron Main Process から subprocess として起動する。

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
};
```

## ログ通知

Python の stdout / stderr を受け取り、Renderer に送信する。

ログは時系列で表示できること。

## 終了コード

Python プロセス終了時に終了コードを確認する。

- `0`: 成功
- `0` 以外: 失敗

失敗時は stderr を UI に表示する。