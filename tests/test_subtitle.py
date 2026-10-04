import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from subtitle import create_parser, format_srt_time, format_vtt_time, main, write_srt, write_txt, write_vtt


class SubtitleOutputTest(unittest.TestCase):
    def test_srt_and_vtt_preserve_segment_text_and_times(self):
        segments = [
            SimpleNamespace(
                start=0.125, end=6.875,
                text=" 価格は1.5万円。集合は10:30です！ ",
                words=[SimpleNamespace(word="価格", start=1.2, end=1.5)],
            ),
            SimpleNamespace(start=8.25, end=10.125, text="次の説明です。\n改行も残します。"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for writer, formatter, header in [
                (write_srt, format_srt_time, ""),
                (write_vtt, format_vtt_time, "WEBVTT\n\n"),
            ]:
                with self.subTest(format=writer.__name__):
                    path = Path(directory) / "日本語 字幕"
                    writer(path, iter(segments))
                    expected = header
                    for index, segment in enumerate(segments, start=1):
                        if writer is write_srt:
                            expected += f"{index}\n"
                        expected += f"{formatter(segment.start)} --> {formatter(segment.end)}\n"
                        expected += segment.text + "\n\n"
                    self.assertEqual(expected, path.read_text(encoding="utf-8"))

    def test_long_segment_is_not_split_or_normalized(self):
        text = "この長い動画の内容について説明します。文字数や句読点による追加の分割は行いません。"
        self.assertGreater(len(text), 20)
        segment = SimpleNamespace(start=0, end=15, text=text)
        with tempfile.TemporaryDirectory() as directory:
            for writer in (write_srt, write_vtt):
                with self.subTest(format=writer.__name__):
                    path = Path(directory) / writer.__name__
                    writer(path, [segment])
                    output = path.read_text(encoding="utf-8")
                    self.assertEqual(1, output.count(" --> "))
                    self.assertIn(text + "\n\n", output)

    def test_word_metadata_does_not_affect_output(self):
        variants = [None, [], [SimpleNamespace(word="別の本文", start=9, end=1)]]
        with tempfile.TemporaryDirectory() as directory:
            for words in variants:
                with self.subTest(words=words):
                    segment = SimpleNamespace(start=1.25, end=8.75, text="元の本文。", words=words)
                    path = Path(directory) / "subtitle.srt"
                    logs = io.StringIO()
                    with contextlib.redirect_stdout(logs):
                        write_srt(path, [segment])
                    self.assertEqual("1\n00:00:01,250 --> 00:00:08,750\n元の本文。\n\n", path.read_text())
                    self.assertEqual("", logs.getvalue())

    def test_txt_preserves_original_text(self):
        segments = [SimpleNamespace(text=" \n価格は1.5万円、10:30です。  "), SimpleNamespace(text="次です！")]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subtitle.txt"
            write_txt(path, iter(segments))
            self.assertEqual("".join(segment.text + "\n" for segment in segments), path.read_text())

    def test_empty_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            for writer, expected in [(write_srt, ""), (write_vtt, "WEBVTT\n\n"), (write_txt, "")]:
                with self.subTest(format=writer.__name__):
                    path = Path(directory) / writer.__name__
                    writer(path, [])
                    self.assertEqual(expected, path.read_text())

    def test_time_rounding_and_hour_rollover(self):
        self.assertEqual("00:00:01,001", format_srt_time(1.001))
        self.assertEqual("01:00:00.000", format_vtt_time(3599.9999))
        self.assertEqual("25:00:00,125", format_srt_time(90000.125))


class SubtitleCliTest(unittest.TestCase):
    def test_defaults_keep_existing_options_and_disable_word_timestamps(self):
        args = create_parser().parse_args(["--input", "input.wav", "--output", "out", "--title", "字幕"])
        self.assertEqual(("small", "srt", "ja"), (args.model, args.format, args.language))
        self.assertIs(args.word_timestamps, False)

    def test_word_timestamps_flag_enables_option(self):
        args = create_parser().parse_args([
            "--input", "input.wav", "--output", "out", "--title", "字幕", "--word-timestamps",
        ])
        self.assertIs(args.word_timestamps, True)

    def test_word_timestamps_flag_does_not_treat_false_string_as_true(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            create_parser().parse_args([
                "--input", "input.wav", "--output", "out", "--title", "字幕", "--word-timestamps", "false",
            ])
        self.assertEqual(2, error.exception.code)

    def test_cli_passes_selected_word_timestamps_to_model_in_all_formats(self):
        for format_name in ("srt", "vtt", "txt"):
            for enabled in (False, True):
                with self.subTest(format=format_name, enabled=enabled), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory)
                    audio = path / "テスト 音声.wav"
                    audio.touch()
                    output = path / "字幕 出力"
                    module = SimpleNamespace(WhisperModel=MagicMock())
                    model = module.WhisperModel.return_value
                    segment = SimpleNamespace(start=0.125, end=2.5, text=" テストです。 ")
                    model.transcribe.return_value = (iter([segment]), SimpleNamespace(language="ja"))
                    arguments = [
                        "subtitle.py", "--input", str(audio), "--output", str(output),
                        "--title", "日本語 字幕", "--model", "small", "--format", format_name, "--language", "ja",
                    ]
                    if enabled:
                        arguments.append("--word-timestamps")
                    with patch.dict(sys.modules, {"faster_whisper": module}), patch.object(sys, "argv", arguments), contextlib.redirect_stdout(io.StringIO()):
                        main()
                    module.WhisperModel.assert_called_once_with("small", device="cpu", compute_type="int8")
                    model.transcribe.assert_called_once_with(str(audio), language="ja", word_timestamps=enabled)
                    actual = (output / f"日本語 字幕.{format_name}").read_text(encoding="utf-8")
                    expected = {
                        "srt": "1\n00:00:00,125 --> 00:00:02,500\n テストです。 \n\n",
                        "vtt": "WEBVTT\n\n00:00:00.125 --> 00:00:02.500\n テストです。 \n\n",
                        "txt": " テストです。 \n",
                    }[format_name]
                    self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
