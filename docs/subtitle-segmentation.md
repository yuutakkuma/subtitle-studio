# 字幕出力仕様 — v1.0.6

## 出力方針

`_display_cues()` は認識結果の1 segmentを1 cueへ変換する。本文は `segment.text`、時刻は `segment.start` / `segment.end` をそのまま保持する。SRT / VTTは同じ変換処理を利用する。

- 固定文字数・句読点・発話の間による追加分割を行わない。
- 隣接segmentを結合しない。
- 句読点・空白・改行を削除・整理しない。
- 認識本文の要約・補完・フィラー除去を行わない。
- 文字数比例の時刻配分や単語時刻による独自補間を行わない。

v1.0.5の独自分割ルール・閾値・単語時刻の対応付け・検証・フォールバックは廃止した。それらのためだけに使われていた関数・クラス・定数・importも削除する。

## 単語タイムスタンプの設定

| 層 | 設定・動作 |
|---|---|
| GUI | 「単語ごとの時刻を取得する」。初回はオフ |
| 保存設定 | `wordTimestamps` をbooleanで保存。項目欠損時はfalse |
| Preload / IPC | `GenerateSubtitleOptions.wordTimestamps` を渡す |
| Electron Main | trueのときだけ `--word-timestamps` を追加する |
| Python CLI | `--word-timestamps` 指定時はTrue、省略時はFalse |
| faster-whisper | `model.transcribe(..., word_timestamps=args.word_timestamps)` |

IPCではboolean以外の値を拒否する。旧形式のリクエストで項目が省略されていればfalseとして扱う。保存済み設定についてはbooleanのtrueだけをオンとして復元する。

この設定は全出力形式で認識モデルに渡す。Trueで取得した `segment.words` も、出力側の再分割・時刻変更には使わない。設定の違いがモデルの返す結果に及ぼす影響と、出力側の独自加工は別であり、出力は常に返されたsegmentを使う。

## ファイル形式

- SRT: 1からの連番、`HH:MM:SS,mmm`、元の本文、空行。
- VTT: `WEBVTT` ヘッダー、`HH:MM:SS.mmm`、元の本文、空行。
- TXT: 各 `segment.text` をそのまま書き、その末尾に改行を追加する。

SRT / VTTの時刻表記はミリ秒へ丸める。元のsegment時刻自体に対する独自の検証・補正はしない。本文に空行などが含まれる場合も加工しないため、取り込み先の形式制約に応じて確認が必要になる。

## 互換性・同梱

既存のCLI引数は維持し、値を伴わない `--word-timestamps` フラグを追加する。Falseにする場合はフラグを省略し、`--word-timestamps false` とは指定しない。

Renderer → Preload → Electron Main Process → Python CLIの呼び出し構成、`spawn` の配列引数、認識モデル・CPU / int8設定は維持する。追加依存はなく、既存のPyInstallerエントリーポイントとビルド設定で同梱する。

## 検証

- Python: segment本文・時刻の保持、長文の非分割、SRT / VTT / TXTの形式、引数省略時のFalse、フラグ指定時のTrue、全出力形式でのモデルへの引き渡し。
- デスクトップ: 保存設定に応じたチェックボックスの初期描画、Preloadによるbooleanの転送、IPCの検証、開発用／同梱CLIへの引数。

合成した認識結果・モックを使うテストであり、実音声の認識精度・同期精度・処理速度を実証するものではない。
