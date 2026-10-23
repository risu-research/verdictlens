#!/usr/bin/env python3
"""VerdictLens V9: evidence-aware, fail-closed retrospective audit.

Inputs are bundled, independently retrieved public metadata snapshots; validation
of those snapshots is distinct from live API verification. The auditor cannot
certify external record authenticity or historical enforcement from input alone.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from v8_audit import audit as audit_v8, dt
from trajectory_audit import observed_state, digest

SHA=re.compile(r'^[0-9a-f]{40}$')

class EvidenceError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise EvidenceError(message)

def check_source_urls(source):
    """Check link identity and query binding; this does NOT fetch the links."""
    checked=0
    for case in [source['new_case'],*source['v7_corpus']['cases']]:
        repo=case['repository']
        sha_by_role={s['role']:s['sha'] for s in case['subjects']}
        for row in case['checks']:
            role, sha, ctx=row['role'],row['sha'],row['context']
            require(sha==sha_by_role.get(role),f'{case["id"]}: foreign SHA')
            url=urlparse(row['lookup_url'])
            expected=f'/repos/{repo}/commits/{sha}/check-runs'
            require(url.scheme=='https' and url.netloc=='api.github.com' and url.path==expected,
                    f'{case["id"]}: wrong API source path')
            names=parse_qs(url.query).get('check_name',[])
            require(len(names)==1 and names[0]==ctx,
                    f'{case["id"]}: source URL query does not bind the exact check context')
            require(isinstance(row['run_id'],int) and row['run_id']>0,
                    f'{case["id"]}: invalid run id')
            require(row.get('event')=='merge_group' if role=='MERGE_GROUP' else True,
                    f'{case["id"]}: queue event mismatch')
            require(row['event'] in ('pull_request','merge_group','pull_request_or_post_merge_observation'),
                    f'{case["id"]}: unsupported workflow event')
            require(row['status']!='completed' or row['conclusion'] is not None,
                    f'{case["id"]}: completed check without conclusion')
            checked+=1
    return checked

def audit_timeline(source, report):
    p=source['temporal_policy']
    dates={
        'policy_source_change': dt(p['versioned_policy']['last_source_change_time']),
        'ruleset_creation': dt(p['ruleset']['created_at']),
        'ruleset_update': dt(p['ruleset']['updated_at']),
        'head_run': dt(p['head_run_started']),
        'failed_queue':dt(p['event_time']),
        'recovery_queue':dt(p['successful_queue_run_started'])
    }
    order=dates['policy_source_change'] < dates['head_run'] < dates['failed_queue'] < dates['recovery_queue']
    require(order,'policy and run chronology inconsistent')
    case=report['reports'][0]
    subjects={r['role']:r['sha'] for r in case['subjects']}
    require(p['ruleset']['id']==22969349 and p['ruleset']['type']=='merge_queue',
            'expected repository ruleset identity altered')
    src=p['versioned_policy']
    sha_list=[]
    for role in ('HEAD','MERGE_GROUP','MERGED_RESULT'):
        snapshot=src['snapshots'][role]
        require(snapshot['ref']==subjects[role] and SHA.fullmatch(snapshot['blob_sha']),
                'policy file ref or hash malformed for '+role)
        sha_list.append(snapshot['blob_sha'])
    require(len(set(sha_list))==1,'policy snapshots are not byte-identical by supplied Git blob identity')
    require(src['protected_branch']=='main' and src['required_context']=='Required Checks',
            'unsupported historical required check declaration')
    require(p['history_access']['status_code'] in (401,403),
            'historical enforcement scope must be revisited for changed access')
    checks={x['context']:x for x in case['rows']}
    required=checks['Required Checks']
    require([(x['role'],x['conclusion']) for x in required['cells']]==
            [('HEAD','success'),('MERGE_GROUP','failure'),('MERGED_RESULT','success')],
            'required-check trajectory changed')
    logs=source['causal_chain']
    from_id=logs['upstream_failed_job_id'];to_id=logs['required_check_id']
    by_id={x['id']:x for x in source['new_case']['checks']}
    require(from_id in by_id and to_id in by_id,'causal chain references absent check')
    require(by_id[from_id]['role']==by_id[to_id]['role']=='MERGE_GROUP',
            'failed prerequisite and gate must be on the same observed queue commit')
    require(by_id[from_id]['conclusion']==by_id[to_id]['conclusion']=='failure',
            'invalid prerequisite/aggregator outcome')
    require(by_id[to_id]['context']=='Required Checks' and by_id[from_id]['context']!=by_id[to_id]['context'],
            'incorrect gate or prerequisite identity')
    later=logs['recovery_observation']
    require(later['sha']==subjects['MERGED_RESULT'] and later['required_check_id'] in by_id,
            'recovery evidence not pinned to final SHA')
    require(by_id[later['required_check_id']]['run_id']==later['run_id'],
            'recovery run attribution inconsistent')
    return {
        'policy_grade':'VERSIONED_DECLARATION_STABLE_BEFORE_OBSERVATION',
        'enforcement_grade':'HISTORICAL_LIVE_SETTINGS_UNAVAILABLE',
        'source_blob_identity':sha_list[0],
        'timeline_ordered':True,
        'history_access':'HTTP '+str(p['history_access']['status_code']),
        'limitations':['The policy blob SHA is a recorded Git API result; the entire raw file is not embedded for independent byte hashing.',
                       'Version-controlled ASF declaration is not the complete past effective GitHub protection configuration.',
                       'Recorded job outcomes do not prove a code regression or unique root cause.']
    }

def audit(data):
    require(data.get('schema')=='verdictlens-v8-two-project-input','wrong input schema')
    count=check_source_urls(data)
    output=audit_v8(data)
    audit_time=audit_timeline(data,output)
    summary=[]
    for case in output['reports']:
        comparison=[]
        for r in case['rows']:
            for c in r['cells']:
                if c['state']=='NOT_OBSERVED':
                    c['interpretation']='No selected Check Run was recorded in this bounded sample; no failure assertion.'
                elif c['state']=='FAILED':
                    c['interpretation']='Selected GitHub Check Run recorded a non-passing completed conclusion.'
                elif c['state']=='SATISFIED':
                    c['interpretation']='Selected Check Run has a GitHub-acceptable conclusion; not overall merge authorization.'
                else:
                    c['interpretation']='Check execution or conclusion is not final.'
            comparison.append({'check':r['context'],'outcomes':[z['state'] for z in r['cells']],
                               'difference':bool(r['minimal_witness']),
                               'sample_complete':all(z['state']!='NOT_OBSERVED' for z in r['cells'])})
        summary.append({'case_id':case['id'],'repository':case['repository'],'pr':case['pr'],
                        'comparisons':comparison,'sample_only':True})
    output['v9']={
        'schema':'verdictlens-v9-defensive-review',
        'evidence_version':'frozen public GitHub observations, retrieved previously; network not rerun in this offline audit',
        'source_input_sha256':digest(data),
        'checked_api_lookup_urls':count,
        'temporal_provenance':audit_time,
        'samples':summary,
        'levels':{
            'observed':'RECORDED_CHECK_OUTCOME',
            'policy':'VERSIONED_SOURCE_DECLARATION',
            'enforcement':'PAST_EFFECTIVE_GITHUB_SETTINGS_NOT_RECOVERED',
            'root_cause':'UNKNOWN',
            'authorization':'NOT_ASSESSED'
        },
        'no_new_external_findings':True
    }
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',default='data/v8_input.json')
    p.add_argument('--output',default='output/v9_audit.json')
    args=p.parse_args()
    result=audit(json.loads(Path(args.input).read_text(encoding='utf-8')))
    dst=Path(args.output);dst.parent.mkdir(parents=True,exist_ok=True)
    dst.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'cases':len(result['reports']),'verified_input_links':result['v9']['checked_api_lookup_urls'],
                      'contexts':result['global_findings']['contrasting_contexts'],'policy':result['v9']['temporal_provenance']['policy_grade']}))

if __name__=='__main__': main()
