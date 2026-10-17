from pathlib import Path
import json,hashlib,collections
run=Path('/tmp/skills-pr130-codex-20261017'); out=run/'export'; (out/'events').mkdir(parents=True,exist_ok=True)
h=lambda b:hashlib.sha256(b).hexdigest()
def sanitized(v):
 if isinstance(v,str) and v.startswith('gAAAA'):
  return {'omitted':'opaque encrypted native payload','sha256':h(v.encode()),'bytes':len(v)}
 if isinstance(v,list):return [sanitized(x) for x in v]
 if isinstance(v,dict):return {k:sanitized(x) for k,x in v.items() if k not in ['encrypted_content','internal_chat_message_metadata_passthrough','model_instructions','summary','raw_content']}
 return v
index=[]
for p in sorted((run/'native-home/sessions').rglob('*.jsonl')):
 evs=[];meta={};ctx=None;calls=[];final=[]
 for line in p.read_text().splitlines():
  e=json.loads(line);v=e.get('payload',{});t=e['type'];keep=None
  if t=='session_meta':
   meta={k:v.get(k) for k in ['id','timestamp','cwd','cli_version','source','agent_role']};keep=meta
  elif t=='turn_context':
   keep={k:v.get(k) for k in ['turn_id','cwd','model','effort','sandbox_policy','approval_policy']};ctx=keep
  elif t=='event_msg':
   if v.get('type')=='item_completed':
    i=v['item']
    if i['type'] in ['CommandExecution','AgentMessage','SubAgentActivity','UserMessage']:
     keep=v
     if i['type']=='CommandExecution':calls.append({'event_id':i['id'],'command':i['command'],'cwd':i['cwd'],'exit_code':i.get('exit_code'),'status':i.get('status'),'stdout':i.get('stdout'),'stderr':i.get('stderr'),'result':i.get('aggregated_output'),'started_at_ms':v.get('started_at_ms'),'completed_at_ms':v.get('completed_at_ms')})
     if i['type']=='AgentMessage' and i.get('phase') in ['final','final_answer']: final.append(i)
   elif v.get('type') in ['task_started','task_complete','task_completed','turn_aborted','error']:keep=v
  elif t=='response_item':
   if v.get('type') in ['function_call','function_call_output','custom_tool_call','custom_tool_call_output','agent_message']:
    keep=v
    if v.get('type')=='function_call' and isinstance(v.get('arguments'),str):
     try:keep=dict(v,arguments=json.loads(v['arguments']))
     except json.JSONDecodeError:pass
  if keep is not None:evs.append({'timestamp':e.get('timestamp'),'type':t,'payload':sanitized(keep)})
 dest=out/'events'/f"{meta['id']}.jsonl";dest.write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in evs))
 index.append({'meta':meta,'context':ctx,'raw_transcript_sha256':h(p.read_bytes()),'export_file':'events/'+dest.name,'export_sha256':h(dest.read_bytes()),'visible_command_count':len(calls),'commands':calls,'final':final})
(out/'native-index.json').write_text(json.dumps(index,indent=2)+'\n')
(out/'export-policy.json').write_text(json.dumps({'included':'Whitelisted native session/turn identity, visible tool calls and outputs, command events and results, public agent messages, subagent lifecycle events, supplied coordinator prompt/contracts and consolidated state.','excluded':'Credentials/auth links, auth/cache DBs, environment secrets, reasoning items and reasoning summaries, private base instructions. Opaque encrypted native task payloads are replaced with hash/length markers; not decrypted. Exact child handoff prose is opaque in native logs; supplied parent prompt, contract bytes, launch identity, child contract-read commands and results are retained.','source':'Fresh isolated Codex CLI native sessions for this run only. No historical Claude events count as Codex observations.'},indent=2)+'\n')
print(json.dumps([{'id':x['meta']['id'],'role':x['meta']['agent_role'],'commands':len(x['commands']),'finals':len(x['final'])} for x in index],indent=2))
