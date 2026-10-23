"""VerdictLens V16: deterministic, offline reading of versioned Check Run evidence.

Source-linked records are observations, not authentication of GitHub's past rulesets.
No network access is used by this module.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

SCHEMA = 'verdictlens-v9-defensive-review'
BUNDLED_SHA256 = 'fb70f093f3e34823f1a0635f9c315bc31e89e79ad7cbdb0b2fdd4f6e89c6badd'
STATE_NAMES = {'SATISFIED':'PASS', 'FAILED':'FAIL', 'NOT_OBSERVED':'NO RECORD', 'PENDING':'PENDING', 'AMBIGUOUS':'AMBIGUOUS', 'INCONCLUSIVE':'INCONCLUSIVE'}
ROLE_NAMES = {'HEAD':'HEAD', 'MERGE_GROUP':'QUEUE', 'MERGED_RESULT':'RESULT', 'TEST_MERGE':'TEST MERGE'}
SCOPE = ('Selected public GitHub Check Runs, frozen snapshot. NO RECORD is not FAIL. '
         'Source-declared policy is not historical enforcement. '
         'Recorded outcomes do not establish root cause or merge authorization.')

def role_name(role):
    return ROLE_NAMES.get(role, str(role))

def state_name(state):
    return STATE_NAMES.get(state, 'UNKNOWN')

def safe_github_url(url):
    if not isinstance(url,str): return None
    try:
        x=urlparse(url)
        if x.scheme=='https' and x.netloc=='github.com' and x.path.startswith('/') and not x.username and not x.password:
            return url
    except ValueError:
        pass
    return None

def verify_structure(data):
    if not isinstance(data,dict) or data.get('v9',{}).get('schema')!=SCHEMA:
        raise ValueError('Expected audited V9 evidence')
    cases=data.get('reports')
    if not isinstance(cases,list) or not 1<=len(cases)<=40:
        raise ValueError('Expected 1–40 cases')
    for c in cases:
        if not isinstance(c,dict) or not isinstance(c.get('repository'),str) or not isinstance(c.get('pr'),int):
            raise ValueError('Invalid case identity')
        roles=c.get('roles'); subjects=c.get('subjects'); rows=c.get('rows')
        if not isinstance(roles,list) or not 1<=len(roles)<=8 or not isinstance(subjects,list) or len(subjects)!=len(roles) or not isinstance(rows,list) or not 1<=len(rows)<=2000:
            raise ValueError('Invalid subjects or checks')
        for r,s in zip(roles,subjects):
            if not isinstance(s,dict) or s.get('role')!=r or not isinstance(s.get('sha'),str) or len(s['sha'])!=40 or any(x not in '0123456789abcdef' for x in s['sha'].lower()):
                raise ValueError('Invalid commit identity')
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('context'),str) or not isinstance(row.get('cells'),list) or len(row['cells'])!=len(roles):
                raise ValueError('Invalid check row')
            for cell,role,subject in zip(row['cells'],roles,subjects):
                if not isinstance(cell,dict) or cell.get('role')!=role or cell.get('sha')!=subject['sha'] or cell.get('state') not in STATE_NAMES:
                    raise ValueError('Cell does not match commit subject')
    return data

def load_audit(path, *, bundled=False):
    raw=Path(path).read_bytes()
    if len(raw)>4*1024*1024:
        raise ValueError('Audit exceeds 4 MB')
    if bundled and hashlib.sha256(raw).hexdigest()!=BUNDLED_SHA256:
        raise ValueError('Bundled snapshot SHA-256 mismatch')
    return verify_structure(json.loads(raw))

def case_by_pr(data,pr):
    hits=[c for c in data['reports'] if c['pr']==int(pr)]
    if len(hits)!=1: raise ValueError('PR not uniquely identified: '+str(pr))
    return hits[0]

def check_by_name(case, name):
    hits=[r for r in case['rows'] if r['context']==name]
    if len(hits)!=1: raise ValueError('Check not uniquely identified: '+str(name))
    return hits[0]

def cases_summary(data):
    return [{ 'case_id':c['id'], 'repository':c['repository'],'pr':c['pr'],
        'checks':len(c['rows']),'observations':c.get('verified_observations'),
        'contrasts':sum(bool(r.get('minimal_witness')) for r in c['rows'])} for c in data['reports']]

def check_summary(case, row):
    return {
        'check':row['context'], 'finding':row['finding'],
        'outcomes':[{ 'role':role_name(c['role']), 'state':state_name(c['state']),
          'sha':c['sha'], 'check_id':c.get('check_id'), 'source':safe_github_url(c.get('url'))}
          for c in row['cells']],
        'has_contrast':bool(row.get('minimal_witness')),
    }

def witness(case,row, *, imported=False):
    w=row.get('minimal_witness')
    if not w: raise ValueError('No contrasting witness recorded for this check')
    return {'schema':'verdictlens-v16-witness','source':'imported-user-supplied' if imported else 'bundled-recorded-github-check-runs',
        'case_id':case['id'],'repository':case['repository'],'pr':case['pr'],
        'check_context':row['context'],'github_app_id':row.get('app_id'),
        'cells':row['cells'],'minimal_witness':w,
        'imported_unverified':bool(imported),
        'scope':{'historical_enforcement':'UNVERIFIED','root_cause':'UNRESOLVED','merge_authorization':'NOT_ASSESSED'}}

def write_json(path, data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
