import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from summarize import collapse_repeats, split_lines, summarize_batch, LengthLimitError


class FakeLLM:
    """Raises LengthLimitError for batches with more than `max_lines` lines."""
    def __init__(self, max_lines):
        self.max_lines = max_lines
        self.calls = []

    def tokens(self, text):
        return len(text) // 4

    def summarize(self, text):
        lines = [l for l in text.splitlines() if l.startswith('[R')]
        self.calls.append(len(lines))
        if len(lines) > self.max_lines:
            raise LengthLimitError('length')
        return {'lines': lines}


def batch(n):
    return ''.join(f'[R{i}] [00:00:{i:02}] 참석자1: ' + '회의 내용 ' * 60 + '\n' for i in range(n))


class CollapseRepeatsTest(unittest.TestCase):
    def test_collapses_hallucinated_loops(self):
        self.assertEqual(collapse_repeats('안전과 안전과 안전과 안전과 확인'), '안전과 [반복] 확인')
        self.assertEqual(collapse_repeats('개발투를 통합 개발투를 통합 개발투를 통합 끝'), '개발투를 통합 [반복] 끝')

    def test_keeps_normal_speech_and_numbers(self):
        for text in ('네 네 좋아요', '그래서 그래서 했다', '10000000 원', '하하하하하'):
            self.assertEqual(collapse_repeats(text), text)


class SummarizeBatchTest(unittest.TestCase):
    def test_split_lines_keeps_every_line(self):
        a, b = split_lines(batch(5))
        self.assertEqual(a + b, batch(5))
        self.assertTrue(a.endswith('\n'))

    def test_length_limit_halves_and_keeps_order(self):
        llm = FakeLLM(max_lines=3)
        results = summarize_batch(llm, '', batch(10))
        lines = [l for r in results for l in r['lines']]
        self.assertEqual(lines, [l for l in batch(10).splitlines()])
        self.assertEqual(llm.calls[0], 10)

    def test_small_batch_reraises(self):
        llm = FakeLLM(max_lines=0)
        with self.assertRaises(LengthLimitError):
            summarize_batch(llm, '', batch(1))


if __name__ == '__main__':
    unittest.main()
