'use strict';
/* Browser fallback: actual frozen audit, no live network or computed GitHub policy. */
const SOURCE=__AUDIT__;
let doc=SOURCE,caseIndex=0,checkIndex=0,subjectIndex=0,imported=false;
const notes=new Map();
const el=x=>document.getElementById(x);
const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const roleName=x=>({HEAD:'HEAD',MERGE_GROUP:'QUEUE',MERGED_RESULT:'RESULT',TEST_MERGE:'TEST MERGE'}[x]||x);
const stateName=x=>({SATISFIED:'PASS',FAILED:'FAIL',NOT_OBSERVED:'NO RECORD',PENDING:'PENDING',AMBIGUOUS:'AMBIGUOUS',INCONCLUSIVE:'INCONCLUSIVE'}[x]||'UNKNOWN');
const caze=()=>doc.reports[caseIndex],row=()=>caze().rows[checkIndex],cell=()=>row().cells[subjectIndex];
const safeLink=url=>{try{let x=new URL(url);return x.protocol==='https:'&&x.host==='github.com'&&!x.username&&!x.password?url:null}catch{return null}};
function openUrl(url){const trusted=safeLink(url);if(trusted)window.open(trusted,'_blank','noopener,noreferrer');else alert('No recorded GitHub URL for this selection.');}
function download(data,name){const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),4000)}
async function copy(value){if(!value)return;try{await navigator.clipboard.writeText(String(value))}catch{const t=document.createElement('textarea');t.value=String(value);t.style.position='fixed';t.style.left='-9999px';document.body.appendChild(t);t.select();document.execCommand('copy');t.remove()}}
function chooseCase(index){if(!doc.reports[index])return;caseIndex=index;checkIndex=caze().rows.findIndex(x=>x.minimal_witness);if(checkIndex<0)checkIndex=0;const w=caze().rows[checkIndex].minimal_witness;const wi=w?caze().roles.indexOf(w.subjects[1]):-1;subjectIndex=wi>=0?wi:0;el('filter').value='';el('viewSelect').value='all';renderAll();}
function chooseCheck(index){if(!caze().rows[index])return;checkIndex=index;const w=row().minimal_witness;const wi=w?caze().roles.indexOf(w.subjects[1]):-1;subjectIndex=wi>=0?wi:0;renderAll(false)}
function chooseSubject(index){if(!row().cells[index])return;subjectIndex=index;renderSources();renderDetails();}
function renderCases(){const opts=doc.reports.map((c,i)=>`<option value="${i}">${escapeHtml(c.repository)}  |  #${c.pr}</option>`).join('');el('caseSelect').innerHTML=opts;el('caseSelect').value=caseIndex}
function visibleRows(){const q=el('filter').value.toLowerCase().trim(),v=el('viewSelect').value;return caze().rows.map((r,i)=>({r,i})).filter(({r})=>r.context.toLowerCase().includes(q)&&(v==='all'||v==='contrasts'&&!!r.minimal_witness||v==='incomplete'&&r.cells.some(x=>['NOT_OBSERVED','PENDING','AMBIGUOUS','INCONCLUSIVE'].includes(x.state))))}
function renderChecks(){const c=caze(),roles=c.roles;el('checkHead').innerHTML=`<tr><th>Check context</th>${[0,1,2].map(j=>`<th>${roles[j]?escapeHtml(roleName(roles[j])):''}</th>`).join('')}<th>Finding</th></tr>`;
 el('checkBody').innerHTML=visibleRows().map(({r,i})=>{const outcomes=r.cells.map(x=>stateName(x.state));const finding=r.minimal_witness?'CONTRAST':outcomes.includes('NO RECORD')||['PENDING','AMBIGUOUS','INCONCLUSIVE'].some(x=>outcomes.includes(x))?'INCOMPLETE':'SAME RECORDED';return `<tr data-row="${i}" class="${i===checkIndex?'selected':''}" aria-selected="${i===checkIndex}"><td tabindex="0">${escapeHtml(r.context)}</td>${[0,1,2].map(j=>`<td data-cell="${j}" tabindex="0">${outcomes[j]?escapeHtml(outcomes[j]):''}</td>`).join('')}<td>${finding}</td></tr>`}).join('')||'<tr><td colspan="5">No checks match this filter.</td></tr>';
 for(const tr of el('checkBody').querySelectorAll('[data-row]')){
   const n=Number(tr.dataset.row);tr.onclick=e=>{const td=e.target.closest('[data-cell]');chooseCheck(n);if(td){const index=Number(td.dataset.cell);if(index<caze().roles.length)chooseSubject(index)}};
   for(const td of tr.querySelectorAll('[tabindex]'))td.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();td.click()}};
 }
 el('caseSummary').textContent=`${c.repository} #${c.pr}  |  ${c.rows.length} named checks  |  ${c.verified_observations} ${imported?'supplied Check Runs':'selected public Check Runs'}`;
}
function renderSources(){el('selectedCheck').textContent=row().context;el('sourceBody').innerHTML=row().cells.map((x,i)=>`<tr data-subject="${i}" class="${i===subjectIndex?'selected':''}"><td tabindex="0">${escapeHtml(roleName(x.role))}</td><td>${escapeHtml(stateName(x.state))}</td><td>${x.check_id??'(none)'}</td><td class="mono">${escapeHtml(x.sha)}</td></tr>`).join('');
for(const tr of el('sourceBody').querySelectorAll('tr')){tr.onclick=()=>chooseSubject(Number(tr.dataset.subject));tr.ondblclick=()=>openUrl(cell().url);tr.querySelector('[tabindex]').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseSubject(Number(tr.dataset.subject))}}}}
function renderDetails(){const x=cell(),r=row();el('status').textContent=stateName(x.state);el('sha').textContent=x.sha;el('checkId').textContent=x.check_id??'(none)';el('appId').textContent=x.app_id??r.app_id??'(unknown)';el('conclusion').textContent=x.conclusion??'(none)';el('finding').textContent=r.finding.replaceAll('_',' ');el('interpretation').textContent=x.interpretation||'No additional recorded interpretation.';el('openRun').disabled=!safeLink(x.url);el('exportWitness').disabled=!r.minimal_witness;
 el('footer').textContent=`${imported?'IMPORTED (source not authenticated)':'Bundled frozen evidence'}  |  ${doc.reports.length} cases  |  Historical enforcement: UNVERIFIED`}
function renderAll(cases=true){if(cases)renderCases();renderChecks();renderSources();renderDetails()}
function showDialog(title,text){el('dialogTitle').textContent=title;el('dialogText').textContent=text;el('dialog').showModal()}
function validateAudit(d){if(d?.v9?.schema!=='verdictlens-v9-defensive-review'||!Array.isArray(d.reports)||d.reports.length<1||d.reports.length>40)throw Error('Expected a V9 audited source');for(const c of d.reports){if(typeof c.repository!=='string'||!Number.isInteger(c.pr)||!Array.isArray(c.roles)||!Array.isArray(c.subjects)||c.subjects.length!==c.roles.length||!Array.isArray(c.rows)||c.rows.length<1||c.rows.length>2000)throw Error('Invalid case');for(const [i,s] of c.subjects.entries()){if(s.role!==c.roles[i]||typeof s.sha!=='string'||!/^[0-9a-f]{40}$/i.test(s.sha))throw Error('Invalid subject SHA')}for(const r of c.rows){if(typeof r.context!=='string'||!Array.isArray(r.cells)||r.cells.length!==c.roles.length)throw Error('Invalid check');for(const [i,x] of r.cells.entries()){if(x.role!==c.roles[i]||x.sha!==c.subjects[i].sha||!['SATISFIED','FAILED','NOT_OBSERVED','PENDING','AMBIGUOUS','INCONCLUSIVE'].includes(x.state))throw Error('Invalid cell')}}}return d}
function makeWitness(){const c=caze(),r=row();if(!r.minimal_witness)return null;return {schema:'verdictlens-v16-witness',source:imported?'imported-user-supplied':'bundled-recorded-github-check-runs',case_id:c.id,repository:c.repository,pr:c.pr,check_context:r.context,github_app_id:r.app_id,cells:r.cells,minimal_witness:r.minimal_witness,imported_unverified:imported,scope:{historical_enforcement:'UNVERIFIED',root_cause:'UNRESOLVED',merge_authorization:'NOT_ASSESSED'}}}
el('caseSelect').onchange=e=>chooseCase(Number(e.target.value));el('viewSelect').onchange=renderChecks;el('filter').oninput=renderChecks;el('clearFilter').onclick=()=>{el('filter').value='';renderChecks()};
el('openPr').onclick=()=>openUrl(caze().pr_url);el('openRun').onclick=()=>openUrl(cell().url);
el('copySha').onclick=()=>copy(cell().sha);el('copyId').onclick=()=>copy(cell().check_id);
el('exportAudit').onclick=()=>download(doc,'VerdictLens_Audit.json');
el('exportWitness').onclick=()=>{const w=makeWitness();if(w)download(w,`VerdictLens_${caze().pr}_Witness.json`)};
el('rawRecord').onclick=()=>showDialog('Raw check record',JSON.stringify(row(),null,2));
el('policy').onclick=()=>showDialog('Evidence policy and limits',`${caze().repository} #${caze().pr}\n\n${caze().historical_policy_provenance?'A source-versioned policy declaration is recorded. Historical live ruleset enforcement was not recovered.':'Historical required check settings were not independently recovered for this PR.'}\n\nSelected GitHub Check Runs are exact-commit observations, not full historical coverage. NO RECORD is not FAIL. Run failure does not establish root cause. The tool does not authorize merge. Imported JSON is format-checked but not source-authenticated.`);
el('restore').onclick=()=>{doc=SOURCE;imported=false;chooseCase(0)};
el('importAudit').onclick=()=>el('filePicker').click();
el('filePicker').onchange=async e=>{const f=e.target.files?.[0];if(!f)return;try{if(f.size>4*1024*1024)throw Error('File is larger than 4 MB');doc=validateAudit(JSON.parse(await f.text()));imported=true;chooseCase(0);alert('Audit loaded. Source authenticity was not independently verified.')}catch(err){alert('Cannot load audit: '+err.message)}finally{e.target.value=''}};
el('closeDialog').onclick=()=>el('dialog').close();
el('notes').onclick=()=>{el('notesText').value=notes.get(caze().id)||'';el('notesDialog').showModal()};
el('saveNotes').onclick=()=>{notes.set(caze().id,el('notesText').value);el('notesDialog').close()};
el('exportNotes').onclick=()=>download({schema:'verdictlens-v16-private-notes',case_id:caze().id,notes:el('notesText').value,note:'Not source evidence'},`VerdictLens_${caze().pr}_Notes.json`);
el('closeNotes').onclick=()=>el('notesDialog').close();
chooseCase(0);
/* Offline GitHub REST Check Runs importer. Mirrors the Python adapter's key judgments.
   No fetch, token, network, or historical policy reconstruction. */
const sourceSchema='verdictlens-github-check-runs-v1';
function check(condition,msg){if(!condition)throw Error(msg)}
function rawBundleToAudit(b){
 check(b&&typeof b==='object'&&!Array.isArray(b)&&b.schema===sourceSchema,'Expected '+sourceSchema);
 const cases=('cases' in b)?b.cases:[b];
 check(Array.isArray(cases)&&cases.length>=1&&cases.length<=40,'Expected 1-40 cases');
 const reports=cases.map((c,ci)=>{
  check(c&&typeof c==='object'&&/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(c.repository||''),'Invalid repository owner/repo');
  check(Number.isSafeInteger(c.pr)&&c.pr>0,'Invalid PR number');
  check(Array.isArray(c.subjects)&&c.subjects.length>=1&&c.subjects.length<=3,'Expected 1-3 subjects');
  const roles=[],subjects=[],data=[];
  for(const s of c.subjects){
   check(s&&['HEAD','TEST_MERGE','MERGE_GROUP','MERGED_RESULT'].includes(s.role)&&!roles.includes(s.role),'Invalid or duplicated role');
   check(typeof s.sha==='string'&&/^[0-9a-f]{40}$/i.test(s.sha),'Invalid SHA');
   const sha=s.sha.toLowerCase();
   check('check_runs' in s,'Missing check_runs');
   const response=s.check_runs;
   const runs=Array.isArray(response)?response:response?.check_runs;
   check(Array.isArray(runs)&&runs.length<=2000,'Expected check_runs array with at most 2000 entries');
   if(!Array.isArray(response)&&response.total_count!==undefined){
    check(Number.isSafeInteger(response.total_count)&&response.total_count===runs.length,'Incomplete API page or invalid total_count. Collect all pages.');
   }
   const ids=new Set();
   const entries=runs.map((r,i)=>{
    check(r&&typeof r==='object'&&typeof r.name==='string'&&r.name.length>0&&r.name.length<=300,'Check Run missing valid name');
    check(Number.isSafeInteger(r.id)&&r.id>0&&!ids.has(r.id),'Missing/duplicate Check Run id');ids.add(r.id);
    check(Number.isSafeInteger(r.app?.id)&&r.app.id>0,'Missing GitHub App id');
    check(typeof r.head_sha==='string'&&r.head_sha.toLowerCase()===sha,'Check Run head_sha disagrees with declared subject');
    const pass=['success','neutral','skipped'],fail=['failure','timed_out','action_required','startup_failure'],unknown=['cancelled','stale'];
    const pending=['queued','in_progress','requested','waiting','pending'];
    check(r.status==='completed'||pending.includes(r.status),'Unknown Check Run status');
    if(r.status==='completed')check([...pass,...fail,...unknown].includes(r.conclusion),'Unexpected completed conclusion');
    else check(r.conclusion==null,'Unfinished Check Run must have null conclusion');
    check(r.html_url==null||safeLink(r.html_url)!=null,'Unsafe/non-GitHub html_url');
    const state=r.status!=='completed'?'PENDING':pass.includes(r.conclusion)?'SATISFIED':fail.includes(r.conclusion)?'FAILED':'INCONCLUSIVE';
    return {name:r.name,app_id:r.app.id,id:r.id,status:r.status,conclusion:r.conclusion,url:r.html_url??null,state,sha};
   });
   roles.push(s.role);subjects.push({role:s.role,sha});data.push(entries);
  }
  check(new Set(subjects.map(x=>x.sha)).size===subjects.length,'Duplicate SHA across subjects');
  const byKey=new Map(), names=new Map();
  for(const entries of data)for(const r of entries){const key=JSON.stringify([r.name,r.app_id]);byKey.set(key,[r.name,r.app_id]);}
  const pairs=[...byKey.values()].sort((a,b)=>a[0].localeCompare(b[0])||a[1]-b[1]);
  check(pairs.length>=1&&pairs.length<=2000,'No Check Runs or too many check contexts');
  for(const [name] of pairs)names.set(name,(names.get(name)||0)+1);
  const rows=pairs.map(([name,appId])=>{
   const cells=subjects.map((s,i)=>{
    const found=data[i].filter(r=>r.name===name&&r.app_id===appId);
    const basic={role:s.role,sha:s.sha,state:'NOT_OBSERVED',conclusion:null,check_id:null,url:null,app_id:appId,interpretation:'No matching Check Run in the supplied bounded input. Not a recorded failure.'};
    if(found.length===0)return basic;
    if(found.length>1)return {...basic,state:'AMBIGUOUS',candidate_check_runs:found.map(r=>({id:r.id,conclusion:r.conclusion,status:r.status,url:r.url})),interpretation:`${found.length} runs share the name and App at this SHA. No arbitrary rerun selected.`};
    const r=found[0];return {...basic,state:r.state,conclusion:r.conclusion,check_id:r.id,url:r.url,
     interpretation:['SATISFIED','FAILED'].includes(r.state)?'Check Run observed on the exact SHA. Historical required-check policy unverified.':'Unfinished or inconclusive outcome. Not treated as PASS or FAIL.'};
   });
   const definitive=cells.filter(x=>['SATISFIED','FAILED'].includes(x.state));let contrast=null;
   outer:for(let i=0;i<definitive.length;i++)for(let j=i+1;j<definitive.length;j++)if(definitive[i].state!==definitive[j].state&&definitive[i].sha!==definitive[j].sha){contrast=[definitive[i],definitive[j]];break outer;}
   const ambiguous=cells.some(x=>x.state==='AMBIGUOUS');
   const incomplete=cells.some(x=>['NOT_OBSERVED','PENDING','INCONCLUSIVE'].includes(x.state));
   const finding=ambiguous?'AMBIGUOUS_RUNS':contrast?'DIFFERENT_RECORDED_RESULT':incomplete?'BOUNDED_EVIDENCE_GAP':'SAME_RECORDED_RESULT';
   const minimal_witness=contrast&&!ambiguous?{subjects:contrast.map(x=>x.role),check_ids:contrast.map(x=>x.check_id),shas:contrast.map(x=>x.sha),evidence_links:contrast.map(x=>x.url),claim:'Contrasting Check Runs on distinct declared commit subjects. Historical enforcement unverified.'}:null;
   return {context:names.get(name)===1?name:`${name} [App ${appId}]`,app_id:appId,cells,finding,minimal_witness};
  });
  const verified_observations=data.reduce((n,x)=>n+x.length,0);
  return {id:`IMPORTED_${ci+1}_${c.repository.replace('/','_')}_PR${c.pr}`,repository:c.repository,pr:c.pr,pr_url:`https://github.com/${c.repository}/pull/${c.pr}`,roles,subjects,rows,observed_contexts:rows.length,verified_observations,contrasting_contexts:rows.filter(x=>x.minimal_witness).length,classification:'IMPORTED_CHECK_RUN_OBSERVATIONS',source_authenticity:'USER_SUPPLIED_NOT_AUTHENTICATED',input_coverage:'ONLY_PROVIDED_CHECK_RUNS; NO HISTORICAL_POLICY_AUTHENTICATION',historical_policy_provenance:null,limitations:{historical_required_checks:'UNVERIFIED',no_record:'ABSENT_FROM_PROVIDED_SNAPSHOT_ONLY',merge_authorization:'NOT_ASSESSED',duplicates:'AMBIGUOUS_NOT_SILENTLY_RESOLVED'}};
 });
 return validateAudit({schema:'verdictlens-v16-imported-offline-snapshot',v9:{schema:'verdictlens-v9-defensive-review'},reports,
  provenance:'OFFLINE_USER_SUPPLIED_API_EXPORT',scope:'User-supplied Check Runs; not authenticated. Historical enforcement unverified.',
  global_findings:{cases:reports.length,observations:reports.reduce((n,c)=>n+c.verified_observations,0),contrasting_contexts:reports.reduce((n,c)=>n+c.contrasting_contexts,0),repositories:new Set(reports.map(x=>x.repository)).size}});
}
el('importGithub').onclick=()=>el('githubPicker').click();
el('githubPicker').onchange=async e=>{const f=e.target.files?.[0];if(!f)return;
 try{check(f.size<=4*1024*1024,'Input file exceeds 4 MB');const next=rawBundleToAudit(JSON.parse(await f.text()));doc=next;imported=true;chooseCase(0);alert('GitHub-shaped records loaded offline. Source authenticity and historical enforcement are NOT verified.');}
 catch(err){alert('Cannot import GitHub checks: '+err.message)}finally{e.target.value=''};
};
