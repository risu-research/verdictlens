"""Deterministic offline adapter: GitHub REST Check Runs -> VerdictLens V9 audit view.

Input is a USER-PROVIDED, frozen JSON bundle; no GitHub API access is performed.
No historical ruleset, required-status-check, or merge authorization is inferred.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from collections import defaultdict
from verdictlens_core import SCHEMA, verify_structure, safe_github_url

INPUT_SCHEMA = 'verdictlens-github-check-runs-v1'
SHA = re.compile(r'^[0-9a-fA-F]{40}$')
REPO = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')
ROLES = ('HEAD', 'TEST_MERGE', 'MERGE_GROUP', 'MERGED_RESULT')
PASS = {'success','neutral','skipped'}
FAIL = {'failure','timed_out','action_required','startup_failure'}
UNCERTAIN = {'cancelled','stale'}
COMPLETE = PASS | FAIL | UNCERTAIN
INCOMPLETE = {'queued','in_progress','requested','waiting','pending'}


def need(ok, message):
    if not ok: raise ValueError(message)


def parse_check_response(obj, sha, role):
    """Check Run API response or an explicit array; rejects partial page and mixed SHA."""
    if isinstance(obj,dict):
        need(isinstance(obj.get('check_runs'),list),f'{role}: expected check_runs array')
        runs=obj['check_runs']
        total=obj.get('total_count')
        if total is not None:
            need(type(total) is int and total>=0,f'{role}: invalid total_count')
            need(total==len(runs),f'{role}: incomplete API response (total_count={total}, provided={len(runs)}). Fetch all pages first.')
    else:
        need(isinstance(obj,list),f'{role}: check_runs must be array or GitHub list response')
        runs=obj
    need(len(runs)<=2000,f'{role}: more than 2000 Check Runs')
    seen=set(); out=[]
    for i,r in enumerate(runs):
        msg=f'{role} Check Run #{i+1}'
        need(isinstance(r,dict),f'{msg}: not an object')
        name=r.get('name'); ident=r.get('id'); app=r.get('app')
        need(isinstance(name,str) and 0<len(name)<=300,f'{msg}: missing/invalid check name')
        need(type(ident) is int and ident>0,f'{msg}: missing/invalid numeric id')
        need(ident not in seen,f'{msg}: duplicate Check Run id {ident}')
        seen.add(ident)
        need(isinstance(app,dict) and type(app.get('id')) is int and app['id']>0,f'{msg}: missing GitHub App id')
        head=r.get('head_sha')
        need(isinstance(head,str) and SHA.fullmatch(head),f'{msg}: missing full head_sha')
        need(head.lower()==sha.lower(),f'{msg}: Check Run {ident} head_sha disagrees with declared {role} SHA')
        status=r.get('status'); conclusion=r.get('conclusion')
        need(status in INCOMPLETE|{'completed'},f'{msg}: unexpected status {status!r}')
        if status=='completed':
            need(conclusion in COMPLETE,f'{msg}: unsupported completed conclusion {conclusion!r}')
            state=('SATISFIED' if conclusion in PASS else 'FAILED' if conclusion in FAIL else 'INCONCLUSIVE')
        else:
            need(conclusion is None,f'{msg}: incomplete status with nonnull conclusion')
            state='PENDING'
        url=r.get('html_url')
        need(url is None or safe_github_url(url) is not None,f'{msg}: invalid/non-GitHub html_url')
        out.append({'name':name,'app_id':app['id'],'id':ident,'sha':sha.lower(),'status':status,
                    'conclusion':conclusion,'state':state,'url':url})
    return out


def cell_for(role, sha, matches):
    standard={'role':role,'sha':sha,'state':'NOT_OBSERVED','conclusion':None,
              'check_id':None,'url':None,'app_id':None,
              'interpretation':'No matching Check Run in the supplied bounded input. Not a recorded failure.'}
    if not matches: return standard
    if len(matches)>1:
        return {**standard,'state':'AMBIGUOUS','app_id':matches[0]['app_id'],
                'candidate_check_runs':[{'id':r['id'],'conclusion':r['conclusion'],'status':r['status'],'url':r['url']} for r in matches],
                'interpretation':f'{len(matches)} Check Runs share this check name and App on one SHA. No arbitrary rerun was selected; filter the API response explicitly before comparison.'}
    r=matches[0]
    note=('Check Run observed on the exact declared SHA. GitHub historical required-check policy was not recovered.'
          if r['state'] in ('SATISFIED','FAILED') else
          'Check Run recorded an inconclusive or unfinished state; it must not be treated as PASS or FAIL.')
    return {**standard,'state':r['state'],'conclusion':r['conclusion'],'check_id':r['id'],
            'url':r['url'],'app_id':r['app_id'],'interpretation':note}


def make_witness(a,b):
    return {'subjects':[a['role'],b['role']], 'check_ids':[a['check_id'],b['check_id']],
            'shas':[a['sha'],b['sha']], 'evidence_links':[a['url'],b['url']],
            'claim':'Contrasting observed Check Run outcomes for the same name and GitHub App on distinct declared commit subjects. Historical gate enforcement unverified.'}


def import_github_bundle(bundle):
    need(isinstance(bundle,dict) and bundle.get('schema')==INPUT_SCHEMA,
         f'Expected schema {INPUT_SCHEMA}')
    cases=bundle.get('cases') if 'cases' in bundle else [bundle]
    need(isinstance(cases,list) and 1<=len(cases)<=40,'Expected 1–40 cases')
    reports=[]
    for ci,item in enumerate(cases):
        prefix=f'case {ci+1}'
        need(isinstance(item,dict),f'{prefix}: invalid object')
        repo=item.get('repository'); pr=item.get('pr'); subjects=item.get('subjects')
        need(isinstance(repo,str) and REPO.fullmatch(repo),f'{prefix}: repository must be owner/repo')
        need(type(pr) is int and pr>0,f'{prefix}: invalid pull request number')
        need(isinstance(subjects,list) and 1<=len(subjects)<=3,f'{prefix}: expected 1–3 explicitly identified commit subjects')
        roles=[]; all_runs=[]; subj=[]
        for si,s in enumerate(subjects):
            need(isinstance(s,dict),f'{prefix} subject {si+1}: invalid object')
            role=s.get('role');sha=s.get('sha')
            need(role in ROLES and role not in roles,f'{prefix}: duplicate/unsupported subject role {role!r}')
            need(isinstance(sha,str) and SHA.fullmatch(sha),f'{prefix} {role}: full 40-character SHA required')
            need('check_runs' in s,f'{prefix} {role}: missing check_runs')
            roles.append(role);subj.append({'role':role,'sha':sha.lower()})
            all_runs.append(parse_check_response(s['check_runs'],sha,role))
        need(len({s['sha'] for s in subj})==len(subj),f'{prefix}: distinct roles cannot silently share the same SHA')
        keys=sorted({(r['name'],r['app_id']) for runs in all_runs for r in runs})
        need(1<=len(keys)<=2000,f'{prefix}: no Check Runs or over 2000 check contexts')
        counts=defaultdict(int)
        for name,app_id in keys:counts[name]+=1
        rows=[]
        for name,app_id in keys:
            label=name if counts[name]==1 else f'{name} [App {app_id}]'
            cells=[cell_for(s['role'],s['sha'],[r for r in runs if (r['name'],r['app_id'])==(name,app_id)])
                   for s,runs in zip(subj,all_runs)]
            for x in cells:
                if x['app_id'] is None:x['app_id']=app_id
            definitive=[c for c in cells if c['state'] in ('SATISFIED','FAILED')]
            contrast=next(((a,b) for i,a in enumerate(definitive) for b in definitive[i+1:]
                            if a['state']!=b['state'] and a['sha']!=b['sha']),None)
            ambiguous=any(c['state']=='AMBIGUOUS' for c in cells)
            incomplete=any(c['state'] in ('NOT_OBSERVED','PENDING','INCONCLUSIVE') for c in cells)
            finding=('AMBIGUOUS_RUNS' if ambiguous else 'DIFFERENT_RECORDED_RESULT' if contrast
                     else 'BOUNDED_EVIDENCE_GAP' if incomplete else 'SAME_RECORDED_RESULT')
            rows.append({'context':label,'app_id':app_id,'cells':cells,'finding':finding,
                         'minimal_witness':make_witness(*contrast) if contrast and not ambiguous else None})
        reports.append({'id':f'IMPORTED_{ci+1}_{repo.replace("/","_")}_PR{pr}',
                        'repository':repo,'pr':pr,'pr_url':f'https://github.com/{repo}/pull/{pr}',
                        'roles':roles,'subjects':subj,'rows':rows,'observed_contexts':len(rows),
                        'verified_observations':sum(len(x) for x in all_runs),
                        'contrasting_contexts':sum(bool(x['minimal_witness']) for x in rows),
                        'classification':'IMPORTED_CHECK_RUN_OBSERVATIONS',
                        'source_authenticity':'USER_SUPPLIED_NOT_AUTHENTICATED',
                        'input_coverage':'ONLY_PROVIDED_CHECK_RUNS; NO HISTORICAL_POLICY_AUTHENTICATION',
                        'historical_policy_provenance':None,
                        'limitations':{'historical_required_checks':'UNVERIFIED',
                                       'no_record':'ABSENT_FROM_PROVIDED_SNAPSHOT_ONLY',
                                       'merge_authorization':'NOT_ASSESSED',
                                       'duplicates':'AMBIGUOUS_NOT_SILENTLY_RESOLVED'}})
    audit={'schema':'verdictlens-v16-imported-offline-snapshot','v9':{'schema':SCHEMA},
           'reports':reports,'scope':('User-supplied GitHub-shaped Check Runs. Source is NOT authenticated. '
            'Missing checks are missing from this bounded input only. No historical ruleset or merge eligibility inference.'),
           'provenance':'OFFLINE_USER_SUPPLIED_API_EXPORT',
           'global_findings':{'cases':len(reports),'observations':sum(c['verified_observations'] for c in reports),
                             'contrasting_contexts':sum(c['contrasting_contexts'] for c in reports),
                             'repositories':len({c['repository'] for c in reports})}}
    return verify_structure(audit)


def load_github_bundle(path):
    raw=Path(path).read_bytes()
    need(len(raw)<=4*1024*1024,'Input exceeds 4 MB')
    return import_github_bundle(json.loads(raw))
