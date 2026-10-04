#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SubtitleCue:
    start: float
    end: float
    # Preserve the recognition text and segment timing without post-processing.
    text: str


def log(message: str):
    print(message, flush=True)


def _format_time(seconds: float, separator: str) -> str:
    # Round once so fractional seconds cannot lose a millisecond to float error.
    total_ms = round(seconds * 1000)
    total_seconds, ms = divmod(total_ms, 1000)
    minutes, s = divmod(total_seconds, 60)
    h, m = divmod(minutes, 60)
    return f"{h:02}:{m:02}:{s:02}{separator}{ms:03}"


def format_srt_time(seconds: float) -> str:
    return _format_time(seconds, ",")


def format_vtt_time(seconds: float) -> str:
    return _format_time(seconds, ".")


def _display_cues(segments):
    return [
        SubtitleCue(
            start=segment.start,
            end=segment.end,
            text=segment.text,
        )
        for segment in segments
    ]


def write_srt(output_file: Path, segments):
    cues = _display_cues(segments)
    with open(output_file, "w", encoding="utf-8") as f:
        for index, cue in enumerate(cues, start=1):
            f.write(f"{index}\n")
            f.write(f"{format_srt_time(cue.start)} --> {format_srt_time(cue.end)}\n")
            f.write(cue.text)
            f.write("\n\n")


def write_vtt(output_file: Path, segments):
    cues = _display_cues(segments)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")
        for cue in cues:
            f.write(f"{format_vtt_time(cue.start)} --> {format_vtt_time(cue.end)}\n")
            f.write(cue.text)
            f.write("\n\n")


def write_txt(output_file: Path, segments):
    with open(output_file, "w", encoding="utf-8") as f:
        for segment in segments:
            f.write(segment.text)
            f.write("\n")


def create_parser():
    parser = argparse.ArgumentParser(
        description="Generate subtitles from audio using Faster Whisper"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input audio file path"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output directory path"
    )

    parser.add_argument(
        "--title",
        required=True,
        help="Output file name without extension"
    )

    parser.add_argument(
        "--model",
        default="small",
        choices=[
            "tiny",
            "base",
            "small",
            "medium",
            "large-v3"
        ],
        help="Whisper model size"
    )

    parser.add_argument(
        "--format",
        default="srt",
        choices=[
            "srt",
            "vtt",
            "txt"
        ],
        help="Output format"
    )

    parser.add_argument(
        "--language",
        default="ja",
        help="Language code (ja, en, etc.)"
    )

    parser.add_argument(
        "--word-timestamps",
        action="store_true",
        default=False,
        help="Extract word-level timestamps (default: disabled)"
    )

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    input_file = Path(args.input)

    if not input_file.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_file}"
        )

    output_dir = Path(args.output)
    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        output_dir /
        f"{args.title}.{args.format}"
    )

    log("Loading model...")

    from faster_whisper import WhisperModel

    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8"
    )

    log("Transcribing audio...")

    segments, info = model.transcribe(
        str(input_file),
        language=args.language,
        word_timestamps=args.word_timestamps,
    )

    segments = list(segments)

    log(
        f"Detected language: {info.language}"
    )

    if args.format == "srt":
        log("Formatting subtitles...")
        write_srt(output_file, segments)

    elif args.format == "vtt":
        log("Formatting subtitles...")
        write_vtt(output_file, segments)

    elif args.format == "txt":
        write_txt(output_file, segments)

    log(
        f"Generated: {output_file}"
    )


if __name__ == "__main__":
    main()
