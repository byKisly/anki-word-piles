import importlib.util
import pathlib
import sys
import unittest
from datetime import datetime

root = pathlib.Path(__file__).resolve().parents[1]
path = root / 'core.py'
if not path.exists():
    path = root / 'word_piles/core.py'
spec = importlib.util.spec_from_file_location('word_piles_core', path)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def timestamp(day, hour=12):
    return int(datetime(2026, 11, day, hour).timestamp() * 1000)


def events(day, ratings, cid=100, nid=200, hour=12, kind=0):
    return [(timestamp(day, hour) + i, cid, nid, rating, kind) for i, rating in enumerate(ratings)]


class RulesTest(unittest.TestCase):
    def state(self, rows, threshold=10):
        return core.analyze(rows, 6, threshold)[200]

    def test_tenth_again_enters_and_nine_does_not(self):
        self.assertFalse(self.state(events(1, [1]*9)).active)
        self.assertTrue(self.state(events(1, [1]*10)).active)

    def test_success_same_day_never_clears(self):
        self.assertTrue(self.state(events(1, [1]*10 + [2, 3, 4]*10)).active)

    def test_directions_aggregate(self):
        rows = events(1, [1]*7) + events(1, [1]*3, cid=101)
        h = self.state(rows)
        self.assertTrue(h.active)
        self.assertEqual(len(h.days['2026-11-01'].directions), 2)

    def test_no_practice_keeps_state(self):
        rows = events(1, [1]*10) + events(5, [3], nid=201)
        self.assertTrue(self.state(rows).active)

    def test_one_passing_answer_next_studied_day_clears(self):
        for rating in (2, 3, 4):
            self.assertFalse(self.state(events(1, [1]*10) + events(5, [rating])).active)

    def test_later_again_reinstates_even_below_entry_threshold(self):
        base = events(1, [1]*10)
        self.assertFalse(self.state(base + events(2, [3])).active)
        self.assertTrue(self.state(base + events(2, [3, 1])).active)

    def test_reenters_after_recovery(self):
        rows = events(1, [1]*10) + events(2, [3]) + events(3, [1]*10)
        h = self.state(rows)
        self.assertTrue(h.active)
        self.assertEqual(h.entered, '2026-11-03')

    def test_rollover_at_six(self):
        self.assertEqual(core.study_day(timestamp(2, 5), 6), '2026-11-01')
        self.assertEqual(core.study_day(timestamp(2, 6), 6), '2026-11-02')
        self.assertTrue(self.state(events(1, [1]*7, hour=23) + events(2, [1]*3, hour=5)).active)

    def test_non_answer_events_ignored(self):
        rows = events(1, [1]*9) + events(1, [1]*20, kind=4) + events(1, [1]*20, kind=5)
        self.assertFalse(self.state(rows).active)

    def test_undo_recomputed_without_extra_state(self):
        rows = events(1, [1]*10)
        self.assertTrue(self.state(rows).active)
        self.assertFalse(self.state(rows[:-1]).active)
        self.assertTrue(self.state(rows + events(2, [3])[:-1]).active)

    def test_future_entries_excluded(self):
        rows = events(1, [1]*10) + events(2, [3])
        result = core.analyze(rows, 6, now_ms=timestamp(1, 23))
        self.assertTrue(result[200].active)

    def test_out_of_order_events_and_notes_independent(self):
        rows = events(2, [3]) + events(1, [1]*10) + events(3, [1]*12, nid=201)
        result = core.analyze(rows, 6)
        self.assertFalse(result[200].active)
        self.assertTrue(result[201].active)

    def test_copies_explicit_content_not_html_or_ids(self):
        row = dict(word='maintain', meaning='поддерживать', detail='Reverse: 1=10, 3=2', nid=123)
        self.assertEqual(core.export_text([row], 'meaning'), 'maintain — поддерживать')
        self.assertEqual(core.export_text([row], 'words'), 'maintain')
        text = core.export_text([row], 'ai', difficult=True)
        self.assertIn('maintain — поддерживать', text)
        self.assertNotIn('123', text)


if __name__ == '__main__':
    unittest.main()
