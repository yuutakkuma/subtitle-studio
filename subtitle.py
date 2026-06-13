#!/usr/bin/env python3

import argparse
from pathlib import Path

from faster_whisper import WhisperModel


def format_srt_time(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    total_seconds = int(seconds)

    s = total_seconds % 60
    m = (total_seconds // 60) % 60
    h = total_seconds // 3600

    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def format_vtt_time(seconds: float) -> str:
    ms = int((seconds % 1) * 1000)
    total_seconds = int(seconds)

    s = total_seconds % 60
    m = (total_seconds // 60) % 60
    h = total_seconds // 3600

    return f"{h:02}:{m:02}:{s:02}.{ms:03}"


def write_srt(output_file: Path, segments):
    with open(output_file, "w", encoding="utf-8") as f:

        for index, segment in enumerate(segments, start=1):

            f.write(f"{index}\n")

            f.write(
                f"{format_srt_time(segment.start)} --> "
                f"{format_srt_time(segment.end)}\n"
            )

            f.write(segment.text.strip())
            f.write("\n\n")


def write_vtt(output_file: Path, segments):
    with open(output_file, "w", encoding="utf-8") as f:

        f.write("WEBVTT\n\n")

        for segment in segments:

            f.write(
                f"{format_vtt_time(segment.start)} --> "
                f"{format_vtt_time(segment.end)}\n"
            )

            f.write(segment.text.strip())
            f.write("\n\n")


def write_txt(output_file: Path, segments):
    with open(output_file, "w", encoding="utf-8") as f:

        for segment in segments:
            f.write(segment.text.strip())
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

    print("Loading model...")

    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8"
    )

    print("Transcribing audio...")

    segments, info = model.transcribe(
        str(input_file),
        language=args.language
    )

    segments = list(segments)

    print(
        f"Detected language: {info.language}"
    )

    if args.format == "srt":
        write_srt(output_file, segments)

    elif args.format == "vtt":
        write_vtt(output_file, segments)

    elif args.format == "txt":
        write_txt(output_file, segments)

    print(
        f"Generated: {output_file}"
    )


if __name__ == "__main__":
    main()