import sys,sysconfig,pathlib,json,hashlib,shutil
fix=pathlib.Path('/tmp/skills-pr130-codex-20261017/fixture'); site=pathlib.Path(sysconfig.get_path('purelib')); inv=sys.argv[1]
if inv=='P4':
 p=site/'fixturedep-1.0.0.dist-info/METADATA'; p.write_text(p.read_text().replace('Version: 1.0.0','Version: 0.9.0')); result={'contamination':'installed metadata locked-version mismatch','path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
elif inv=='P5':
 stale=fix/'owned-tmp/stale';stale.mkdir();shutil.copy2(fix/'review-wt/app.py',stale/'app.py')
 code="import importlib.util,sys\np="+repr(str(stale/'app.py'))+"\ns=importlib.util.spec_from_file_location('app',p)\nm=importlib.util.module_from_spec(s)\nsys.modules['app']=m\ns.loader.exec_module(m)\n"
 p=site/'sitecustomize.py';p.write_text(code);result={'contamination':'startup stale-code origin, byte-identical app copy outside pinned worktree','stale_app':str(stale/'app.py'),'stale_app_sha256':hashlib.sha256((stale/'app.py').read_bytes()).hexdigest(),'startup_path':str(p),'startup_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
else: raise SystemExit('invalid invocation')
print(json.dumps(result))
