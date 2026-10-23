#!/usr/bin/env python3
"""Offline release integrity, independent-case replay, and executable test verification."""
from pathlib import Path
import hashlib, sys, json, tempfile, subprocess, collections
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from github_import import import_github_bundle
from verdictlens_core import witness,case_by_pr,check_by_name,load_audit

def integrity():
    rows=[s for s in (ROOT/'SHA256SUMS.txt').read_text().splitlines() if s.strip()]
    count=0
    for row in rows:
        h,rel=row.split('  ',1)
        path=ROOT/rel
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=h:
            raise AssertionError('Manifest mismatch or missing file: '+rel)
        count+=1
    print(f'OK: release SHA-256 integrity ({count} files)')
def main():
    integrity()
    bundle=json.loads((ROOT/'evidence/cli_cli_14805_GITHUB_FIELD_PROJECTION.json').read_text())
    expected=json.loads((ROOT/'evidence/cli_cli_14805_V16_AUDIT.json').read_text())
    audit=import_github_bundle(bundle)
    if audit!=expected:raise AssertionError('Independent import differs from frozen expected audit')
    c=case_by_pr(audit,14805)
    assert (len(c['rows']),c['verified_observations'],c['contrasting_contexts'])==(28,39,0)
    assert collections.Counter(row['finding'] for row in c['rows'])=={'SAME_RECORDED_RESULT':10,'BOUNDED_EVIDENCE_GAP':17,'AMBIGUOUS_RUNS':1}
    duplicate=check_by_name(c,'dispatch')
    assert [run['id'] for run in duplicate['cells'][1]['candidate_check_runs']]==[120647645284,120637913536]
    assert duplicate['minimal_witness'] is None
    print('OK: cli/cli #14805 exact replay (28 checks / 39 runs / one ambiguous context)')
    baseline=load_audit(str(ROOT/'data/v9_audit.json'),bundled=True)
    original=case_by_pr(baseline,7016)
    pair=check_by_name(original,'Required Checks')
    w=witness(original,pair)
    assert w['minimal_witness']['check_ids']==[119782747033,120289414102]
    with tempfile.TemporaryDirectory(prefix='verdictlens-replay-') as t:
        t=Path(t)
        cmds=[
            [sys.executable,str(ROOT/'verdictlens_cli.py'),'witness','--pr','7016','--check','Required Checks','--out',str(t/'comet_witness.json')],
            [sys.executable,str(ROOT/'verdictlens_cli.py'),'import-check-runs','--input',str(ROOT/'evidence/cli_cli_14805_GITHUB_FIELD_PROJECTION.json'),'--out',str(t/'cli_audit.json')],
            [sys.executable,str(ROOT/'verdictlens_cli.py'),'--audit',str(t/'cli_audit.json'),'verify'],
            [sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-p','test_*.py'],
            [sys.executable,str(ROOT/'repro/test_independent_case.py')]
        ]
        for cmd in cmds:
            result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
            if result.returncode:
                print(result.stdout);print(result.stderr,file=sys.stderr)
                raise AssertionError('Failed command: '+' '.join(cmd))
            if cmd[-1].endswith('test_independent_case.py') or 'discover' in cmd:print(result.stderr.strip().splitlines()[-2:])
        assert json.loads((t/'cli_audit.json').read_text())==audit
        assert json.loads((t/'comet_witness.json').read_text())==w
    integrity()
    print('PASS: original 28 tests + independent eight tests, witnesses, CLI import, manifest unchanged')
if __name__=='__main__':
    try:main()
    except Exception as e:
        print('REPRODUCTION FAILED:',e,file=sys.stderr);raise SystemExit(1)
