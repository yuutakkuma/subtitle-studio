#!/usr/bin/env python3

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

MAX_SUBTITLE_LINE_WIDTH = 18
HARD_SUBTITLE_LINE_WIDTH = 24
MAX_SUBTITLE_LINES = 2
MAX_SUBTITLE_DURATION = 6.0
MERGE_GAP_SECONDS = 0.35
SHORT_CUE_MERGE_GAP_SECONDS = 1.0
MIN_CUE_WIDTH = 8
SHORT_LINE_WIDTH = 8
MIN_LINE_WIDTH = 6
READING_MARGIN_SECONDS = 0.45
MIN_SUBTITLE_DURATION = 1.0
MIN_CUE_GAP_SECONDS = 0.05
BREAK_CHARS = set(" 、。，．,.!?！？:：;；)]}）』」")
STRONG_BREAK_CHARS = set("。！？!?")
MEDIUM_BREAK_CHARS = set("、，,")
SMALL_KANA_CHARS = set("ゃゅょぁぃぅぇぉっャュョァィゥェォッ")
CONTINUATION_START_CHARS = SMALL_KANA_CHARS | set("ー")
SHORT_KANA_FRAGMENT_WIDTH = 5
SENTENCE_ENDING_KANA_MIN_WIDTH = 6
SENTENCE_ENDING_KANA_MAX_WIDTH = 8
TRAILING_DISPLAY_PUNCTUATION = "、，,"


@dataclass
class SubtitleCue:
    start: float
    end: float
    text: str


@dataclass
class TimedToken:
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
    return re.sub(r"\s+", " ", text).strip()


def clean_display_line(text: str) -> str:
    return normalize_subtitle_text(text).rstrip(TRAILING_DISPLAY_PUNCTUATION)


def clean_display_text(text: str) -> str:
    return "\n".join(
        clean_display_line(line)
        for line in text.split("\n")
    ).strip()


def is_cjk(char: str) -> bool:
    return bool(char) and unicodedata.east_asian_width(char) in {
        "F",
        "W",
        "A",
    }


def join_subtitle_text(left: str, right: str) -> str:
    left = normalize_subtitle_text(left)
    right = normalize_subtitle_text(right)

    if not left:
        return right

    if not right:
        return left

    if is_cjk(left[-1]) and is_cjk(right[0]):
        return left + right

    return f"{left} {right}"


def character_width(char: str) -> float:
    if char.isspace():
        return 0.5

    if unicodedata.east_asian_width(char) in {
        "F",
        "W",
        "A",
    }:
        return 1.0

    return 0.5


def text_width(text: str) -> float:
    return sum(character_width(char) for char in text)


def is_hiragana(char: str) -> bool:
    return "\u3040" <= char <= "\u309f"


def is_katakana(char: str) -> bool:
    return "\u30a0" <= char <= "\u30ff"


def is_kana(char: str) -> bool:
    return is_hiragana(char) or is_katakana(char) or char == "ー"


def is_kanji(char: str) -> bool:
    return "\u4e00" <= char <= "\u9fff"


def leading_run(text: str, predicate) -> str:
    chars = []

    for char in text:
        if not predicate(char):
            break

        chars.append(char)

    return "".join(chars)


def trailing_run(text: str, predicate) -> str:
    chars = []

    for char in reversed(text):
        if not predicate(char):
            break

        chars.append(char)

    return "".join(reversed(chars))


def starts_with_continuation_char(text: str) -> bool:
    return bool(text) and text[0] in CONTINUATION_START_CHARS


def ends_with_continuation_char(text: str) -> bool:
    return bool(text) and text[-1] in CONTINUATION_START_CHARS


def splits_continuous_japanese_text(left: str, right: str) -> bool:
    if not left or not right:
        return False

    return (
        (is_kana(left[-1]) and is_kana(right[0])) or
        (is_kanji(left[-1]) and is_kanji(right[0])) or
        (is_kanji(left[-1]) and is_kana(right[0]))
    )


def creates_short_kana_tail(right: str) -> bool:
    kana_head = leading_run(right, is_kana)

    if not kana_head:
        return False

    head_width = text_width(kana_head)

    if head_width <= 2:
        return True

    if head_width > SHORT_KANA_FRAGMENT_WIDTH:
        return False

    rest = right[len(kana_head):]

    return not rest or rest[0] in BREAK_CHARS


def trailing_kana_unit(text: str) -> str:
    return trailing_run(text, is_kana)


def is_sentence_ending_kana_fragment(right: str) -> bool:
    kana_head = leading_run(right, is_kana)

    if not kana_head:
        return False

    head_width = text_width(kana_head)

    if (
        head_width < SENTENCE_ENDING_KANA_MIN_WIDTH or
        head_width > SENTENCE_ENDING_KANA_MAX_WIDTH
    ):
        return False

    rest = right[len(kana_head):]

    return not rest or rest[0] in STRONG_BREAK_CHARS


def splits_short_kana_unit(left: str, right: str) -> bool:
    kana_tail = trailing_kana_unit(left)

    if not kana_tail:
        return False

    if text_width(kana_tail) > SHORT_KANA_FRAGMENT_WIDTH:
        return False

    return bool(right) and (is_kana(right[0]) or is_kanji(right[0]))


def break_position_score(
    text: str,
    position: int,
    target_line_width: int = MAX_SUBTITLE_LINE_WIDTH,
    hard_line_width: int = HARD_SUBTITLE_LINE_WIDTH
) -> float:
    left = normalize_subtitle_text(text[:position])
    right = normalize_subtitle_text(text[position:])

    if not left or not right:
        return -10000

    left_width = text_width(left)
    right_width = text_width(right)

    if left_width > hard_line_width:
        return -10000

    score = 0.0
    preferred_width = hard_line_width * 0.85
    score -= abs(left_width - preferred_width)

    if left_width > target_line_width:
        score -= (left_width - target_line_width) * 2

    if starts_with_continuation_char(right):
        score -= 150

    if ends_with_continuation_char(left):
        score -= 150

    if splits_continuous_japanese_text(left, right):
        score -= 90

    if creates_short_kana_tail(right):
        score -= 120

    if splits_short_kana_unit(left, right):
        score -= 80

    left_kana_tail_width = text_width(trailing_run(left, is_kana))

    if (
        is_sentence_ending_kana_fragment(right) and
        left_kana_tail_width <= 3
    ):
        score += 95

    if left_width < MIN_LINE_WIDTH:
        score -= 30

    if right_width < MIN_LINE_WIDTH:
        score -= 25

    if left[-1] in STRONG_BREAK_CHARS:
        score += 100
    elif left[-1] in MEDIUM_BREAK_CHARS:
        score += 70

    if left[-1:] in BREAK_CHARS:
        score += 35

    return score


def best_text_split_position(
    text: str,
    target_line_width: int = MAX_SUBTITLE_LINE_WIDTH,
    hard_line_width: int = HARD_SUBTITLE_LINE_WIDTH
) -> int:
    best_position = 0
    best_score = -10000.0
    fallback_position = 0
    current_width = 0.0

    for index, char in enumerate(text, start=1):
        current_width += character_width(char)

        if current_width <= hard_line_width:
            fallback_position = index
        elif fallback_position > 0:
            break

        score = break_position_score(
            text,
            index,
            target_line_width,
            hard_line_width
        )

        if score > best_score:
            best_score = score
            best_position = index

    return best_position or fallback_position or len(text)


def wrap_subtitle_text(
    text: str,
    target_line_width: int = MAX_SUBTITLE_LINE_WIDTH,
    hard_line_width: int = HARD_SUBTITLE_LINE_WIDTH
) -> list[str]:
    remaining_text = normalize_subtitle_text(text)
    lines = []

    while remaining_text:
        if text_width(remaining_text) <= hard_line_width:
            lines.append(remaining_text.strip())
            break

        split_position = best_text_split_position(
            remaining_text,
            target_line_width,
            hard_line_width
        )
        line = remaining_text[:split_position].strip()

        if not line:
            line = remaining_text[:1].strip()
            split_position = 1

        lines.append(line)
        remaining_text = remaining_text[split_position:].strip()

    return lines


def split_lines_into_blocks(
    lines: list[str],
    max_lines: int = MAX_SUBTITLE_LINES
) -> list[str]:
    if (
        max_lines == 2 and
        len(lines) == 3 and
        text_width(lines[-1]) <= SHORT_LINE_WIDTH
    ):
        return [
            lines[0],
            "\n".join(lines[1:])
        ]

    blocks = []

    for index in range(0, len(lines), max_lines):
        block_lines = lines[index:index + max_lines]
        blocks.append("\n".join(block_lines))

    return blocks


def create_text_timing_cues(segment) -> list[SubtitleCue]:
    lines = wrap_subtitle_text(segment.text)
    blocks = split_lines_into_blocks(lines)

    if not blocks:
        return []

    duration = max(segment.end - segment.start, 0)
    weights = [
        max(text_width(block.replace("\n", "")), 1.0)
        for block in blocks
    ]
    total_weight = sum(weights)
    cues = []
    current_start = segment.start
    elapsed_weight = 0.0

    for index, block in enumerate(blocks):
        if index == len(blocks) - 1 or duration == 0:
            cue_end = segment.end
        else:
            elapsed_weight += weights[index]
            cue_end = (
                segment.start +
                duration *
                elapsed_weight /
                total_weight
            )

        cues.append(
            SubtitleCue(
                start=current_start,
                end=cue_end,
                text=clean_display_text(block)
            )
        )
        current_start = cue_end

    return cues


def split_long_token(token: TimedToken) -> list[TimedToken]:
    text = normalize_subtitle_text(token.text)

    if text_width(text) <= MIN_LINE_WIDTH:
        return [
            TimedToken(
                start=token.start,
                end=token.end,
                text=token.text
            )
        ]

    chars = [char for char in text if not char.isspace()]
    weights = [max(character_width(char), 0.5) for char in chars]
    total_weight = sum(weights)

    if not chars or token.end <= token.start:
        return [
            TimedToken(
                start=token.start,
                end=token.end,
                text=text
            )
        ]

    tokens = []
    current_start = token.start
    elapsed_weight = 0.0

    for index, char in enumerate(chars):
        if index == len(chars) - 1:
            current_end = token.end
        else:
            elapsed_weight += weights[index]
            current_end = (
                token.start +
                (token.end - token.start) *
                elapsed_weight /
                total_weight
            )

        tokens.append(
            TimedToken(
                start=current_start,
                end=current_end,
                text=char
            )
        )
        current_start = current_end

    return tokens


def create_timed_tokens(segment) -> list[TimedToken]:
    words = getattr(segment, "words", None)

    if not words:
        return []

    tokens = []

    for word in words:
        text = getattr(word, "word", "")
        start = getattr(word, "start", None)
        end = getattr(word, "end", None)

        if not text or start is None or end is None:
            continue

        token = TimedToken(
            start=max(float(start), float(segment.start)),
            end=min(float(end), float(segment.end)),
            text=text
        )

        tokens.extend(split_long_token(token))

    return [
        token
        for token in tokens
        if token.end > token.start and normalize_subtitle_text(token.text)
    ]


def timed_line_text(tokens: list[TimedToken]) -> str:
    return normalize_subtitle_text("".join(token.text for token in tokens))


def token_sequence_text(tokens: list[TimedToken]) -> str:
    return normalize_subtitle_text("".join(token.text for token in tokens))


def best_token_split_index(
    tokens: list[TimedToken],
    target_line_width: int = MAX_SUBTITLE_LINE_WIDTH,
    hard_line_width: int = HARD_SUBTITLE_LINE_WIDTH
) -> int:
    text = token_sequence_text(tokens)
    best_index = 0
    best_score = -10000.0
    fallback_index = 0
    position = 0

    for index, token in enumerate(tokens[:-1], start=1):
        position += len(normalize_subtitle_text(token.text))
        left = token_sequence_text(tokens[:index])

        if text_width(left) <= hard_line_width:
            fallback_index = index
        else:
            break

        score = break_position_score(
            text,
            position,
            target_line_width,
            hard_line_width
        )

        if score > best_score:
            best_score = score
            best_index = index

    return best_index or fallback_index


def wrap_timed_tokens(
    tokens: list[TimedToken],
    target_line_width: int = MAX_SUBTITLE_LINE_WIDTH,
    hard_line_width: int = HARD_SUBTITLE_LINE_WIDTH
) -> list[list[TimedToken]]:
    lines = []
    remaining_tokens = list(tokens)

    while remaining_tokens:
        current_line = []
        current_width = 0.0

        for token in remaining_tokens:
            token_width = text_width(normalize_subtitle_text(token.text))

            if current_line and current_width + token_width > hard_line_width:
                break

            current_line.append(token)
            current_width += token_width

        if len(current_line) == len(remaining_tokens):
            lines.append(current_line)
            break

        candidate_count = min(len(current_line) + 1, len(remaining_tokens))
        split_index = best_token_split_index(
            remaining_tokens[:candidate_count],
            target_line_width,
            hard_line_width
        )

        if split_index <= 0:
            split_index = max(len(current_line), 1)

        lines.append(remaining_tokens[:split_index])
        remaining_tokens = remaining_tokens[split_index:]

    return lines


def split_timed_lines_into_blocks(
    lines: list[list[TimedToken]],
    max_lines: int = MAX_SUBTITLE_LINES
) -> list[list[list[TimedToken]]]:
    if (
        max_lines == 2 and
        len(lines) == 3 and
        text_width(timed_line_text(lines[-1])) <= SHORT_LINE_WIDTH
    ):
        return [
            [lines[0]],
            lines[1:]
        ]

    blocks = []

    for index in range(0, len(lines), max_lines):
        blocks.append(lines[index:index + max_lines])

    return blocks


def format_cue_text(text: str) -> Optional[str]:
    lines = wrap_subtitle_text(text)

    if not lines or len(lines) > MAX_SUBTITLE_LINES:
        return None

    return clean_display_text("\n".join(lines))


def can_merge_cues(
    previous: SubtitleCue,
    current: SubtitleCue
) -> Tuple[bool, Optional[str]]:
    gap = current.start - previous.end
    duration = current.end - previous.start

    previous_width = text_width(previous.text.replace("\n", ""))
    current_width = text_width(current.text.replace("\n", ""))
    max_gap = (
        SHORT_CUE_MERGE_GAP_SECONDS
        if min(previous_width, current_width) < MIN_CUE_WIDTH
        else MERGE_GAP_SECONDS
    )

    if gap < 0 or gap > max_gap:
        return False, None

    if duration > MAX_SUBTITLE_DURATION:
        return False, None

    merged_text = normalize_subtitle_text(
        join_subtitle_text(
            previous.text.replace("\n", " "),
            current.text.replace("\n", "")
        )
    )
    formatted_text = format_cue_text(merged_text)

    if formatted_text is None:
        return False, None

    return True, formatted_text


def merge_nearby_cues(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    if not cues:
        return []

    merged = [cues[0]]

    for cue in cues[1:]:
        previous = merged[-1]
        can_merge, formatted_text = can_merge_cues(previous, cue)

        if can_merge and formatted_text:
            merged[-1] = SubtitleCue(
                start=previous.start,
                end=cue.end,
                text=clean_display_text(formatted_text)
            )
        else:
            merged.append(cue)

    return merged


def add_reading_margins(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    adjusted = []

    for index, cue in enumerate(cues):
        next_start = (
            cues[index + 1].start
            if index + 1 < len(cues)
            else None
        )
        target_end = max(
            cue.end + READING_MARGIN_SECONDS,
            cue.start + MIN_SUBTITLE_DURATION
        )

        if next_start is not None:
            target_end = min(
                target_end,
                next_start - MIN_CUE_GAP_SECONDS
            )

        adjusted.append(
            SubtitleCue(
                start=cue.start,
                end=max(target_end, cue.end),
                text=cue.text
            )
        )

    return adjusted


def polish_subtitle_cues(cues: list[SubtitleCue]) -> list[SubtitleCue]:
    return add_reading_margins(merge_nearby_cues(cues))


def timed_block_to_cue(
    block: list[list[TimedToken]],
    segment
) -> SubtitleCue:
    block_tokens = [
        token
        for line in block
        for token in line
    ]
    text = clean_display_text(
        "\n".join(timed_line_text(line) for line in block)
    )

    return SubtitleCue(
        start=max(block_tokens[0].start, segment.start),
        end=min(block_tokens[-1].end, segment.end),
        text=text
    )


def split_segment_to_cues(segment) -> list[SubtitleCue]:
    tokens = create_timed_tokens(segment)

    if not tokens:
        return create_text_timing_cues(segment)

    lines = wrap_timed_tokens(tokens)
    blocks = split_timed_lines_into_blocks(lines)

    return [
        timed_block_to_cue(block, segment)
        for block in blocks
    ]


def create_subtitle_cues(segments) -> list[SubtitleCue]:
    cues = []

    for segment in segments:
        cues.extend(split_segment_to_cues(segment))

    return polish_subtitle_cues(cues)


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
        word_timestamps=True
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
