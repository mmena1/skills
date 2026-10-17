from pathlib import Path
import json,hashlib,shutil,subprocess,os,re,tomllib,datetime,importlib.util
run=Path('/tmp/skills-pr130-codex-20261017');fix=run/'fixture';out=run/'export';repo=Path('/home/martin/.codex/worktrees/214f/skills');record=Path('/home/martin/code/skills/.git/deep-review/records/skills-pr130-codex-e31ead5-01a14752')
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
state=json.loads((fix/'evidence/run-state.json').read_text());audit=json.loads((out/'audit.json').read_text());index=json.loads((out/'native-index.json').read_text())
assert [x['id'] for x in state['invocations']]==['P1','P2','P3','P4','P5']
assert len(audit)==5 and all(x['before_baseline_verified'] and x['restoration_verified'] and x['evidence_recorded_before_restore'] and x['complete_response_byte_equal'] and x['final_phase_observed'] and all(x['fingerprint_matches'].values()) for x in audit)
assert [x['outcome'] for x in audit]==['Finding','Disproved','Unresolved','Unresolved','Unresolved']
assert all(x['native_role']=='deep-review-validator-probe' and x['model']=='gpt-6-luna' and x['effort']=='high' and x['approval_policy']=='never' and x['inherited_policy']=={'type':'danger-full-access'} for x in audit)
# Verify the PR-head validator body was loaded, without exporting other developer instructions.
body=(repo/'skills/deep-review/reviewers/validator.md').read_text().strip(); role_load=[]
for p in (run/'native-home/sessions').rglob('*.jsonl'):
 evs=[json.loads(l) for l in p.read_text().splitlines()];meta=next(e['payload'] for e in evs if e['type']=='session_meta')
 if not meta.get('agent_role'):continue
 texts=[b.get('text','') for e in evs if e['type']=='response_item' and e['payload'].get('type')=='message' and e['payload'].get('role')=='developer' for b in e['payload'].get('content',[])]
 match=any(body in t for t in texts);assert match;role_load.append({'native_id':meta['id'],'canonical_validator_body_in_native_developer_message':match,'canonical_body_sha256':h(repo/'skills/deep-review/reviewers/validator.md')})
parent=next(x for x in index if x['meta']['source']=='exec')
parent_events=[json.loads(l) for l in (out/parent['export_file']).read_text().splitlines()]
ordering=[]
for a in audit:
 inv=a['id'];steps={}
 for op in ['before','preserve','restore']:
  matches=[c for c in parent['commands'] if re.search(r'state\.py\s+'+op+r'\s+'+inv+r'\b',' '.join(c['command']))]
  matches=[c for c in matches if any(('\"mode\": \"'+op+'\"') in line and ('\"id\": \"'+inv+'\"') in line for line in (c.get('result') or '').splitlines())]
  assert len(matches)==1,(inv,op,len(matches));steps[op]=matches[0]
 child=next(x for x in index if x['meta']['id']==a['native_id'])
 events=[json.loads(l) for l in (out/child['export_file']).read_text().splitlines()]
 finals=[e['payload'] for e in events if e['type']=='event_msg' and e['payload'].get('type')=='item_completed' and e['payload']['item']['type']=='AgentMessage' and e['payload']['item'].get('phase')=='final_answer'];assert len(finals)==1
 launch=[e['payload'] for e in parent_events if e['type']=='event_msg' and e['payload'].get('type')=='item_completed' and e['payload']['item']['type']=='SubAgentActivity' and e['payload']['item'].get('kind')=='started' and e['payload']['item']['agent_thread_id']==a['native_id']];assert len(launch)==1
 times={'before_complete':steps['before']['completed_at_ms'],'launch':launch[0]['completed_at_ms'],'child_final':finals[0]['completed_at_ms'],'preserve_start':steps['preserve']['started_at_ms'],'preserve_complete':steps['preserve']['completed_at_ms'],'restore_start':steps['restore']['started_at_ms'],'restore_complete':steps['restore']['completed_at_ms']}
 assert list(times.values())==sorted(times.values()),times
 ordering.append({'id':inv,'native_event_order_verified':True,'times_ms':times,'event_ids':{op:steps[op]['event_id'] for op in steps}})
for a,b in zip(ordering,ordering[1:]):assert a['times_ms']['restore_complete']<=b['times_ms']['before_complete']
unchanged_entries={}
for inv,expected in state['extension_P4_P5']['preserved_P1_P3_entry_sha256'].items():
 e=next(x for x in state['invocations'] if x['id']==inv);actual=hashlib.sha256(json.dumps(e,sort_keys=True,separators=(',',':')).encode()).hexdigest();assert actual==expected;unchanged_entries[inv]=actual
before=json.loads((run/'global-config-before.json').read_text());after={p:h(p) for p in before};assert after==before
head=json.loads(subprocess.check_output(['gh','pr','view','130','--repo','mmena1/skills','--json','headRefOid,isDraft,state'],text=True));assert head['headRefOid']==state['skill_head'] and head['state']=='OPEN' and head['isDraft']
spec=importlib.util.spec_from_file_location('coord',fix/'tools/coord.py');coord=importlib.util.module_from_spec(spec);spec.loader.exec_module(coord);fp=coord.fingerprint(fix)
for e in state['invocations']:
 for k in ['caller_checkout_excluding_git_and_venv','caller_git_excluding_worktree_admin','caller_venv','sim_home','shared_tmp']:assert e['fingerprint_before'][k]==fp[k]
assert coord.git(fix,'status','--porcelain','--ignored','--untracked-files=all')[1]==''
assert not (fix/'review-wt/.venv').exists() and not list((fix/'owned-tmp').iterdir())
# Copy fixture bytes and instrumentation before removal; never export auth or full native home.
(out/'fixture/vendor').mkdir(parents=True,exist_ok=True)
for rel in state['fixture']['files']:
 dest=out/'fixture'/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(fix/'review-wt'/rel,dest)
for directory in ['contracts','tools']:
 shutil.copytree(fix/directory,out/directory,dirs_exist_ok=True)
for name in ['setup.py','build_fixture.py','prepare_contracts.py','prepare_negative.py','export_native.py','audit.py','finalize.py','coordinator-prompt.txt','negative-coordinator-prompt.txt','preflight-limitation.txt','coordinator-final.txt','negative-coordinator-final.txt']:
 if (run/name).exists():shutil.copy2(run/name,out/name)
shutil.copy2(fix/'evidence/coordinator-report.md',out/'coordinator-report.md')
(out/'roles').mkdir(exist_ok=True)
for p in (run/'native-home/agents').glob('*.toml'):shutil.copy2(p,out/'roles'/p.name)
shutil.copy2(run/'native-home/config.toml',out/'isolated-config.toml')
(out/'observations').mkdir(exist_ok=True)
for name in ['gate-canary.json','gate-canary-before-narrowing.json','initial-restoration.json','post-canary-restoration.json']:
 shutil.copy2(fix/'evidence'/name,out/'observations'/name)
checks={'role_load':role_load,'event_ordering':ordering,'P1_P3_entries_unchanged':unchanged_entries,'global_config_and_role_hashes_before':before,'global_config_and_role_hashes_after':after,'measured_final_fingerprints':fp,'pr_prepublication':head,'source_checkout_head':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),'source_checkout_status':subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip(),'repository_checks':'PYTHONDONTWRITEBYTECODE=1 python3 scripts/check.py: passed for 31 skills; git diff --check: passed','limits':'Only measured controlled fixture paths; no general claim that the real home was unchanged. Native role tool access was instruction-enforced under inherited full access; only sbx-run commands mechanically confined. Static transitions crafted; no scouts/static wave or full review ran.'}
state['outer_native_audit']=checks
(out/'verification.json').write_text(json.dumps(checks,indent=2)+'\n')
# Remove only registered, owned fixture worktree via Git, after its last verified restoration.
r=subprocess.run(['git','-C',str(fix/'caller'),'worktree','remove',str(fix/'review-wt')],capture_output=True,text=True);assert r.returncode==0,r.stderr
remaining=subprocess.check_output(['git','-C',str(fix/'caller'),'worktree','list','--porcelain'],text=True);assert str(fix/'review-wt') not in remaining
mounts=[line for line in Path('/proc/self/mountinfo').read_text().splitlines() if str(run) in line];assert not mounts
state['cleanup']={'worktree_removed':True,'command':['git','-C',str(fix/'caller'),'worktree','remove',str(fix/'review-wt')],'remaining_fixture_worktree_registration':False,'fixture_venv_and_owned_tmp_absent_before_worktree_removal':True,'sandbox_mounts_in_host_namespace':mounts,'temporary_auth_link_removed':False,'record_directory':str(record),'temporary_run_directory':str(run),'temporary_run_cleanup':'pending verified preservation'}
(run/'native-home/auth.json').unlink();state['cleanup']['temporary_auth_link_removed']=True
shutil.rmtree(fix);shutil.rmtree(run/'runtime');shutil.rmtree(run/'native-home')
state['cleanup']['fixture_runtime_and_isolated_native_home_removed']=True
(out/'run-state.json').write_text(json.dumps(state,indent=2)+'\n')
print('Assertions passed; fixture worktree, fixture, runtime, native home and credential link removed. Export staging ready:',out)
