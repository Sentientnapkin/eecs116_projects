import json
from pathlib import Path
import tempfile
import unittest
from .ledger import Claim, write_spec, utc_now
from .report import distribution, paired_scene_bootstrap, build_report
from .leaderboard import eligibility, render
from .perflight import consolidate


def row(ep, value, scene='a'):
    return {'episode': ep, 'ate_full': value, 'guest': 'g', 'scene': scene, 'group': 'clean', 'catalog': 'procthor', 'start_type': 'static', 'source_pool': 'synthetic', 'draw_weight': 1, 'completed': True}


class CampaignTests(unittest.TestCase):
    def test_failure_is_counted(self):
        rows = [row('a', 1), {**row('b', 9), 'completed': False, 'filled_full': 20}]
        d = distribution(rows, 100)
        self.assertEqual(d['mean_unaligned_ate_m'], 5)
        self.assertEqual(d['filled_flight_count'], 1)
        self.assertEqual(d['failed_flight_count'], 1)

    def test_weights_and_scene_pair(self):
        a = [row('a', 1), {**row('b', 4), 'draw_weight': 3}]
        self.assertEqual(distribution(a, 100)['draw_weighted_mean_m'], 3.25)
        b = [{**r, 'ate_full': r['ate_full']+2} for r in a]
        result = paired_scene_bootstrap(a, b, 100)
        self.assertEqual(result['scene_bootstrap90_interval_m'], [-2, -2])
        with self.assertRaises(ValueError): paired_scene_bootstrap(a, b[:1])

    def test_no_silent_missing_score(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); (root/'g').mkdir(); (root/'meta').mkdir()
            (root/'meta'/'ep.json').write_text(json.dumps({'scene': 'a', 'group': 'clean', 'catalog': 'procthor'}))
            (root/'g'/'scores.json').write_text(json.dumps({'guest': {'name': 'g', 'sha256': 'abc', 'archives': ['ep.zip']}, 'rows': []}))
            with self.assertRaisesRegex(ValueError, 'unscored flight'): consolidate(root, root/'meta')

    def test_claim_exclusion_and_stale_reporting(self):
        with tempfile.TemporaryDirectory() as td:
            with Claim(td, 'job') as claim:
                with self.assertRaises(FileExistsError): Claim(td, 'job').acquire()
                self.assertFalse(claim.inspect()['stale'])
                claim.heartbeat()
            with Claim(td, 'job'): pass

    def test_spec_content_addressing(self):
        with tempfile.TemporaryDirectory() as td:
            s = {'arm': 'test', 'parent': 'abc', 'hypothesis': 'test', 'build': {}, 'train': {},
                 'eval': {'workers': 160}, 'gate': {'metric': 'mean_unaligned_ate_m', 'declared_at': utc_now()},
                 'preflight': [], 'resources': {}, 'overfit': {}}
            path = write_spec(td, s)
            self.assertEqual(path, write_spec(td, s))
            self.assertNotEqual(path, write_spec(td, {**s, 'hypothesis': 'changed'}))

    def test_final_rows_need_provenance_and_three_seeds(self):
        r = {'mean_unaligned_ate_m': 1., 'median_unaligned_ate_m': .5, 'status': 'final', 'preflight_pass': True, 'metric': 'mean_unaligned_ate_m', 'learned': True,
             'evaluated_seeds': [217], 'train_excludes_reserved': True}
        self.assertIn('three_seeds_required', eligibility(r))
        self.assertIn('declaration_provenance_missing', eligibility(r))
        r.update({'evaluated_seeds': [217, 218, 219], 'declared_at': '2026-01-01T00:00:00Z', 'first_score_at': '2026-01-02T00:00:00Z'})
        self.assertEqual(eligibility(r), [])

    def test_tags_and_duplicates(self):
        with self.assertRaises(ValueError): build_report([{'guest': 'g', 'ate_full': 1}])
        with self.assertRaises(ValueError): build_report([row('a', 1), row('a', 2)])


if __name__ == '__main__': unittest.main()
