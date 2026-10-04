#!/usr/bin/env python3

import argparse
import math
import re
from dataclasses import dataclass
from numbers import Real
from pathlib import Path


@dataclass(frozen=True)
class SegmentationConfig:
    """Timing thresholds in seconds; there is deliberately no character limit."""

    pause_seconds: float = 0.5
    comma_pause_seconds: float = 0.25
    long_pause_seconds: float = 1.0
    clause_speech_seconds: float = 3.0
    min_cue_speech_seconds: float = 0.8


SEGMENTATION_CONFIG = SegmentationConfig()

# Conservative phrase rules, not a morphological dictionary. Keep uncertain
# Japanese script runs intact rather than treating Whisper pieces as words.
JAPANESE_EXPRESSIONS = (
    "について", "につき", "に関して", "に対して", "に対する", "によって",
    "による", "にとって", "において", "における", "として", "という",
    "といった", "とはいえ", "だけでなく", "だけではなく", "かもしれない",
    "なければならない", "なくてはならない", "ではありません", "ではない",
    "ている", "でいる", "ていた", "でいた", "てある", "である",
    "てしまう", "てください", "ていく", "てくる",
)
EXPRESSION_PATTERN = re.compile(
    "|".join(re.escape(value) for value in sorted(JAPANESE_EXPRESSIONS, key=len, reverse=True))
)
SCRIPT_RUN_PATTERN = re.compile(
    r"[ぁ-ゖゝゞー]+|[ァ-ヺヽヾー]+|[一-鿿㐀-䶿々〆ヶ]+|"
    r"[A-Za-z0-9０-９_]+(?:[.．,，:：/@'’+\-][A-Za-z0-9０-９_]+)*"
)
CLAUSE_END_PATTERN = re.compile(
    r"(?:について|に関して|に対して|によって|にとって|において|として|"
    r"でした|ました|ません|でしょう|だろう|です|ます|だった|った|いた|んだ|"
    r"ない|たい|から|ので|"
    r"けれども|けれど|けど|ても|でも|ながら|なら|たり|[はがをにもへとで])"
)
ATTACHED_WORD_PARTS = (
    "は が を に へ と で も の や ね よ ぞ さ か て た し ば ず ぬ "
    "な ん る れ られ せ させ です ます でした ました ません だ だった "
    "ございます ください でない ではない じゃない じゃありません"
).split()
ATTACHED_PART_PATTERN = re.compile(
    "|".join(re.escape(part) for part in sorted(ATTACHED_WORD_PARTS, key=len, reverse=True))
)
LEADING_HIRAGANA_PATTERN = re.compile(r"^[ぁ-ゖー]+")
INDEPENDENT_RESPONSES = frozenset({
    "はい", "いいえ", "うん", "ううん", "ええ", "そう", "なるほど",
    "了解", "ありがとう", "ありがとうございます", "お願いします",
    "どうぞ", "わかりました", "分かりました", "わかった", "了解しました",
    "そうです", "そうですね", "OK", "Yes", "No", "yes", "no",
})
CLOSING_MARKS = frozenset("」』）)]}】〉》”’\"'")
OPENING_MARKS = "「『（([{【〈《“‘\"'"
RESPONSE_PATTERN = re.compile(
    r"\s*[" + re.escape(OPENING_MARKS) + r"]*(?:"
    + "|".join(re.escape(value) for value in INDEPENDENT_RESPONSES)
    + r")[" + re.escape("、。，．,.!?！？" + "".join(CLOSING_MARKS)) + r"]*\s*"
)


@dataclass
class SubtitleCue:
    start: float
    end: float
    # Original text, including punctuation. Display cleanup belongs to writers.
    text: str


@dataclass(frozen=True)
class TimedWord:
    start: float
    end: float
    text_start: int
    text_end: int


@dataclass(frozen=True)
class CueBoundary:
    word_index: int
    hard: bool


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


def _punctuation_kind(text: str, index: int) -> str:
    character = text[index]
    if character not in "、。，．,.!?！？":
        return ""
    before = text[index - 1] if index else ""
    after = text[index + 1] if index + 1 < len(text) else ""
    if character in ".．,，" and before.isdigit() and after.isdigit():
        return ""  # Decimal/grouping marks, including full-width numbers.
    if character in ".．" and after.isdigit():
        return ""  # Leading decimals such as .5 and -.5.
    if character in "!?" and after and after in "=<>+-*/&|%^~":
        return ""  # Operators such as !=, not sentence punctuation.
    if character in "!?" and after.isascii() and after.isalnum():
        return ""  # Prefix operators / notation, e.g. !flag.
    if character == "!" and before.isdigit():
        return ""  # A trailing factorial can be meaningful (5!).
    if character in ".,!?" and before.isascii() and before.isalnum() and after.isascii() and after.isalnum():
        return ""  # Embedded notation such as v1.0, example.com or a,b.
    if character == "." and index >= 2 and text[index - 2] == "." and before.isascii() and before.isalpha():
        return ""  # Final period of an initialism, e.g. U.S.
    return "comma" if character in "、，," else "sentence"


def normalize_subtitle_text(text: str) -> str:
    """Display only: preserve numbers, colons, operators, brackets and notation."""
    visible = "".join(
        character for index, character in enumerate(text)
        if not _punctuation_kind(text, index)
    )
    return " ".join(visible.split())


def _is_independent_response(text: str) -> bool:
    # Inspect the raw source, without running the display transformation.
    return RESPONSE_PATTERN.fullmatch(text) is not None


def _starts_with_attached_word(text: str) -> bool:
    leading = LEADING_HIRAGANA_PATTERN.match(text.lstrip().lstrip(OPENING_MARKS))
    if not leading or _is_independent_response(text):
        return False
    # Scan parts once; a repeated, overlapping alternation with fullmatch can
    # backtrack exponentially on long repeated recognition text.
    prefix = leading.group()
    return "".join(ATTACHED_PART_PATTERN.findall(prefix)) == prefix


def _valid_interval(start, end) -> bool:
    return (
        isinstance(start, Real) and not isinstance(start, bool)
        and isinstance(end, Real) and not isinstance(end, bool)
        and math.isfinite(start) and math.isfinite(end)
        and 0 <= start < end
        and round(start * 1000) < round(end * 1000)
    )


def _reaches(duration: float, threshold: float) -> bool:
    # Compare at the same millisecond resolution as the output, avoiding
    # subtraction noise such as 0.7 - 0.2 falling just below 0.5 seconds.
    return round(duration * 1000) >= round(threshold * 1000)


def _align_segment_words(segment) -> list[TimedWord]:
    """Align exact non-whitespace characters; never normalize recognition text."""
    words = getattr(segment, "words", None)
    if not words:
        raise ValueError("missing word timestamps")
    positions = [index for index, character in enumerate(segment.text) if not character.isspace()]
    source = "".join(segment.text[index] for index in positions)
    cursor = 0
    previous_end = segment.start
    aligned = []
    for index, word in enumerate(words):
        start = getattr(word, "start", None)
        end = getattr(word, "end", None)
        if not _valid_interval(start, end):
            raise ValueError(f"word {index}: invalid or missing time interval")
        if start < segment.start or end > segment.end:
            raise ValueError(f"word {index}: timestamps outside segment")
        if start < previous_end:
            raise ValueError(f"word {index}: overlapping or out-of-order timestamps")
        spelling = getattr(word, "word", None)
        if not isinstance(spelling, str) or not spelling.strip():
            raise ValueError(f"word {index}: empty or missing text")
        spelling = "".join(spelling.split())
        if not source.startswith(spelling, cursor):
            raise ValueError(f"word {index}: text does not match original segment")
        next_cursor = cursor + len(spelling)
        aligned.append(TimedWord(start, end, positions[cursor], positions[next_cursor - 1] + 1))
        cursor = next_cursor
        previous_end = end
    if cursor != len(source):
        raise ValueError("word text does not cover the entire segment")
    return aligned


def _boundary_punctuation(text: str, end: int) -> str:
    kind = ""
    for index in range(end - 1, -1, -1):
        if text[index].isspace() or text[index] in CLOSING_MARKS:
            continue
        current = _punctuation_kind(text, index)
        if not current:
            break
        if current == "sentence" or not kind:
            kind = current
    return kind


def _phrase_boundaries(text: str, words: list[TimedWord]) -> set[int]:
    """Conservative lexical boundaries expressed as indexes into timed words."""
    protected = bytearray(len(text) + 1)
    for pattern in (SCRIPT_RUN_PATTERN, EXPRESSION_PATTERN):
        for match in pattern.finditer(text):
            protected[match.start() + 1:match.end()] = b"\x01" * (match.end() - match.start() - 1)
    clause_ends = {match.end() for match in CLAUSE_END_PATTERN.finditer(text)}
    safe = set()
    for index in range(1, len(words)):
        left, right = words[index - 1], words[index]
        left_text = text[left.text_start:left.text_end].strip()
        if left_text and all(character in OPENING_MARKS for character in left_text):
            continue  # An opening quote belongs to the following speech.
        offset = left.text_end
        next_text = text[right.text_start:right.text_end].lstrip(OPENING_MARKS)
        lookahead = index
        while not next_text and lookahead + 1 < len(words):
            lookahead += 1
            following = words[lookahead]
            next_text = text[following.text_start:following.text_end].lstrip(OPENING_MARKS)
        if not next_text or all(
            _punctuation_kind(next_text, position) or character in CLOSING_MARKS
            for position, character in enumerate(next_text)
        ):
            continue  # Keep standalone punctuation with the preceding speech.
        if _starts_with_attached_word(next_text):
            continue
        # Separate recognized responses even when adjacent all-hiragana runs
        # would otherwise be ambiguous (e.g. はい + わかりました).
        if _is_independent_response(left_text) and _is_independent_response(next_text):
            safe.add(index)
            continue
        if protected[offset] or protected[right.text_start]:
            continue
        if _boundary_punctuation(text, offset):
            safe.add(index)
        elif text[offset:right.text_start].strip() == "" and offset < right.text_start:
            safe.add(index)
        elif offset in clause_ends:
            safe.add(index)
        elif _is_independent_response(left_text):
            safe.add(index)
    return safe


def _split_aligned_text(
    text: str, words: list[TimedWord], config: SegmentationConfig
) -> list[SubtitleCue]:
    if not words:
        return []
    safe = _phrase_boundaries(text, words)
    speech = [0.0]
    for word in words:
        speech.append(speech[-1] + word.end - word.start)
    boundaries = [CueBoundary(0, True)]
    for index in range(1, len(words)):
        if index not in safe:
            continue
        previous, following = words[index - 1], words[index]
        gap = following.start - previous.end
        punctuation = _boundary_punctuation(text, previous.text_end)
        if not punctuation and not _reaches(gap, config.pause_seconds):
            continue
        cue_start = boundaries[-1].word_index
        source_start = words[cue_start - 1].text_end if cue_start else 0
        independent = _is_independent_response(text[source_start:previous.text_end])
        hard = punctuation == "sentence" or _reaches(gap, config.long_pause_seconds)
        if hard or _reaches(gap, config.pause_seconds) or (
            punctuation == "comma" and (
                _reaches(gap, config.comma_pause_seconds)
                or _reaches(speech[index] - speech[cue_start], config.clause_speech_seconds)
                or independent
            )
        ):
            boundaries.append(CueBoundary(index, hard or independent))
    boundaries.append(CueBoundary(len(words), True))

    # A short fragment may absorb a neighbour only across a soft boundary.
    # Sentence endings, independent responses and long pauses remain barriers.
    pieces = []
    for before, after in zip(boundaries, boundaries[1:]):
        start, end = before.word_index, after.word_index
        source_start = words[start - 1].text_end if start else 0
        independent = (
            _boundary_punctuation(text, words[end - 1].text_end) == "sentence"
            or _is_independent_response(text[source_start:words[end - 1].text_end])
        )
        short = not _reaches(speech[end] - speech[start], config.min_cue_speech_seconds)
        if pieces and not before.hard and ((short and not independent) or pieces[-1][2]):
            previous_start = pieces[-1][0]
            combined_short = not _reaches(speech[end] - speech[previous_start], config.min_cue_speech_seconds)
            pieces[-1] = (previous_start, end, combined_short and not independent)
        else:
            pieces.append((start, end, short and not independent))
    cues = []
    for start, end, _ in pieces:
        text_start = words[start - 1].text_end if start else 0
        text_end = words[end - 1].text_end if end < len(words) else len(text)
        cues.append(SubtitleCue(words[start].start, words[end - 1].end, text[text_start:text_end]))
    return cues


def create_subtitle_cues(segments, config: SegmentationConfig = SEGMENTATION_CONFIG) -> list[SubtitleCue]:
    """Shared SRT/VTT pipeline. Valid adjacent segments can form one phrase."""
    cues = []
    text_parts = []
    words = []
    text_length = 0

    def flush():
        nonlocal text_length
        cues.extend(_split_aligned_text("".join(text_parts), words, config))
        text_parts.clear()
        words.clear()
        text_length = 0

    previous_end = 0.0
    for index, segment in enumerate(segments):
        if not _valid_interval(segment.start, segment.end) or segment.start < previous_end:
            raise ValueError(f"segment {index}: invalid or overlapping segment timestamps")
        previous_end = segment.end
        try:
            aligned = _align_segment_words(segment)
        except ValueError as error:
            flush()
            log(f"Subtitle fallback: segment {index} [{segment.start:.3f}, {segment.end:.3f}]: {error}")
            cues.append(SubtitleCue(segment.start, segment.end, segment.text))
            continue
        # Do not combine segments over long silence, even when their text looks
        # like one word. The segment boundary is already supplied by the model.
        if words:
            first_word = segment.text[aligned[0].text_start:aligned[0].text_end]
            separate_response = (
                _is_independent_response(text_parts[-1])
                or _is_independent_response(segment.text)
            ) and not _starts_with_attached_word(first_word)
            if separate_response or _reaches(aligned[0].start - words[-1].end, config.long_pause_seconds):
                flush()
        words.extend(
            TimedWord(word.start, word.end, word.text_start + text_length, word.text_end + text_length)
            for word in aligned
        )
        text_parts.append(segment.text)
        text_length += len(segment.text)
    flush()
    return cues


def split_segment_to_cues(segment, config: SegmentationConfig = SEGMENTATION_CONFIG) -> list[SubtitleCue]:
    return create_subtitle_cues([segment], config)


def _display_cues(segments):
    return [
        SubtitleCue(cue.start, cue.end, text)
        for cue in create_subtitle_cues(segments)
        if (text := normalize_subtitle_text(cue.text))
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
