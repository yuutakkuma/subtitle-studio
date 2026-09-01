#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
from pathlib import Path

MAX_SUBTITLE_CHARACTERS = 20
REMOVED_SUBTITLE_PUNCTUATION = "、。，．,.!?！？:：;；"
PREFERRED_BREAK_CHARACTERS = set(" ")


@dataclass
class SubtitleCue:
    start: float
    end: float
    text: str


def log(message: str):
    print(message, flush=True)


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


def normalize_subtitle_text(text: str) -> str:
    single_line_text = " ".join(text.split())
    punctuation_removed_text = single_line_text.translate(
        str.maketrans("", "", REMOVED_SUBTITLE_PUNCTUATION)
    )
    return " ".join(punctuation_removed_text.split())


def split_subtitle_text(
    text: str,
    max_characters: int = MAX_SUBTITLE_CHARACTERS
) -> list[str]:
    if max_characters <= 0:
        raise ValueError("max_characters must be greater than zero")

    remaining_text = normalize_subtitle_text(text)
    chunks = []

    while len(remaining_text) > max_characters:
        split_position = max_characters
        preferred_start = max_characters // 2

        for index in range(max_characters - 1, preferred_start - 1, -1):
            if remaining_text[index] in PREFERRED_BREAK_CHARACTERS:
                split_position = index if remaining_text[index].isspace() else index + 1
                break

        chunk = remaining_text[:split_position].strip()

        if chunk:
            chunks.append(chunk)

        remaining_text = remaining_text[split_position:].strip()

    if remaining_text:
        chunks.append(remaining_text)

    return chunks


def split_segment_to_cues(segment) -> list[SubtitleCue]:
    chunks = split_subtitle_text(segment.text)

    if not chunks:
        return []

    duration = max(segment.end - segment.start, 0)
    total_characters = sum(len(chunk) for chunk in chunks)
    cues = []
    elapsed_characters = 0

    for index, chunk in enumerate(chunks):
        cue_start = (
            segment.start + duration * elapsed_characters / total_characters
        )
        elapsed_characters += len(chunk)
        cue_end = (
            segment.end
            if index == len(chunks) - 1
            else segment.start + duration * elapsed_characters / total_characters
        )
        cues.append(SubtitleCue(start=cue_start, end=cue_end, text=chunk))

    return cues


def create_subtitle_cues(segments) -> list[SubtitleCue]:
    cues = []

    for segment in segments:
        cues.extend(split_segment_to_cues(segment))

    return cues


def write_srt(output_file: Path, segments):
    cues = create_subtitle_cues(segments)

    with open(output_file, "w", encoding="utf-8") as f:
        for index, cue in enumerate(cues, start=1):
            f.write(f"{index}\n")
            f.write(
                f"{format_srt_time(cue.start)} --> "
                f"{format_srt_time(cue.end)}\n"
            )
            f.write(cue.text)
            f.write("\n\n")


def write_vtt(output_file: Path, segments):
    cues = create_subtitle_cues(segments)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("WEBVTT\n\n")

        for cue in cues:
            f.write(
                f"{format_vtt_time(cue.start)} --> "
                f"{format_vtt_time(cue.end)}\n"
            )
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
        language=args.language
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
