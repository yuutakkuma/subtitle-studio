# AGENT.md

このリポジトリでは、既存の Python CLI `subtitle.py` を利用して、音声ファイルから字幕ファイルを生成するデスクトップアプリを開発する。

## 最重要方針

- 既存の `subtitle.py` は原則として壊さない。
- Python 側の CLI 仕様は維持する。
- デスクトップアプリは Python CLI を subprocess として実行する。
- Renderer と Main Process を分離する。
- Electron の `nodeIntegration` は無効化する。
- Renderer から Node.js API を直接呼ばない。
- IPC は `contextBridge` 経由で公開する。
- 実装前に `docs/` 配下の仕様を確認する。

## 参照すべき仕様書

- `docs/desktop-app-requirements.md`
- `docs/cli-spec.md`
- `docs/architecture.md`
- `docs/ui-spec.md`

## 技術スタック

- Electron
- React
- TypeScript
- Vite
- Tailwind CSS
- Python
- faster-whisper

## 実装ルール

- 型安全を優先する。
- 例外処理を省略しない。
- 標準出力・標準エラーを UI に表示できるようにする。
- ファイルパスは空白や日本語を含んでも動作するように扱う。
- shell 経由ではなく `spawn` を使用する。
- ユーザー入力を shell コマンド文字列に直接連結しない。
- 既存仕様を変更する場合は README と docs を更新する。

## 完了条件

- GUI から音声ファイルを選択できる。
- 出力先フォルダを選択できる。
- 出力ファイル名を指定できる。
- モデルを選択できる。
- 出力形式を選択できる。
- 言語を選択できる。
- 字幕生成を実行できる。
- 実行ログが UI に表示される。
- 成功・失敗が UI で分かる。
- README に起動方法とビルド方法が記載されている。