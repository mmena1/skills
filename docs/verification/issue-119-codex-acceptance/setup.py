from pathlib import Path
import shutil,json,hashlib,os,tomllib,subprocess
repo=Path('/home/martin/.codex/worktrees/214f/skills'); run=Path('/tmp/skills-pr130-codex-20261017'); fix=run/'fixture'
(run/'preflight-limitation.txt').write_text('Initial system /usr/bin/python3 3.14 fixture build failed before native invocation: ensurepip unavailable. No system package installed. Rebuilt controlled fixture to declare an existing CPython 3.11.16 runtime, copied into the owned run; this is a fixture adaptation, not a tested target-manager substitution.\n')
subprocess.run(['git','-C',str(fix/'caller'),'worktree','remove','--force',str(fix/'review-wt')],check=True)
shutil.rmtree(fix)
shutil.copytree('/home/martin/.local/share/uv/python/cpython-3.11.16-linux-x86_64-gnu',run/'runtime',symlinks=True)
py=str(run/'runtime/bin/python3.11')
builder=(repo/'docs/verification/issue-119-native-acceptance/tools/build_fixture.py').read_text().replace('/usr/bin/python3',py).replace('    python3 -m venv',f'    {py} -m venv')
(run/'build_fixture.py').write_text(builder)
subprocess.run(['/usr/bin/python3',str(run/'build_fixture.py'),str(fix)],check=True,stdout=(run/'fixture-init.json').open('w'))
for name in ['coord.py','gate_canary.py']:
 shutil.copy2(repo/'docs/verification/issue-119-native-acceptance/tools'/name,fix/'tools'/name)
for name in ['probe-environment.md','probe-environment-scenarios.md']:
 shutil.copy2(repo/'skills/deep-review/references'/name,fix/'contracts'/name)
for name in ['SKILL.md','protocol.md','runtime-acceptance.md']:
 shutil.copy2(repo/'skills/deep-review'/name,fix/'contracts'/name)
(run/'native-home/agents').mkdir(parents=True)
for name in ['deep-review-validator-probe','deep-review-validator-static']:
 shutil.copy2(repo/f'skills/deep-review/harnesses/codex/{name}.toml',run/f'native-home/agents/{name}.toml')
auth=Path(os.environ['CODEX_HOME'])/'auth.json'; assert auth.exists()
(run/'native-home/auth.json').symlink_to(auth)
orig=tomllib.loads((Path(os.environ['CODEX_HOME'])/'config.toml').read_text())
config=f'''model = {json.dumps(orig['model'])}
model_reasoning_effort = {json.dumps(orig['model_reasoning_effort'])}
approval_policy = "never"
sandbox_mode = "workspace-write"
web_search = "disabled"
[features]
memories = false
shell_snapshot = false
[agents]
max_concurrent_threads_per_session = 6
'''
for name in ['deep-review-validator-probe','deep-review-validator-static']:
 config+=f'\n[agents.{name}]\ndescription = "PR-head native acceptance role"\nconfig_file = {json.dumps(str(run/f"native-home/agents/{name}.toml"))}\n'
(run/'native-home/config.toml').write_text(config)
wrapper='''#!/bin/bash
set -euo pipefail
FIX=/tmp/skills-pr130-codex-20261017/fixture
RUNTIME=/tmp/skills-pr130-codex-20261017/runtime
[ "${1:-}" = --cwd ] || exit 64
CWD=$(realpath -m "$2"); shift 2
[ "${1:-}" = -- ] || exit 64
shift
case "$CWD" in "$FIX/review-wt"|"$FIX/review-wt/"*) ;; *) exit 64 ;; esac
exec /usr/bin/bwrap --unshare-all --die-with-parent --new-session --cap-drop ALL \\
 --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --symlink usr/sbin /sbin \\
 --ro-bind /etc /etc --proc /proc --dev /dev --tmpfs /tmp --ro-bind "$RUNTIME" "$RUNTIME" \\
 --ro-bind "$FIX" "$FIX" --bind "$FIX/review-wt" "$FIX/review-wt" \\
 --ro-bind "$FIX/review-wt/.git" "$FIX/review-wt/.git" --bind "$FIX/owned-tmp" "$FIX/owned-tmp" \\
 --clearenv --setenv PATH "$RUNTIME/bin:/usr/bin:/bin" --setenv HOME "$FIX/home" --setenv TMPDIR "$FIX/owned-tmp" \\
 --setenv PYTHONDONTWRITEBYTECODE 1 --setenv PYTHONNOUSERSITE 1 --setenv PIP_CONFIG_FILE /dev/null \\
 --setenv PIP_NO_CACHE_DIR 1 --setenv PIP_DISABLE_PIP_VERSION_CHECK 1 --chdir "$CWD" -- "$@"
'''
(fix/'tools/sbx-run').write_text(wrapper); (fix/'tools/sbx-run').chmod(0o755)
paths=[Path('/home/martin/.codex/config.toml'),Path('/mnt/c/Users/marti/.codex/config.toml')]
for root in ['/home/martin/.codex/agents','/mnt/c/Users/marti/.codex/agents']:
 paths+=list(Path(root).glob('*.toml'))
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(run/'global-config-before.json').write_text(json.dumps(hashes,indent=2))
print('isolated native home and narrowing wrapper prepared')
