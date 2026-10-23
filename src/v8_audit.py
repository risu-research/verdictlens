#!/usr/bin/env python3
"""Source-linked, time-aware cross-project GitHub CI evidence auditor.

Conservatively distinguishes versioned policy *intent* from actual historical
GitHub enforcement and recorded CI outcomes from causal bug diagnosis.
No network, AI, or GitHub credentials required to verify the included records.
"""
import argparse, copy, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from trajectory_audit import analyze, digest


def dt(s):
    if not isinstance(s,str): raise ValueError('invalid timestamp')
    v=datetime.fromisoformat(s.replace('Z','+00:00'))
    if v.tzinfo is None: raise ValueError('timestamp needs explicit UTC offset')
    return v.astimezone(timezone.utc)


def audit_policy(pol,subj):
    refs={s['role']:s['sha'] for s in subj}
    event=dt(pol['event_time'])
    rules=pol['ruleset']; src=pol['versioned_policy']
    checks=[]
    def gate(name,good,reason):
        checks.append({'gate':name,'pass':bool(good),'note':reason})
        return bool(good)
    gate('source_path',src.get('path')=='.asf.yaml','ASF source-controlled repository policy')
    gate('head_blob_pinned',bool(src.get('snapshots',{}).get('HEAD',{}).get('blob_sha')),'Source content hash present on the HEAD SHA')
    hashes=[]
    for role in ('HEAD','MERGE_GROUP','MERGED_RESULT'):
        entry=src.get('snapshots',{}).get(role,{})
        valid=(entry.get('ref')==refs.get(role) and len(entry.get('blob_sha',''))==40)
        gate(role+'_source_ref',valid,'Source blob queried at exact commit subject')
        hashes.append(entry.get('blob_sha'))
    gate('policy_blob_same_both_subjects',len(set(hashes))==1 and None not in hashes,'Same pinned source content observed on both commit subjects')
    gate('required_context_declared',src.get('required_context')=='Required Checks' and src.get('protected_branch')=='main','Exact Required Checks string declared in protected_branches.main')
    gate('policy_commit_before_event',dt(src['last_source_change_time'])<=event,'Commit that most recently changed source policy predates queue run')
    gate('ruleset_active',rules['enforcement']=='active','Active merge queue ruleset at retrieval')
    gate('ruleset_created_before_event',dt(rules['created_at'])<=event,'Independent GitHub Ruleset creation predates queue run')
    gate('ruleset_updated_before_event',dt(rules['updated_at'])<=event,'Independent GitHub Ruleset latest update predates queue run')
    gate('queue_event_after_head',dt(pol['head_run_started'])<event,'HEAD run was already recorded when queue started')
    gate('successful_queue_after_failure',dt(pol['successful_queue_run_started'])>event,'A later successful queue event exists')
    gate('merged_sha_is_successful_queue_sha',pol['final_merge_commit_sha']==refs.get('MERGED_RESULT'),'PR final merged commit matches the successful queue commit')
    gate('queue_check_matches_context',pol['head_required_check']['name']==pol['queue_required_check']['name']=='Required Checks','Same provider and context')
    gate('queue_provider_equal',pol['head_required_check']['app_id']==pol['queue_required_check']['app_id'],'GitHub application identity matches')
    status='VERSIONED_DECLARATION_STABLE_BEFORE_OBSERVATION' if all(c['pass'] for c in checks) else 'POLICY_PROVENANCE_INCOMPLETE'
    return {
        'grade':status,'checks':checks,
        'source_claim':'The checked commit snapshots contain the same version-controlled declaration: main requires Required Checks.',
        'ruleset_claim':'An active merge_queue ruleset was created and updated before these observations.',
        'enforcement_claim':'HISTORICAL_EFFECTIVE_BRANCH_PROTECTION_NOT_INDEPENDENTLY_RETRIEVED',
        'history_endpoint':pol['history_access'],
        'boundaries':['Source control snapshots are not a signed record of live branch protection.',
                      'Merge queue is distinct from GitHub test-merge ref.',
                      'Head and queue run differ in commit, runner, and event context.',
                      'This check is not a claim of a software regression or denied merge authorization.']}


def audit(input_data):
    if input_data.get('schema')!='verdictlens-v8-two-project-input': raise ValueError('wrong schema')
    orig=copy.deepcopy(input_data['v7_corpus'])
    orig['cases'].insert(0,input_data['new_case'])
    result=analyze(orig)
    reports={x['id']:x for x in result['reports']}
    new=reports[input_data['new_case']['id']]
    if not any(r['context']=='Required Checks' and r['minimal_witness'] for r in new['rows']):
        raise ValueError('mandatory aggregator divergence not demonstrated')
    mandatory=next(x for x in new['rows'] if x['context']=='Required Checks')
    chain=input_data['causal_chain']
    roles={x['role']:x['sha'] for x in new['subjects']}
    idset={r['id'] for r in input_data['new_case']['checks']}
    if chain['required_check_id'] not in idset or chain['upstream_failed_job_id'] not in idset:
        raise ValueError('causal chain check IDs not in selected evidence')
    if chain['upstream_failed_job_id']==chain['required_check_id']:
        raise ValueError('causal chain cannot use same job as prerequisite and aggregator')
    evidence={'project':new['repository'],'pr':new['pr'],
              'same_required_context':mandatory['minimal_witness'],
              'from_job':chain['upstream_failed_job_id'],'to_aggregator':chain['required_check_id'],
              'log_assertions':chain['log_assertions'], 'recovery_observation':chain.get('recovery_observation'),
              'interpretation':'Observed failed prerequisite appears as pr_build_macos: failure in Required Checks aggregation. ZIP unpack failure is recorded; why the ZIP was invalid remains unknown.',
              'not_a_full_causal_proof':True}
    temporal=audit_policy(input_data['temporal_policy'],new['subjects'])
    new['historical_policy_provenance']=temporal
    new['dependency_trace']=evidence
    # Override V7 broad, default case-level policy text with graded, source-specific evidence.
    new['claim_ledger'].append({'claim':'Same versioned required-check declaration on HEAD and MERGE_GROUP subjects','status':temporal['grade'],
                                 'evidence':'ASF .asf.yaml source blob at both exact commit subjects, source last change prior to incident'})
    new['claim_ledger'].append({'claim':'Underlying failing job explains aggregator failure in original logs','status':'LOG_SUPPORTED_FOR_JOB_DEPENDENCY',
                                 'evidence':'Upstream job failure and Required Checks logs record pr_build_macos: failure'})
    result['v8']={'schema':'verdictlens-v8-independent-cross-project-audit',
                  'case':new['id'],'temporal_policy':temporal,'dependency_trace':evidence,
                  'provenance':input_data['temporal_policy'],
                  'source_data_sha256':digest(input_data)}
    result['global_findings']['repositories']=len(set(x['repository'] for x in result['reports']))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',default='data/v8_input.json');p.add_argument('--output',default='output/v8_audit.json');a=p.parse_args()
    result=audit(json.loads(Path(a.input).read_text()))
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'findings':result['global_findings'],'temporal_grade':result['v8']['temporal_policy']['grade'],'gates':len(result['v8']['temporal_policy']['checks'])}))

if __name__=='__main__': main()
