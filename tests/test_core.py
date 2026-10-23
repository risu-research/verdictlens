import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from verdictlens_core import load_audit,verify_structure,case_by_pr,check_by_name,check_summary,cases_summary,witness,write_json,safe_github_url,BUNDLED_SHA256
from v9_audit import audit

class CoreTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.audit=load_audit(ROOT/'data/v9_audit.json',bundled=True)
 def test_v9_engine_reproduces_bundled_record(self):
  original=json.loads((ROOT/'data/v8_input.json').read_text())
  self.assertEqual(audit(original),self.audit)
 def test_exact_baseline_counts(self):
  self.assertEqual(self.audit['global_findings'],{'cases':3,'observations':33,'contrasting_contexts':3,'repositories':2})
  self.assertEqual([(c['pr'],len(c['rows'])) for c in self.audit['reports']],[(7016,3),(46333,5),(46412,5)])
 def test_source_file_sha_matches(self):
  import hashlib
  self.assertEqual(hashlib.sha256((ROOT/'data/v9_audit.json').read_bytes()).hexdigest(),BUNDLED_SHA256)
 def test_original_failures_are_not_redistributed(self):
  c=case_by_pr(self.audit,7016);r=check_by_name(c,'Required Checks');self.assertEqual([x['state'] for x in r['cells']],['SATISFIED','FAILED','SATISFIED'])
 def test_no_record_is_distinct(self):
  c=case_by_pr(self.audit,7016);r=next(x for x in c['rows'] if 'macOS' in x['context']);self.assertEqual(r['cells'][0]['state'],'NOT_OBSERVED')
  self.assertEqual(check_summary(c,r)['outcomes'][0]['state'],'NO RECORD')
 def test_witness_preserves_real_check_ids(self):
  c=case_by_pr(self.audit,7016);r=check_by_name(c,'Required Checks');w=witness(c,r)
  self.assertEqual(w['minimal_witness']['check_ids'],[119782747033,120289414102]);self.assertEqual(w['scope']['historical_enforcement'],'UNVERIFIED')
 def test_no_witness_for_homogeneous_row(self):
  c=case_by_pr(self.audit,46333);r=check_by_name(c,'assets')
  with self.assertRaises(ValueError):witness(c,r)
 def test_case_summary(self):
  x=cases_summary(self.audit);self.assertEqual([z['contrasts'] for z in x],[2,1,0])
 def test_reject_cross_commit_swap(self):
  d=json.loads(json.dumps(self.audit));d['reports'][0]['rows'][0]['cells'][0]['sha']='0'*40
  with self.assertRaises(ValueError):verify_structure(d)
 def test_reject_unknown_state(self):
  d=json.loads(json.dumps(self.audit));d['reports'][0]['rows'][0]['cells'][0]['state']='INVENTED'
  with self.assertRaises(ValueError):verify_structure(d)
 def test_imports_are_structural_not_authenticated(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'external.json'
   write_json(p,self.audit)
   self.assertEqual(load_audit(p),self.audit)
 def test_source_links_allow_only_github_https(self):
  self.assertEqual(safe_github_url('https://github.com/github/docs/pull/46333'),'https://github.com/github/docs/pull/46333')
  self.assertIsNone(safe_github_url('javascript:alert(1)'))
  self.assertIsNone(safe_github_url('https://github.com.evil.net/x'))
  self.assertIsNone(safe_github_url('https://foo:bar@github.com/x'))
 def test_cli_json_inspect(self):
  import subprocess
  q=subprocess.run([sys.executable,str(ROOT/'verdictlens_cli.py'),'inspect','--pr','7016','--json'],check=True,capture_output=True,text=True)
  self.assertEqual(len(json.loads(q.stdout)['checks']),3)
 def test_cli_verify(self):
  import subprocess
  q=subprocess.run([sys.executable,str(ROOT/'verdictlens_cli.py'),'verify'],check=True,capture_output=True,text=True)
  self.assertIn('bundled SHA-256 matches',q.stdout)
 def test_export_exact_json(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'exp.json';write_json(p,self.audit)
   self.assertEqual(json.loads(p.read_text()),self.audit)
 def test_html_code_is_offline_plain(self):
  html=(ROOT/'VerdictLens_Offline.html').read_text()
  for b in ('fetch(', '<script src=', 'fonts.googleapis','class="card"','box-shadow:'):
   self.assertNotIn(b,html)
  self.assertIn('120289414102',html)

if __name__=='__main__':unittest.main()
