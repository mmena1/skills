import json,hashlib,re
from pathlib import Path
run=Path('/tmp/skills-pr130-codex-20261017');fix=run/'fixture';out=run/'export'
state=json.loads((fix/'evidence/run-state.json').read_text());index=json.loads((out/'native-index.json').read_text())
by_task={x['meta']['source']['subagent']['thread_spawn']['agent_path']:x for x in index if isinstance(x['meta']['source'],dict)}
integrity=['caller_checkout_excluding_git_and_venv','caller_git_excluding_worktree_admin','caller_venv','sim_home','shared_tmp','contracts','context','tools']
audit=[]
for e in state['invocations']:
 inv=e['id'];task='/root/'+inv.lower();n=by_task.get(task)
 if not n:continue
 report=json.loads(e['validator_report']) if 'validator_report' in e else {}
 native='\n'.join(b.get('text','') for f in n['final'] for b in f['content'])
 saved=report.get('complete_response','')
 calls=n['commands'];exec_calls=[c for c in calls if '/tools/sbx-run --cwd' in ' '.join(c['command'])]
 reads=[c for c in calls if c not in exec_calls]
 result={'id':inv,'task':task,'native_id':n['meta']['id'],'model':n['context']['model'],'effort':n['context']['effort'],'native_role':n['meta']['agent_role'],'inherited_policy':n['context']['sandbox_policy'],'approval_policy':n['context']['approval_policy'],'outcome':report.get('outcome'),'before_baseline_verified':e['before_restoration']['exact_baseline_verified'],'evidence_recorded_before_restore':e.get('preserved_before_restoration',False),'restoration_verified':e.get('restoration',{}).get('exact_baseline_verified',False),'fingerprint_matches':{k:e['fingerprint_before'][k]==e['fingerprint_after'][k] for k in integrity} if 'fingerprint_after' in e else {},'native_command_count':len(calls),'wrapper_command_event_ids':[c['event_id'] for c in exec_calls],'nonwrapper_commands':[{'event_id':c['event_id'],'command':c['command'],'exit_code':c['exit_code']} for c in reads],'complete_response_byte_equal':native==saved,'native_response_sha256':hashlib.sha256(native.encode()).hexdigest(),'saved_response_sha256':hashlib.sha256(saved.encode()).hexdigest(),'native_response_chars':len(native),'saved_response_chars':len(saved),'final_phase_observed':bool(n['final'])}
 if e.get('hook_log'):
  hook=e['hook_log'];child=json.loads(hook['child']); result['hook']={'parent_outside_writes_denied':all(v.get('errno')==30 for k,v in hook['parent'].items() if k!='owned_tmp'),'child_outside_writes_denied':all(v.get('errno')==30 for k,v in child.items() if k!='owned_tmp_child'),'parent_owned_write':hook['parent']['owned_tmp'],'child_owned_write':child['owned_tmp_child']}
 audit.append(result)
(out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps([{k:e.get(k) for k in ['id','outcome','native_id','before_baseline_verified','restoration_verified','complete_response_byte_equal','native_command_count']} for e in audit],indent=2))
