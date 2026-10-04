# CLI Specification

## 概要

`subtitle.py` は音声ファイルを入力として、faster-whisper により字幕ファイルを生成する CLI ツールである。

デスクトップアプリは、この CLI を subprocess として実行する。

## 実行例

```bash
python subtitle.py \
  --input "/path/to/audio.wav" \
  --output "/path/to/output" \
  --title "haikei001" \
  --model "large-v3" \
  --format "srt" \
  --language "ja"
```

## オプション

| オプション | 必須 | 説明 |
|---|---:|---|
| `--input` | Yes | 入力音声ファイルパス |
| `--output` | Yes | 出力先ディレクトリ |
| `--title` | Yes | 出力ファイル名。拡張子は含めない |
| `--model` | No | Whisperモデル |
| `--format` | No | 出力形式 |
| `--language` | No | 認識言語 |

## --input

入力音声ファイルパスを指定する。

例:

```bash
--input "./voice.wav"
```

対応形式は ffmpeg が読み込める音声ファイルに準拠する。

想定例:

- wav
- mp3
- m4a
- aac
- flac

## --output

出力先ディレクトリを指定する。

例:

```bash
--output "./output"
```

存在しない場合は `subtitle.py` 側で自動作成される。

## --title

出力ファイル名を指定する。

拡張子は含めない。

例:

```bash
--title "haikei001"
```

生成例:

```text
haikei001.srt
```

## --model

Whisperモデルを指定する。

利用可能な値:

- `tiny`
- `base`
- `small`
- `medium`
- `large-v3`

デフォルト:

```text
small
```

目安:

| モデル | 精度 | 速度 |
|---|---|---|
| tiny | 低 | 最速 |
| base | 普通 | 速い |
| small | 良 | 実用的 |
| medium | 高 | やや遅い |
| large-v3 | 最高 | 遅い |

## --format

出力形式を指定する。

利用可能な値:

- `srt`
- `vtt`
- `txt`

デフォルト:

```text
srt
```

用途:

| 形式 | 用途 |
|---|---|
| srt | DaVinci Resolve 用 |
| vtt | YouTube 用 |
| txt | 文字起こし確認用 |

## --language

認識言語を指定する。

デフォルト:

```text
ja
```

主な指定例:

| 言語 | コード |
|---|---|
| 日本語 | ja |
| 英語 | en |
| 中国語 | zh |
| 韓国語 | ko |

## 出力

指定された出力ディレクトリに以下の形式でファイルを生成する。

```text
{title}.{format}
```

例:

```text
output/
└── haikei001.srt
```

## 字幕出力

v1.0.5 の `srt` / `vtt` は共通の字幕分割・時刻生成処理を使う。固定文字数による分割・文字数比例の時刻配分は行わない。

- `model.transcribe(..., word_timestamps=True)` を全出力形式で使用する。モデル・device・compute_type・CLI引数は変更しない。
- 分割前の原文を `segment.words` に対応付け、句読点・語間の無音・日本語の表現や語尾を組み合わせて境界を選ぶ。
- 時刻は字幕内の最初の語の `start` と最後の語の `end` を使う。語の内部に分割点を推測したり、時刻を補間したりしない。
- 欠損・不正な単語時刻や本文不一致は、そのsegmentを原文・元のsegment時刻のまま1 cueにする。`Subtitle fallback: segment ...: 理由` をstdoutへ出力する。
- 分割後に表示用句読点を除去し、改行・連続空白を整理する。小数点・時刻のコロン・数値の桁区切り・演算子などは保持する。
- SRTは連番とカンマ区切りのミリ秒、VTTは `WEBVTT` ヘッダーとピリオド区切りのミリ秒を出力する。
- 元のsegment時刻自体が不正・重複してフォールバック不能な場合はエラーとし、出力ファイルを開く前に停止する。

`txt` は各segmentのテキストを加工せず、その末尾に改行を追加する。認識結果に含まれる句読点・空白・改行は保持する。

分割ルール、閾値、フォールバックの条件と制約は [字幕分割仕様](subtitle-segmentation.md) を参照する。
