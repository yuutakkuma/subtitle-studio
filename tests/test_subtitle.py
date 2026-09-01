import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from subtitle import (
    MAX_SUBTITLE_CHARACTERS,
    create_subtitle_cues,
    split_subtitle_text,
    write_srt,
)


class SubtitleFormattingTest(unittest.TestCase):
    def test_splits_text_into_single_line_chunks_of_at_most_20_characters(self):
        text = "あ" * 45

        chunks = split_subtitle_text(text)

        self.assertEqual([20, 20, 5], [len(chunk) for chunk in chunks])
        self.assertTrue(all("\n" not in chunk for chunk in chunks))

    def test_removes_japanese_and_english_punctuation(self):
        chunks = split_subtitle_text("あ、い。う！え？ a,b.c!")

        self.assertEqual(["あいうえ abc"], chunks)

    def test_distributes_segment_timing_between_split_cues(self):
        segment = SimpleNamespace(start=2.0, end=11.0, text="あ" * 45)

        cues = create_subtitle_cues([segment])

        self.assertEqual(3, len(cues))
        self.assertEqual(2.0, cues[0].start)
        self.assertEqual(11.0, cues[-1].end)
        self.assertEqual(cues[0].end, cues[1].start)
        self.assertEqual(cues[1].end, cues[2].start)
        self.assertTrue(
            all(len(cue.text) <= MAX_SUBTITLE_CHARACTERS for cue in cues)
        )

    def test_srt_output_contains_one_text_line_per_cue(self):
        segment = SimpleNamespace(start=0.0, end=4.2, text="あ" * 21)

        with tempfile.TemporaryDirectory() as directory:
            output_file = Path(directory) / "subtitle.srt"
            write_srt(output_file, [segment])
            output = output_file.read_text(encoding="utf-8")

        blocks = output.strip().split("\n\n")
        self.assertEqual(2, len(blocks))

        for block in blocks:
            lines = block.splitlines()
            self.assertEqual(3, len(lines))
            self.assertLessEqual(len(lines[2]), MAX_SUBTITLE_CHARACTERS)


if __name__ == "__main__":
    unittest.main()
