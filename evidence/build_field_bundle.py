"""Transcribe fields actually returned by public GitHub REST API on 2026-10-23.
Extracted projection is NOT a byte-for-byte API archive; use published endpoint URLs to refetch.
"""
import json,collections,pathlib,hashlib
P=pathlib.Path(__file__).resolve().parent
sha={'HEAD':'17ac598e6afc43bb6206f074b05de9d63563a42f','MERGED_RESULT':'4f2cfe92e3499f8581bf39db77e0a1431fa7b55c'}
rows=collections.defaultdict(list)
for line in (P/'cli_cli_14805_checkruns.tsv').read_text().splitlines():
    if not line.strip() or line.startswith('#'): continue
    role,rid,name,app,conclusion,url=line.split('|',5)
    assert role in sha and rid.isdigit() and app.isdigit()
    rows[role].append({'id':int(rid),'name':name,'app':{'id':int(app)},'status':'completed','conclusion':conclusion,'head_sha':sha[role],'html_url':url})
assert len(rows['HEAD'])==19 and len(rows['MERGED_RESULT'])==20
bundle={'schema':'verdictlens-github-check-runs-v1','repository':'cli/cli','pr':14805,'subjects':[]}
for role in ['HEAD','MERGED_RESULT']:
    bundle['subjects'].append({'role':role,'sha':sha[role],'check_runs':{'total_count':len(rows[role]),'check_runs':rows[role]}})
path=P/'cli_cli_14805_GITHUB_FIELD_PROJECTION.json'
path.write_text(json.dumps(bundle,indent=2,ensure_ascii=False)+'\n')
print('counts',len(rows['HEAD']),len(rows['MERGED_RESULT']),'SHA256',hashlib.sha256(path.read_bytes()).hexdigest())
