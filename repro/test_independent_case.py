"""Reproducible evaluation of a fresh public-record field projection using unmodified V16.
The source projection is reconstructed from fields read from the GitHub REST API on 2026-10-23.
No new GitHub bug or historical authorization claim is made.
"""
from pathlib import Path
import sys,json,hashlib,copy,collections,unittest
TOOL=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(TOOL/'src'))
from github_import import import_github_bundle
from verdictlens_core import verify_structure
F=TOOL/'evidence/cli_cli_14805_GITHUB_FIELD_PROJECTION.json'
class TestIndependentCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=json.loads(F.read_text());cls.report=import_github_bundle(cls.bundle)['reports'][0]
    def test_sha_roles(self):
        self.assertEqual([s['role'] for s in self.report['subjects']],['HEAD','MERGED_RESULT'])
        self.assertEqual(self.report['subjects'][0]['sha'],'17ac598e6afc43bb6206f074b05de9d63563a42f')
        self.assertEqual(self.report['subjects'][1]['sha'],'4f2cfe92e3499f8581bf39db77e0a1431fa7b55c')
    def test_39_observations_and_28_contexts(self):
        self.assertEqual(self.report['verified_observations'],39)
        self.assertEqual(self.report['observed_contexts'],28)
        self.assertEqual(self.report['contrasting_contexts'],0)
    def test_partition(self):
        x=collections.Counter(r['finding'] for r in self.report['rows'])
        self.assertEqual(x,{'SAME_RECORDED_RESULT':10,'BOUNDED_EVIDENCE_GAP':17,'AMBIGUOUS_RUNS':1})
        self.assertEqual(sum(c['state']=='NOT_OBSERVED' for r in self.report['rows'] for c in r['cells']),18)
    def test_dispatch_ambiguity_without_discarding_sources(self):
        row=next(r for r in self.report['rows'] if r['context']=='dispatch')
        self.assertEqual(row['finding'],'AMBIGUOUS_RUNS')
        self.assertEqual(row['cells'][1]['state'],'AMBIGUOUS')
        self.assertEqual([r['id'] for r in row['cells'][1]['candidate_check_runs']],[120647645284,120637913536])
        self.assertIsNone(row['minimal_witness'])
    def test_shared_build_check_trace(self):
        row=next(r for r in self.report['rows'] if r['context']=='build (windows-latest)')
        self.assertEqual([c['check_id'] for c in row['cells']],[120623600453,120630987645])
        self.assertTrue(all(c['state']=='SATISFIED' for c in row['cells']))
    def test_bad_sha_rejected(self):
        d=copy.deepcopy(self.bundle)
        d['subjects'][1]['check_runs']['check_runs'][0]['head_sha']=self.bundle['subjects'][0]['sha']
        with self.assertRaisesRegex(ValueError,'disagrees'):import_github_bundle(d)
    def test_truncated_response_rejected(self):
        d=copy.deepcopy(self.bundle)
        d['subjects'][1]['check_runs']['check_runs'].pop()
        with self.assertRaisesRegex(ValueError,'incomplete API response'):import_github_bundle(d)
    def test_replay_determinism(self):
        a=import_github_bundle(self.bundle);b=import_github_bundle(self.bundle)
        self.assertEqual(a,b)
if __name__=='__main__':unittest.main(verbosity=2)
