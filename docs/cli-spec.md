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
| `--word-timestamps` | No | 単語時刻を取得するフラグ。省略時はFalse |

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

## --word-timestamps

値を伴わない有効化フラグ。指定時は `True`、省略時は `False` を `model.transcribe()` の `word_timestamps` に渡す。`--word-timestamps false` という指定は受け付けない。オフにする場合はフラグを省略する。

GUIの `wordTimestamps` がtrueのときにElectronがこのフラグを追加する。SRT / VTT / TXTのすべてで適用する。

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

v1.0.6 の `srt` / `vtt` は `_display_cues()` を共通に使い、1 segmentを1 cueへ変換する。

- 本文は `segment.text`、時刻は `segment.start` / `segment.end` を保持する。
- 独自分割・結合・文字数比例の時刻配分・句読点や空白の加工は行わない。
- `word_timestamps` は認識時の設定であり、`segment.words` による出力側の再分割は行わない。単語時刻の検証・フォールバック処理もない。
- SRTは連番とカンマ区切りのミリ秒、VTTは `WEBVTT` ヘッダーとピリオド区切りのミリ秒を出力する。
- 元segmentの時刻を独自補正・検証する処理は設けない。

`txt` は各segmentのテキストを加工せず、その末尾に改行を追加する。

詳細は [字幕出力仕様](subtitle-segmentation.md) を参照する。
