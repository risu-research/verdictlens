#!/usr/bin/env python3
"""Offline command-line interface for recorded public GitHub Check Run evidence."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from verdictlens_core import load_audit,case_by_pr,check_by_name,check_summary,cases_summary,witness,write_json,state_name,role_name,SCOPE
from github_import import load_github_bundle,INPUT_SCHEMA,import_github_bundle

def main(argv=None):
    p=argparse.ArgumentParser(description='VerdictLens V16 - inspect frozen GitHub Check Run records')
    p.add_argument('--audit',default=str(ROOT/'data/v9_audit.json'),help='Path to V9 audit JSON; imports are structurally validated but not authenticated')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('list',help='List bundled cases')
    i=sub.add_parser('inspect',help='Print a commit-by-commit table');i.add_argument('--pr',type=int,required=True);i.add_argument('--check');i.add_argument('--json',action='store_true')
    w=sub.add_parser('witness',help='Export a recorded minimal contrasting witness');w.add_argument('--pr',type=int,required=True);w.add_argument('--check',required=True);w.add_argument('--out',required=True)
    sub.add_parser('verify',help='Verify input structure and compare bundled file hash')
    imp=sub.add_parser('import-check-runs',help='Convert GitHub REST Check Runs bundle to a VerdictLens audit')
    imp.add_argument('--input',required=True,help='User-supplied versioned Check Runs bundle JSON')
    imp.add_argument('--out',required=True,help='Generated audit JSON; no GitHub authentication implied')
    pack=sub.add_parser('pack-check-runs',help='Build a bundle from separate per-SHA API JSON files')
    pack.add_argument('--repo',required=True,help='owner/repo')
    pack.add_argument('--pr',type=int,required=True)
    for role in ('head','test-merge','queue','result'):
        pack.add_argument('--'+role,metavar='SHA=PATH',help='Commit SHA and complete API JSON response file')
    pack.add_argument('--out',required=True)

    args=p.parse_args(argv)
    try:
        if args.command=='import-check-runs':
            new=load_github_bundle(args.input)
            write_json(args.out,new)
            print(f"Imported {len(new['reports'])} case(s), {sum(len(c['rows']) for c in new['reports'])} check contexts to {args.out}")
            print('User-supplied records, NOT authenticated; historical required-check policy UNVERIFIED.')
            return 0
        if args.command=='pack-check-runs':
            specs=[('HEAD',args.head),('TEST_MERGE',args.test_merge),('MERGE_GROUP',args.queue),('MERGED_RESULT',args.result)]
            subjects=[]
            for role,spec in specs:
                if spec is None:continue
                if '=' not in spec:raise ValueError(role+' must use SHA=PATH')
                sha,path=spec.split('=',1)
                raw=Path(path).read_bytes()
                if len(raw)>4*1024*1024:raise ValueError('API file exceeds 4MB: '+path)
                subjects.append({'role':role,'sha':sha,'check_runs':json.loads(raw)})
            if not subjects:raise ValueError('Specify at least one --head/--queue/... SHA=PATH')
            bundle={'schema':INPUT_SCHEMA,'repository':args.repo,'pr':args.pr,'subjects':subjects}
            import_github_bundle(bundle)  # Strict validation before packaging.
            write_json(args.out,bundle)
            print('Created '+args.out+' (user-supplied GitHub API data; unverified)')
            return 0
        bundled=Path(args.audit).resolve()==(ROOT/'data/v9_audit.json').resolve()
        d=load_audit(args.audit,bundled=bundled)
        if args.command=='list':
            for c in cases_summary(d):print(f"{c['repository']}  #{c['pr']}  |  {c['checks']} checks  |  {c['observations']} observed runs  |  {c['contrasts']} contrasts")
        elif args.command=='inspect':
            c=case_by_pr(d,args.pr)
            rows=[check_by_name(c,args.check)] if args.check else c['rows']
            if args.json:print(json.dumps({'repository':c['repository'],'pr':c['pr'],'checks':[check_summary(c,r) for r in rows],'scope':d.get('scope',SCOPE)},indent=2))
            else:
                print(f"{c['repository']}  PR #{c['pr']}  ({'user-supplied; unverified' if c.get('source_authenticity') else 'recorded snapshot'})")
                print('Check'.ljust(71)+' '.join(role_name(r).ljust(11) for r in c['roles']))
                print('-'*min(115,71+12*len(c['roles'])))
                for row in rows:
                    print(row['context'][:70].ljust(71)+' '.join(state_name(x['state']).ljust(11) for x in row['cells']))
                    if args.check:
                        for x in row['cells']:
                            print(f"    {role_name(x['role'])}: {x['sha']}  Check Run #{x.get('check_id') or 'none'}")
                            print(f"    {x.get('url') or '(no recorded URL)'}")
                print('\n'+d.get('scope',SCOPE))
        elif args.command=='witness':
            c=case_by_pr(d,args.pr);r=check_by_name(c,args.check)
            write_json(args.out,witness(c,r,imported=not bundled));print('Wrote '+args.out)
        elif args.command=='verify':
            print(f"Structure: PASS  |  Cases: {len(d['reports'])}  |  File: {'bundled SHA-256 matches' if bundled else 'external audit, source authenticity unverified'}")
            print('Note: structural validation is not independent GitHub authentication.')
        return 0
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as e:
        print('Error: '+str(e),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
