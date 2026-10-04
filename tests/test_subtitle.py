import contextlib
import io
import math
import random
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from subtitle import (
    SEGMENTATION_CONFIG,
    create_parser,
    create_subtitle_cues,
    format_srt_time,
    format_vtt_time,
    main,
    normalize_subtitle_text,
    split_segment_to_cues,
    write_srt,
    write_txt,
    write_vtt,
)


def word(text, start, end):
    return SimpleNamespace(word=text, start=start, end=end)


def segment(parts, start=None, end=None, text=None):
    words = [word(*part) for part in parts]
    return SimpleNamespace(
        start=words[0].start if start is None else start,
        end=words[-1].end if end is None else end,
        text="".join(item.word for item in words) if text is None else text,
        words=words,
    )


def visible(cues):
    return [normalize_subtitle_text(cue.text) for cue in cues]


class SubtitleSegmentationTest(unittest.TestCase):
    def assert_lossless(self, segments, cues):
        self.assertEqual("".join(item.text for item in segments), "".join(cue.text for cue in cues))

    def test_no_character_limit_even_for_long_unpunctuated_speech(self):
        text = "この長い動画で説明する内容について途中で言葉を切らず自然な字幕として表示します"
        item = segment([(text, 2.0, 15.0)], start=0, end=18)
        cues = create_subtitle_cues([item])
        self.assertGreater(len(cues[0].text), 20)
        self.assertEqual([(2.0, 15.0, text)], [(cue.start, cue.end, cue.text) for cue in cues])

    def test_many_word_pieces_do_not_trigger_character_splits(self):
        text = "今回の長い動画について詳しく説明しながら自然な字幕の表示方法を確認します"
        item = segment([(character, index / 10, (index + 1) / 10) for index, character in enumerate(text)])
        cues = create_subtitle_cues([item])
        self.assertEqual(1, len(cues))
        self.assert_lossless([item], cues)

    def test_long_repeated_hiragana_is_processed_without_losing_text(self):
        item = segment([("確認は、", 0, 1), ("でした" * 150 + "あ", 1.6, 4)])
        cues = create_subtitle_cues([item])
        self.assertEqual(2, len(cues))
        self.assert_lossless([item], cues)

    def test_sentence_endings_split_without_pause_and_keep_short_answers(self):
        item = segment([("はい。", 0, 0.2), ("本題です！", 0.2, 1.7), ("準備はいいですか？", 1.7, 3.2)])
        cues = create_subtitle_cues([item])
        self.assertEqual(["はい", "本題です", "準備はいいですか"], visible(cues))
        self.assert_lossless([item], cues)

    def test_comma_with_pause_splits_at_word_times(self):
        item = segment([("今日は、", 2.0, 3.2), ("動画について", 3.55, 5.2), ("説明します。", 5.3, 9.1)], start=0, end=12)
        cues = create_subtitle_cues([item])
        self.assertEqual(["今日は", "動画について説明します"], visible(cues))
        self.assertEqual([(2.0, 3.2), (3.55, 9.1)], [(cue.start, cue.end) for cue in cues])
        self.assert_lossless([item], cues)

    def test_not_every_comma_creates_a_cue(self):
        item = segment([("赤、", 0, 0.4), ("青、", 0.45, 0.85), ("黄色です。", 0.9, 2.0)])
        self.assertEqual(["赤青黄色です"], visible(create_subtitle_cues([item])))

    def test_long_spoken_clause_can_break_at_comma_without_a_pause(self):
        item = segment([("ここまでの内容を詳しく確認したので、", 0, 3.5), ("次の説明に進みます。", 3.5, 5.5)])
        self.assertEqual(2, len(create_subtitle_cues([item])))

    def test_pause_at_japanese_phrase_end_without_punctuation(self):
        item = segment([("この件について", 0.3, 1.5), ("詳しく説明します", 2.1, 4.2)])
        self.assertEqual(["この件について", "詳しく説明します"], visible(create_subtitle_cues([item])))

    def test_pause_after_completed_verb_without_punctuation(self):
        item = segment([("確認が終わった", 0, 1.2), ("次を始めます", 3, 4.5)])
        self.assertEqual(["確認が終わった", "次を始めます"], visible(create_subtitle_cues([item])))

    def test_whisper_fragments_do_not_split_japanese_words_or_expressions(self):
        cases = [
            ("この件につい", "て", "詳しく説明します。"),
            ("この件に", "関し", "て説明します。"),
            ("字幕を食", "べ", "ることはできません。"),
            ("東京", "大学", "について説明します。"),
            ("コン", "ピューター", "を使います。"),
            ("字幕を確認し", "まし", "た。"),
            ("彼は来るかも", "しれ", "ない。"),
        ]
        for first, second, third in cases:
            with self.subTest(parts=(first, second, third)):
                item = segment([(first, 0, 1), (second, 1.6, 2.6), (third, 3.2, 4.4)])
                cues = create_subtitle_cues([item])
                expected = [first + second, third] if second == "て" else [first + second + third]
                self.assertEqual(expected, [cue.text for cue in cues])
                self.assert_lossless([item], cues)

    def test_particles_auxiliaries_and_counters_are_not_left_on_next_cue(self):
        for first, second in [("内容", "を確認します。"), ("確認し", "ます。"), ("準備", "でした。"), ("一", "つです。"), ("10", "万円です。")]:
            with self.subTest(parts=(first, second)):
                item = segment([(first, 0, 1), (second, 1.65, 2.8)])
                self.assertEqual(1, len(create_subtitle_cues([item])))

    def test_short_fragment_is_merged_across_soft_boundary(self):
        item = segment([("今日は、", 0, 0.2), ("字幕について説明します。", 0.5, 3)])
        self.assertEqual(["今日は字幕について説明します"], visible(create_subtitle_cues([item])))

    def test_short_tail_is_merged_back(self):
        item = segment([("確認したのは、", 0, 1.8), ("こちら", 2.2, 2.4)])
        self.assertEqual(1, len(create_subtitle_cues([item])))

    def test_short_reply_at_comma_stays_independent(self):
        item = segment([("はい、", 0, 0.2), ("説明を始めます。", 0.25, 2)])
        self.assertEqual(["はい", "説明を始めます"], visible(create_subtitle_cues([item])))

    def test_short_reply_after_soft_boundary_stays_independent(self):
        item = segment([("確認できましたか、", 0, 2), ("はい。", 2.6, 2.8)])
        self.assertEqual(["確認できましたか", "はい"], visible(create_subtitle_cues([item])))

    def test_hiragana_responses_do_not_join_across_silence(self):
        item = segment([("はい", 0, 0.2), ("わかりました", 2, 2.4)])
        self.assertEqual(["はい", "わかりました"], visible(create_subtitle_cues([item])))

    def test_short_fragments_do_not_merge_across_long_silence(self):
        item = segment([("今日は、", 0, 0.2), ("本題です。", 3, 3.4)])
        cues = create_subtitle_cues([item])
        self.assertEqual(2, len(cues))
        self.assertEqual((0.2, 3), (cues[0].end, cues[1].start))

    def test_uneven_speech_uses_word_times_not_text_proportions(self):
        item = segment([("非常に長い説明の前半部分です。", 5, 5.4), ("次。", 8.3, 12.9)], start=4, end=14)
        cues = create_subtitle_cues([item])
        self.assertEqual([(5, 5.4), (8.3, 12.9)], [(cue.start, cue.end) for cue in cues])

    def test_decimal_time_grouping_and_symbols_are_preserved(self):
        text = "価格は1.5万円、集合は10:30。１．５万円、１，０００円！C++、a!=b、https://example.com?a=1、U.S."
        self.assertEqual("価格は1.5万円集合は10:30１．５万円１，０００円C++a!=bhttps://example.com?a=1U.S.", normalize_subtitle_text(text))

    def test_numbers_split_into_whisper_pieces_remain_intact(self):
        item = segment([("価格は1", 0, 1), (".", 1.5, 1.6), ("5", 2.2, 2.3), ("万円、", 2.9, 4), ("開始は10", 4.4, 5.4), (":", 5.9, 6), ("30です。", 6.6, 7.8)])
        cues = create_subtitle_cues([item])
        self.assertEqual(["価格は1.5万円", "開始は10:30です"], visible(cues))
        self.assert_lossless([item], cues)

    def test_leading_decimals_remain_intact(self):
        self.assertEqual("差は-.5倍 比率は.25", normalize_subtitle_text("差は-.5倍。 比率は.25！"))

    def test_prefix_operator_and_factorial_remain_intact(self):
        self.assertEqual("!flagと5!", normalize_subtitle_text("!flagと5!。"))

    def test_standalone_punctuation_and_closing_quotes_stay_with_speech(self):
        item = segment([("「大丈夫です", 0, 1.2), ("。", 1.2, 1.3), ("」", 1.3, 1.4), ("次です。", 1.5, 2.7)])
        cues = create_subtitle_cues([item])
        self.assertEqual(["「大丈夫です」", "次です"], visible(cues))
        self.assert_lossless([item], cues)

    def test_standalone_opening_quote_stays_with_following_speech(self):
        item = segment([("前半です。", 0, 1), ("「", 1.1, 1.2), ("大丈夫です。", 1.2, 2.5), ("」", 2.5, 2.6)])
        cues = create_subtitle_cues([item])
        self.assertEqual(["前半です", "「大丈夫です」"], visible(cues))
        self.assertEqual(1.1, cues[1].start)
        self.assert_lossless([item], cues)

    def test_word_with_internal_sentence_punctuation_is_not_given_invented_times(self):
        item = segment([("一文目です。二文目です。", 0.3, 4.2)], start=0, end=5)
        self.assertEqual(1, len(create_subtitle_cues([item])))

    def test_alignment_ignores_only_whitespace_and_preserves_raw_text(self):
        item = segment([(" 今日は、", 0.1, 1.2), (" 説明します。", 1.6, 3)], text="\n 今日 は、\t説明します。 \n")
        cues = create_subtitle_cues([item])
        self.assertEqual(["今日 は", "説明します"], visible(cues))
        self.assert_lossless([item], cues)

    def test_adjacent_segments_can_complete_a_phrase(self):
        items = [segment([("この件につい", 0, 1)]), segment([("て説明します。", 1.1, 2.4)])]
        cues = create_subtitle_cues(iter(items))
        self.assertEqual(["この件について説明します"], visible(cues))
        self.assertEqual((0, 2.4), (cues[0].start, cues[0].end))
        self.assert_lossless(items, cues)

    def test_independent_response_segments_stay_separate(self):
        items = [segment([("はい", 0, 0.2)]), segment([("説明を始めます", 0.3, 1.8)])]
        cues = create_subtitle_cues(items)
        self.assertEqual(["はい", "説明を始めます"], visible(cues))
        self.assert_lossless(items, cues)

    def test_response_prefix_does_not_strand_an_auxiliary_in_next_segment(self):
        for first, second in [("そう", "です。"), ("ありがとう", "ございます。")]:
            with self.subTest(parts=(first, second)):
                items = [segment([(first, 0, 0.2)]), segment([(second, 0.3, 1)])]
                self.assertEqual([first + second[:-1]], visible(create_subtitle_cues(items)))

    def test_segments_are_never_combined_across_long_silence(self):
        items = [segment([("確認", 0, 0.2)]), segment([("次の内容", 5, 5.5)])]
        self.assertEqual(2, len(create_subtitle_cues(items)))

    def test_custom_thresholds_are_applied(self):
        item = segment([("内容について", 0, 1), ("説明します", 1.6, 2.8)])
        self.assertEqual(2, len(split_segment_to_cues(item)))
        config = replace(SEGMENTATION_CONFIG, pause_seconds=0.7)
        self.assertEqual(1, len(split_segment_to_cues(item, config)))

    def test_exact_pause_thresholds_are_not_missed_by_float_rounding(self):
        cases = [
            segment([("はい", 0, 0.2), ("説明します", 0.7, 2)]),
            segment([("今日は、", 7, 7.1), ("説明します", 8.1, 9.5)]),
        ]
        for item in cases:
            with self.subTest(text=item.text):
                self.assertEqual(2, len(create_subtitle_cues([item])))

    def test_punctuation_only_cues_do_not_create_empty_srt_blocks(self):
        item = segment([("。", 0, 0.2)])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subtitle.srt"
            write_srt(path, [item])
            self.assertEqual("", path.read_text())

    def test_many_segments_remain_lossless_and_monotonic(self):
        rng = random.Random(13)
        items = []
        for index in range(2000):
            start = index * 8
            first = rng.uniform(0.1, 1.5)
            gap = rng.choice([0, 0.3, 0.6, 1.5])
            items.append(segment([("この件について、", start, start + first), ("詳しく確認します。", start + first + gap, start + 4)]))
        cues = create_subtitle_cues(iter(items))
        self.assert_lossless(items, cues)
        self.assertTrue(all(cue.start < cue.end for cue in cues))
        self.assertTrue(all(left.end <= right.start for left, right in zip(cues, cues[1:])))


class SubtitleFallbackTest(unittest.TestCase):
    def assert_fallback(self, item, reason):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cues = create_subtitle_cues([item])
        self.assertEqual([(item.start, item.end, item.text)], [(cue.start, cue.end, cue.text) for cue in cues])
        self.assertIn("Subtitle fallback: segment 0", output.getvalue())
        self.assertIn(reason, output.getvalue())

    def test_missing_words(self):
        for value in (None, []):
            item = segment([("原文を落とさずに保持します。次も同じです。", 0, 4)])
            item.words = value
            self.assert_fallback(item, "missing word timestamps")
        del item.words
        self.assert_fallback(item, "missing word timestamps")

    def test_invalid_word_times(self):
        for start, end in [(None, 1), (0, None), (math.nan, 1), (0, math.inf), (1, 1), (2, 1), (-1, 1), ("0", 1), (False, 1), (0.0001, 0.0002)]:
            with self.subTest(interval=(start, end)):
                item = segment([("原文です。", 0, 4)])
                item.words[0].start = start
                item.words[0].end = end
                self.assert_fallback(item, "invalid or missing time interval")

    def test_missing_word_start_or_end(self):
        for field in ("start", "end"):
            item = segment([("原文です。", 0, 4)])
            delattr(item.words[0], field)
            self.assert_fallback(item, "invalid or missing time interval")

    def test_overlap_and_reversed_word_order(self):
        for parts in [[("前半。", 0, 2), ("後半。", 1, 3)], [("前半。", 2, 3), ("後半。", 0, 1)]]:
            self.assert_fallback(segment(parts, start=0, end=4), "overlapping or out-of-order")

    def test_word_outside_segment(self):
        item = segment([("原文です。", 0, 4)], start=1, end=3)
        self.assert_fallback(item, "outside segment")

    def test_mismatched_or_incomplete_word_text(self):
        for text, reason in [("原文です。残りの文です。", "does not cover"), ("違う文です。", "does not match"), ("原文です", "does not match")]:
            self.assert_fallback(segment([("原文です。", 0, 4)], text=text), reason)

    def test_empty_or_missing_word_text(self):
        for spelling in ("", " \n", None):
            item = segment([("原文です。", 0, 4)])
            item.words[0].word = spelling
            self.assert_fallback(item, "empty or missing text")

    def test_fallback_does_not_affect_or_merge_valid_neighbours(self):
        items = [segment([("前半です。", 0.1, 1.2)], start=0, end=2), SimpleNamespace(text="欠損です。内容は残します。", start=2, end=3), segment([("後半です。", 3.5, 4.8)], start=3, end=5)]
        with contextlib.redirect_stdout(io.StringIO()):
            cues = create_subtitle_cues(items)
        self.assertEqual([(0.1, 1.2), (2, 3), (3.5, 4.8)], [(cue.start, cue.end) for cue in cues])
        self.assertEqual("".join(item.text for item in items), "".join(cue.text for cue in cues))

    def test_invalid_segment_time_cannot_be_used_as_fallback(self):
        for start, end in [(math.nan, 1), (0, math.inf), (-1, 1), (2, 1), (0, 0)]:
            with self.subTest(interval=(start, end)), self.assertRaisesRegex(ValueError, "segment 0"):
                create_subtitle_cues([SimpleNamespace(start=start, end=end, text="原文")])


class SubtitleOutputTest(unittest.TestCase):
    def test_srt_vtt_share_text_and_word_timestamps(self):
        item = segment([("価格は1.5万円。", 0.125, 1.875), ("集合は10:30です。", 3.25, 5.125)], start=0, end=6)
        with tempfile.TemporaryDirectory() as directory:
            srt = Path(directory) / "日本語 字幕.srt"
            vtt = Path(directory) / "日本語 字幕.vtt"
            write_srt(srt, iter([item]))
            write_vtt(vtt, iter([item]))
            srt_blocks = srt.read_text().strip().split("\n\n")
            vtt_blocks = vtt.read_text().strip().split("\n\n")
        self.assertEqual("WEBVTT", vtt_blocks.pop(0))
        self.assertEqual(2, len(srt_blocks))
        expected_times = [("00:00:00,125", "00:00:01,875"), ("00:00:03,250", "00:00:05,125")]
        for index, (srt_block, vtt_block) in enumerate(zip(srt_blocks, vtt_blocks)):
            lines = srt_block.splitlines()
            self.assertEqual(str(index + 1), lines[0])
            self.assertEqual(" --> ".join(expected_times[index]), lines[1])
            self.assertEqual([lines[1].replace(",", "."), lines[2]], vtt_block.splitlines())

    def test_txt_preserves_original_segment_text(self):
        items = [SimpleNamespace(text=" \n価格は1.5万円、10:30です。  "), SimpleNamespace(text="次です！")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subtitle.txt"
            write_txt(path, iter(items))
            self.assertEqual("".join(item.text + "\n" for item in items), path.read_text())

    def test_empty_outputs_are_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            for writer, expected in [(write_srt, ""), (write_vtt, "WEBVTT\n\n"), (write_txt, "")]:
                path = Path(directory) / writer.__name__
                writer(path, [])
                self.assertEqual(expected, path.read_text())

    def test_fallback_is_the_same_in_srt_and_vtt(self):
        item = SimpleNamespace(start=1.25, end=8.75, text="単語時刻がありません。本文は残します。")
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            for writer, formatter in [(write_srt, format_srt_time), (write_vtt, format_vtt_time)]:
                path = Path(directory) / writer.__name__
                writer(path, [item])
                text = path.read_text()
                self.assertEqual(1, text.count(" --> "))
                self.assertIn(f"{formatter(item.start)} --> {formatter(item.end)}", text)
                self.assertIn("単語時刻がありません本文は残します", text)

    def test_time_rounding_and_hour_rollover(self):
        self.assertEqual("00:00:01,001", format_srt_time(1.001))
        self.assertEqual("01:00:00.000", format_vtt_time(3599.9999))
        self.assertEqual("25:00:00,125", format_srt_time(90000.125))

    def test_overlapping_segments_are_rejected_before_overwriting_output(self):
        items = [segment([("前半です。", 0, 2)]), segment([("後半です。", 1, 3)])]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.srt"
            path.write_text("既存のファイル")
            with self.assertRaisesRegex(ValueError, "segment 1"):
                write_srt(path, items)
            self.assertEqual("既存のファイル", path.read_text())

    def test_cli_arguments_are_unchanged(self):
        args = create_parser().parse_args(["--input", "input.wav", "--output", "out", "--title", "字幕"])
        self.assertEqual(("small", "srt", "ja"), (args.model, args.format, args.language))

    def test_cli_enables_word_timestamps_for_all_output_formats(self):
        for format_name in ("srt", "vtt", "txt"):
            with self.subTest(format=format_name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                audio = path / "テスト 音声.wav"
                audio.touch()
                output = path / "字幕 出力"
                module = SimpleNamespace(WhisperModel=MagicMock())
                model = module.WhisperModel.return_value
                item = segment([("テストです。", 0.2, 1.2)], start=0, end=2)
                model.transcribe.return_value = (iter([item]), SimpleNamespace(language="ja"))
                arguments = ["subtitle.py", "--input", str(audio), "--output", str(output), "--title", "日本語 字幕", "--model", "small", "--format", format_name, "--language", "ja"]
                with patch.dict(sys.modules, {"faster_whisper": module}), patch.object(sys, "argv", arguments), contextlib.redirect_stdout(io.StringIO()):
                    main()
                module.WhisperModel.assert_called_once_with("small", device="cpu", compute_type="int8")
                model.transcribe.assert_called_once_with(str(audio), language="ja", word_timestamps=True)
                self.assertTrue((output / f"日本語 字幕.{format_name}").exists())


if __name__ == "__main__":
    unittest.main()
