import sys,json,hashlib,importlib.util,subprocess
from pathlib import Path
fix=Path('/tmp/skills-pr130-codex-20261017/fixture')
spec=importlib.util.spec_from_file_location('coord',fix/'tools/coord.py'); c=importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
p=fix/'evidence/run-state.json';d=json.loads(p.read_text()) if p.exists() else {'kind':'targeted Codex native coordinator/probe acceptance, crafted static transitions, not a full review','skill_head':'e31ead5ff2f45b67cbe29cea95f8bf202f4a6621','fixture':json.loads((fix/'evidence/fixture.json').read_text()),'invocations':[]}
mode,inv=sys.argv[1:3]
if mode=='before':
 restore=c.restore(fix); assert restore['exact_baseline_verified'];d['invocations'].append({'id':inv,'before_restoration':restore,'fingerprint_before':c.fingerprint(fix)})
elif mode=='preserve':
 e=d['invocations'][-1];assert e['id']==inv;e['validator_report']=sys.stdin.read();e['contract']=json.loads((fix/f'contracts/contract-{inv}.json').read_text());e['fingerprint_after']=c.fingerprint(fix)
 hook=fix/'owned-tmp/issue119-hook-log.json';e['hook_log']=json.loads(hook.read_text()) if hook.exists() else None
 e['pre_restore_status']=c.git(fix,'status','--porcelain','--ignored','--untracked-files=all')[1].splitlines();e['preserved_before_restoration']=True
elif mode=='restore':
 e=d['invocations'][-1];assert e['id']==inv and e['preserved_before_restoration'];e['restoration']=c.restore(fix);assert e['restoration']['exact_baseline_verified']
else: raise SystemExit('unknown')
p.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':mode,'id':inv,'state_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'exact_baseline':d['invocations'][-1].get('restoration',d['invocations'][-1].get('before_restoration'))['exact_baseline_verified']}))
