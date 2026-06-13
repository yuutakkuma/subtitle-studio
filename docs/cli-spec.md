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

## 字幕整形

`srt` / `vtt` 出力では、動画上で字幕が横にはみ出しにくいように自動整形する。

- 1行あたりの目安: 全角18文字
- 不自然な分割になる場合は、自然な切れ目を優先して全角24文字相当まで許容する
- 最大行数: 2行
- 長すぎる場合: cue 自体を複数に分割する
- 句読点、文字種、断片の長さから自然な切れ目を推定して改行する
- 文字種と断片の長さを見て、短い語尾だけが次行に残る分割を抑制する
- cue や行末の不要な読点 `、` は表示から取り除く
- 3行に分かれる場合は、最後の短い行が単独 cue にならないように配置する
- `よね。` など短すぎる cue は、可能な場合に前後の cue へ吸収する
- 近接する短い cue は、2行以内・最大6秒以内に収まる場合に結合する
- cue の終了時刻には、次の字幕に重ならない範囲で最大0.45秒の読了マージンを追加する

word timestamp が利用できる場合は、分割後 cue の開始・終了時刻を単語単位の時刻から決定する。
word timestamp が利用できない場合のみ、元の segment の開始・終了時刻を文字量の比率で按分する。

`txt` 出力は文字起こし確認用として、segment ごとのテキストをそのまま出力する。
