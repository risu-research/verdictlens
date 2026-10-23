import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from github_import import import_github_bundle,load_github_bundle
from verdictlens_core import verify_structure,witness

class GithubImportTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.bundle=json.loads((ROOT/'examples/EXAMPLE_SYNTHETIC_GITHUB_CHECK_RUNS.json').read_text())
 def test_accept_official_api_list_shape(self):
  d=import_github_bundle(self.bundle);verify_structure(d)
  c=d['reports'][0]
  self.assertEqual([s['role'] for s in c['subjects']],['HEAD','MERGE_GROUP'])
  self.assertEqual(c['verified_observations'],6)
  self.assertEqual([(r['context'],r['finding']) for r in c['rows']],
   [('deploy','BOUNDED_EVIDENCE_GAP'),('integration','BOUNDED_EVIDENCE_GAP'),('lint','SAME_RECORDED_RESULT'),('unit tests','DIFFERENT_RECORDED_RESULT')])
  r=c['rows'][-1];self.assertEqual([x['state'] for x in r['cells']],['SATISFIED','FAILED'])
  w=witness(c,r,imported=True)
  self.assertEqual(w['minimal_witness']['check_ids'],[1001,2001]);self.assertTrue(w['imported_unverified'])
 def test_neutral_and_missing_are_explicit(self):
  c=import_github_bundle(self.bundle)['reports'][0]
  lookup={r['context']:r for r in c['rows']}
  self.assertEqual([x['state'] for x in lookup['lint']['cells']],['SATISFIED','SATISFIED'])
  self.assertEqual(lookup['lint']['cells'][1]['conclusion'],'neutral')
  self.assertEqual([x['state'] for x in lookup['integration']['cells']],['NOT_OBSERVED','INCONCLUSIVE'])
  self.assertEqual([x['state'] for x in lookup['deploy']['cells']],['PENDING','NOT_OBSERVED'])
 def test_refuse_cross_sha_mix(self):
  x=copy.deepcopy(self.bundle);x['subjects'][1]['check_runs']['check_runs'][0]['head_sha']='a'*40
  with self.assertRaisesRegex(ValueError,'head_sha disagrees'):import_github_bundle(x)
 def test_refuse_incomplete_page(self):
  x=copy.deepcopy(self.bundle);x['subjects'][1]['check_runs']['total_count']=4
  with self.assertRaisesRegex(ValueError,'incomplete API response'):import_github_bundle(x)
 def test_refuse_duplicate_id(self):
  x=copy.deepcopy(self.bundle);x['subjects'][0]['check_runs']['check_runs'][1]['id']=1001
  with self.assertRaisesRegex(ValueError,'duplicate Check Run id'):import_github_bundle(x)
 def test_ambiguity_does_not_make_fake_witness(self):
  x=copy.deepcopy(self.bundle)
  new=copy.deepcopy(x['subjects'][1]['check_runs']['check_runs'][0]);new['id']=2011
  x['subjects'][1]['check_runs']['check_runs'].append(new)
  x['subjects'][1]['check_runs']['total_count']=4
  c=import_github_bundle(x)['reports'][0];r=next(r for r in c['rows'] if r['context']=='unit tests')
  self.assertEqual(r['cells'][1]['state'],'AMBIGUOUS');self.assertIsNone(r['minimal_witness'])
  self.assertEqual(len(r['cells'][1]['candidate_check_runs']),2)
 def test_different_apps_same_check_not_conflated(self):
  x=copy.deepcopy(self.bundle)
  for s in x['subjects']:
   check=s['check_runs']['check_runs'][0]
   new=copy.deepcopy(check);new['id']+=99999;new['app']['id']=998
   s['check_runs']['check_runs'].append(new);s['check_runs']['total_count']+=1
  c=import_github_bundle(x)['reports'][0]
  self.assertTrue(any(r['context']=='unit tests [App 998]' for r in c['rows']))
  self.assertTrue(any(r['context']=='unit tests [App 901]' for r in c['rows']))
 def test_bad_url_rejected(self):
  x=copy.deepcopy(self.bundle);x['subjects'][0]['check_runs']['check_runs'][0]['html_url']='https://github.com.attacker.invalid/pull/1'
  with self.assertRaisesRegex(ValueError,'invalid/non-GitHub'):import_github_bundle(x)
 def test_completed_must_have_supported_conclusion(self):
  x=copy.deepcopy(self.bundle);x['subjects'][0]['check_runs']['check_runs'][0]['conclusion']='unknown'
  with self.assertRaisesRegex(ValueError,'unsupported completed conclusion'):import_github_bundle(x)
 def test_pack_and_convert_cli(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d); b=d/'bundle.json';out=d/'audit.json'
   head=d/'head.json';queue=d/'queue.json'
   subs=self.bundle['subjects']
   head.write_text(json.dumps(subs[0]['check_runs']));queue.write_text(json.dumps(subs[1]['check_runs']))
   cmd=[sys.executable,str(ROOT/'verdictlens_cli.py'),'pack-check-runs','--repo','sample-lab/sample-project','--pr','12',
        '--head','a'*40+'='+str(head),'--queue','b'*40+'='+str(queue),'--out',str(b)]
   subprocess.run(cmd,check=True,capture_output=True,text=True)
   subprocess.run([sys.executable,str(ROOT/'verdictlens_cli.py'),'import-check-runs','--input',str(b),'--out',str(out)],check=True,capture_output=True,text=True)
   self.assertEqual(json.loads(out.read_text())['reports'][0]['rows'][-1]['finding'],'DIFFERENT_RECORDED_RESULT')
   q=subprocess.run([sys.executable,str(ROOT/'verdictlens_cli.py'),'--audit',str(out),'inspect','--pr','12','--json'],check=True,capture_output=True,text=True)
   self.assertEqual(len(json.loads(q.stdout)['checks']),4)
 def test_bundle_multicase(self):
  x={'schema':'verdictlens-github-check-runs-v1','cases':[self.bundle,self.bundle]}
  self.assertEqual(len(import_github_bundle(x)['reports']),2)
 def test_file_limit(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'large.json';p.write_bytes(b' '* (4*1024*1024+1))
   with self.assertRaisesRegex(ValueError,'exceeds 4 MB'):load_github_bundle(p)
