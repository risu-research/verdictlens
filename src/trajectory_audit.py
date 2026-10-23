#!/usr/bin/env python3
"""VerdictLens V7: audited cross-subject CI check trajectories.

A witness is a minimal set of *reported observations* supporting a conclusion
change for a matched context, publisher and different commit subjects.
It is NOT a causal certificate, merger decision, or cryptographic attestation.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, re
from pathlib import Path
from urllib.parse import urlparse

SHA_RE=re.compile(r'^[a-f0-9]{40}$')
ROLES={'HEAD','TEST_MERGE','MERGE_GROUP','MERGED_RESULT'}
OK={'success','neutral','skipped'}
BAD={'failure','cancelled','timed_out','action_required','stale'}
ALL=OK|BAD|{None}


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def observed_state(rec):
    if rec is None:return 'NOT_OBSERVED'
    if rec['status']!='completed':return 'IN_PROGRESS'
    if rec['conclusion'] in OK:return 'SATISFIED'
    if rec['conclusion'] in BAD:return 'FAILED'
    return 'IN_PROGRESS'


def validate(case):
    repo=case['repository']
    if not re.fullmatch(r'[\w.-]+/[\w.-]+',repo):raise ValueError('invalid repository')
    if not isinstance(case.get('pr'),int) or case['pr']<1:raise ValueError('invalid PR number')
    roles={}
    shas=set()
    for s in case['subjects']:
        r,sha=s['role'],s['sha']
        if r not in ROLES or r in roles or not SHA_RE.fullmatch(sha) or sha in shas:raise ValueError('duplicate/invalid commit subjects')
        if r=='MERGE_GROUP' and s.get('event')!='merge_group':raise ValueError('unverified queue event')
        roles[r]=sha;shas.add(sha)
    if 'HEAD' not in roles or len(roles)<2:raise ValueError('HEAD and second commit subject required')
    if set(case.get('checked_contexts',[]))!={r['context'] for r in case['checks']}:
        raise ValueError('context manifest mismatches check observations')
    if not case['checks']:raise ValueError('no evidence')
    uniq=set();ids=set()
    for r in case['checks']:
        role=r['role']; ctx=r['context'];app=r['app_id'];sha=r['sha'];cid=r['id']
        if role not in roles or sha!=roles[role]:raise ValueError('foreign SHA or role')
        if not isinstance(ctx,str) or not ctx or not isinstance(app,int) or app<1:raise ValueError('bad check name/app identity')
        if not isinstance(cid,int) or cid<1 or cid in ids:raise ValueError('duplicate/bad check id')
        key=(role,ctx,app)
        if key in uniq:raise ValueError('ambiguous duplicate check identity')
        uniq.add(key);ids.add(cid)
        if r['status'] not in {'completed','queued','in_progress','waiting','requested','pending'}:raise ValueError('unknown check status')
        if r['conclusion'] not in ALL:raise ValueError('unknown check conclusion')
        if r['status']=='completed' and r['conclusion'] is None:raise ValueError('completed check missing conclusion')
        u=urlparse(r['url']); expected=f'/{repo}/actions/runs/{r["run_id"]}/job/{cid}'
        if u.scheme!='https' or u.netloc!='github.com' or u.path!=expected:raise ValueError('check canonical URL must align with identity')
        query=urlparse(r['lookup_url']);expectprefix=f'/repos/{repo}/commits/{sha}/check-runs'
        if query.scheme!='https' or query.netloc!='api.github.com' or query.path!=expectprefix:raise ValueError('API lookup not bound to expected SHA')
        if role=='MERGE_GROUP' and r['event']!='merge_group':raise ValueError('invalid queue event')
    return roles


def analyze_case(case):
    roles=validate(case)
    order=[s['role'] for s in case['subjects']]
    contexts=case['checked_contexts']
    rows=[]
    for ctx in contexts:
        matches=[x for x in case['checks'] if x['context']==ctx]
        apps=set(x['app_id'] for x in matches)
        if len(apps)!=1:raise ValueError('provider identity not the same across compared subjects')
        by_role={x['role']:x for x in matches}
        cells=[]
        for role in order:
            c=by_role.get(role)
            cells.append({'role':role,'sha':roles[role], 'state':observed_state(c), 'conclusion':c['conclusion'] if c else None,
                          'check_id':c['id'] if c else None,'url':c['url'] if c else None,'app_id':next(iter(apps))})
        unique_states=set(x['state'] for x in cells)
        verdict='DIFFERENT_RECORDED_RESULT' if len(unique_states)>1 and 'NOT_OBSERVED' not in unique_states else ('INCOMPLETE_COMPARISON' if 'NOT_OBSERVED' in unique_states else 'SAME_RECORDED_RESULT')
        # Smallest cross-SHA witness: earliest pair of explicit, contradictory completed check outcomes.
        pairs=[]
        for i in range(len(cells)):
            for j in range(i+1,len(cells)):
                a,b=cells[i],cells[j]
                if a['state'] in ('SATISFIED','FAILED') and b['state'] in ('SATISFIED','FAILED') and a['state']!=b['state']:
                    pairs.append({'subjects':[a['role'],b['role']], 'check_ids':[a['check_id'],b['check_id']],
                                  'shas':[a['sha'],b['sha']], 'evidence_links':[a['url'],b['url']],
                                  'claim':'Different recorded check outcomes for the same context and publisher on different commit subjects'})
        rows.append({'context':ctx,'app_id':next(iter(apps)),'cells':cells,'finding':verdict,
                     'minimal_witness':pairs[0] if pairs else None,
                     'all_contrasting_pairs':pairs})
    discrep=[r for r in rows if r['minimal_witness']]
    return {'id':case['id'],'repository':case['repository'],'pr':case['pr'],'pr_url':case['pr_url'],
            'roles':order,'subjects':case['subjects'], 'rows':rows,
            'observed_contexts':len(contexts),'verified_observations':len(case['checks']),
            'contrasting_contexts':len(discrep),
            'minimal_case_witness':discrep[0]['minimal_witness']|{'context':discrep[0]['context'],'app_id':discrep[0]['app_id']} if discrep else None,
            'claim_ledger': [
                {'claim':'Matched context and publisher across reported commit subjects','status':'SUPPORTED_BY_INPUT_VALIDATION','evidence':'Each row is indexed by context, GitHub App ID, exact SHA and check ID'},
                {'claim':'At least one contradictory recorded outcome across distinct SHA subjects','status':'SUPPORTED_BY_WITNESS' if discrep else 'NOT_OBSERVED_IN_SAMPLE','evidence':'Smallest contrasting pair of check-run IDs and URLs' if discrep else 'No contrasting pair in the selected contexts'},
                {'claim':'The context was a mandatory check on the historical incident date','status':'NOT_ESTABLISHED','required_evidence':'Contemporaneous branch protection or effective ruleset snapshot plus ref and bypass scope'},
                {'claim':'A remote service response uniquely caused the failed job','status':'NOT_ESTABLISHED','required_evidence':'Controlled rerun or independent causal diagnosis with comparable inputs'},
                {'claim':'GitHub granted or denied merge permission based on these observations','status':'OUT_OF_SCOPE','required_evidence':'Authoritative merge decision and full contemporaneous protection/queue evaluation'}
            ],
            'classification':'OBSERVED_CROSS_SHA_DIVERGENCE' if discrep else 'NO_DIVERGENCE_IN_SAMPLED_CONTEXTS',
            'log_witness':case.get('log_witness'), 'queue_job_observation':case.get('queue_job_observation'),
            'queue_check_population':case.get('queue_check_population'),
            'limitations':{'historical_required_checks':'UNVERIFIED','code_regression_causality':'NOT_ESTABLISHED',
                           'merge_authorization':'NOT_ASSESSED','test_merge_priority':'NOT_DERIVED_FROM_MERGE_GROUP',
                           'sampling':'Only specified contexts and subjects have been checked'} }

def analyze(data):
    if data.get('schema')!='verdictlens-ci-evidence-v7':raise ValueError('schema mismatch')
    results=[analyze_case(c) for c in data['cases']]
    if len({x['id'] for x in results})!=len(results):raise ValueError('duplicate case IDs')
    return {'schema':'verdictlens-trajectory-audit-v7','observed_date':data['observed_date'],
            'source_snapshot_sha256':digest(data),'reports':results,'current_ruleset':data['current_ruleset'],
            'scope':data['scope'], 'provenance':data['retrieval'],
            'global_findings':{'cases':len(results),'observations':sum(x['verified_observations'] for x in results),
                               'contrasting_contexts':sum(x['contrasting_contexts'] for x in results)},
            'evidence_policy':{'identity':'context + GitHub App ID + exact commit SHA',
                               'decision':'observed state on that subject only',
                               'root_cause':'requires independent causal controls',
                               'required_at_time':'requires contemporaneous ruleset evidence'}}

def run():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=Path('data/field_corpus.json'))
    p.add_argument('--out',type=Path,default=Path('output/trajectory_audit.json'))
    args=p.parse_args()
    output=analyze(json.loads(args.input.read_text(encoding='utf8')))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps(output['global_findings'],indent=2))

if __name__=='__main__':run()
