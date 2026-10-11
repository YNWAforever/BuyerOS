#!/usr/bin/env python3
"""C61 same-candidate automated provenance check and conservative go/no-go.

This first slice validates current automated evidence and all case dispositions.
Owned migration/runtime requires the full API proof and retained cold-restore observations.
Real provider/auth, quality, human UAT and production readback remain separate open gates.
The checker never authenticates a human or provider from a JUnit/report label.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
TRACE = 'docs/buyeros/evidence/c61/BuyerOS_C61_Case_Traceability_2026-10-06.csv'
ORIGINAL = 'docs/buyeros/audits/2026-10-06/BuyerOS_Test_Cases_2026-10-06.csv'
ORIGINAL_CANONICAL_DIGEST = '2c7c23fd2547c55d3d0cc063173251268068b9aec873b2e9e3b0dcea6ec72829'
NEW = 'docs/buyeros/evidence/c61/BuyerOS_C61_New_Test_Cases_2026-10-06.csv'
POST = {'U01', 'R01', 'O26-01', 'O26-15'}
NEON = {'NA28', 'NA30'}
NATIVE = {'O26-16', 'C61T-12', 'C61T-13', 'C61T-16'}
HUMAN = {'U10', 'U11', 'U12', 'O26-13'}
AUTO_GATES = {'api-full', 'worker-full', 'frontend-full', 'controller-full', 'built-ui'}
EXTERNAL_GATES = {'migration-runtime', 'real-auth', 'real-research', 'research-quality',
                  'performance', 'eight-module-journey', 'human-uat', 'workspace500-root-cause'}
ENVIRONMENTS = {'offline', 'owned-fixture', 'built-fixture', 'preview-real', 'production-readback'}

def _csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def _require(condition, message):
    if not condition: raise ValueError(message)

def load_catalog(repo):
    """Use the approved 114+16 IDs/stages and compare every original column."""
    original, trace, new = (_csv(Path(repo)/p) for p in (ORIGINAL, TRACE, NEW))
    digest=hashlib.sha256(json.dumps(original,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    _require(digest==ORIGINAL_CANONICAL_DIGEST,'original audit digest changed')
    _require(len(original)==len(trace)==114,'original114 denominator changed')
    by_id = {row['case_id']: row for row in trace}
    _require(len(by_id)==114,'duplicate original case')
    for row in original:
        _require(row['case_id'] in by_id and all(by_id[row['case_id']].get(k)==v for k,v in row.items()),'original audit columns changed')
    _require({row['case_id'] for row in new}=={f'C61T-{n:02d}' for n in range(1,17)} and len(new)==16,'new16 denominator changed')
    catalog = {}
    for row in trace:
        case = row['case_id']
        phase = ('superseded' if case=='B14' else 'postdeploy' if case in POST else
                 'neon-only' if case in NEON else 'native-send' if case in NATIVE else 'predeploy')
        expected = {'superseded':'historical-contract;successor=B15/O26-05',
                    'postdeploy':'release-A-postdeploy-readback', 'neon-only':'neon-only-final-readback',
                    'native-send':'native-send-release',
                    'predeploy':'release-A-predeploy;final-acceptance-in-declared-environment'}[phase]
        _require(row['release_stage']==expected,'unapproved original phase change: '+case)
        catalog[case] = phase
    for row in new:
        catalog[row['case_id']] = 'native-send' if row['case_id'] in NATIVE else 'predeploy'
    return catalog

def _utc(value):
    if not isinstance(value, str): raise ValueError('timestamp required')
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() is None: raise ValueError('timezone required')
    return parsed

def _artifact(root, ref, limit=10*1024*1024):
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str): raise ValueError('artifact reference required')
    path = Path(ref['path'])
    if path.is_absolute() or path.drive or '\\' in ref['path']: raise ValueError('relative artifact path required')
    root = Path(root).resolve(); target = (root/path).resolve()
    if not target.is_relative_to(root): raise ValueError('artifact path escapes root')
    if not re.fullmatch('[0-9a-f]{64}',str(ref.get('sha256',''))): raise ValueError('artifact digest required')
    if target.stat().st_size>limit: raise ValueError('artifact exceeds size limit')
    raw = target.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref['sha256']: raise ValueError('artifact digest mismatch')
    return raw

def _json(raw):
    def pairs(items):
        result = {}
        for key,value in items:
            if key in result: raise ValueError('duplicate JSON key: '+key)
            result[key]=value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('non-finite JSON number')))

def _junit(raw):
    try: text=raw.decode('utf-8-sig')
    except UnicodeDecodeError as exc: raise ValueError('UTF-8 JUnit required') from exc
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper(): raise ValueError('XML declarations are not allowed')
    document = ET.fromstring(text)
    if document.tag not in {'testsuite','testsuites'}: raise ValueError('JUnit root required')
    cases = list(document.iter('testcase'))
    if not cases: raise ValueError('empty JUnit')
    names = [(c.get('classname','').strip(), c.get('name','').strip()) for c in cases]
    if any(not c or not n for c,n in names): raise ValueError('named JUnit cases required')
    if len(names)!=len(set(names)): raise ValueError('duplicate JUnit case')
    if any(c.find(tag) is not None for c in cases for tag in ('failure','error','skipped')): raise ValueError('required case failed/error/skipped')
    for suite in document.iter():
        if suite.tag not in {'testsuite','testsuites'}: continue
        if 'tests' in suite.attrib and int(suite.attrib['tests'])!=len(list(suite.iter('testcase'))): raise ValueError('JUnit count mismatch')
        for attr in ('failures','errors','skipped'):
            if attr in suite.attrib and int(suite.attrib[attr])!=0: raise ValueError('required suite failed/error/skipped')
    return {c+'::'+n for c,n in names}

def _discovery(raw, format):
    if format=='named-json':
        data = _json(raw)
        if data.get('schema')!='buyeros.named-discovery.v1' or type(data.get('exit_code')) is not int or data['exit_code']!=0: raise ValueError('positive discovery required')
        names = data.get('cases')
        if not isinstance(names,list) or not names or any(not isinstance(n,str) or '::' not in n for n in names) or len(names)!=len(set(names)): raise ValueError('positive discovery required with unique named cases')
        return set(names)
    if format!='pytest': raise ValueError('unsupported discovery format; no inferred discovery')
    text = raw.decode('utf-8-sig'); count = re.search(r'^(\d+) tests? collected\b',text,re.M)
    lines = [line.strip() for line in text.splitlines() if line.startswith('tests/') and '::test_' in line]
    if not count or int(count[1])<=0 or len(lines)!=len(set(lines)) or len(lines)!=int(count[1]): raise ValueError('positive discovery required with unique named cases')
    names=set()
    for line in lines:
        path,node=line.split('::',1)
        if not path.endswith('.py'): raise ValueError('pytest discovery source path required')
        prefix,bracket,parameters=node.partition('[')
        parts=prefix.split('::')
        names.add(path[:-3].replace('/','.')+('.'+'.'.join(parts[:-1]) if len(parts)>1 else '')+'::'+parts[-1]+bracket+parameters)
    return names

def _full_pytest_command(command, discovery):
    """Validate an argv array without executing or interpreting shell text."""
    if not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command):
        raise ValueError('unfiltered full pytest command required')
    args = list(command)
    executable = args.pop(0).replace('\\', '/').rsplit('/', 1)[-1].lower()
    if executable in {'uv', 'uv.exe'}:
        if args[:3] != ['run', '--frozen', 'pytest']:
            raise ValueError('unfiltered full pytest command required')
        args = args[3:]
    elif re.fullmatch(r'python(?:3(?:\.\d+)?)?(?:\.exe)?', executable):
        if args[:2] == ['-X', 'utf8']: args = args[2:]
        if args[:2] != ['-m', 'pytest']:
            raise ValueError('unfiltered full pytest command required')
        args = args[2:]
    elif executable not in {'pytest', 'pytest.exe'}:
        raise ValueError('unfiltered full pytest command required')
    if args.count('--collect-only') != (1 if discovery else 0) or args.count('tests') != 1:
        raise ValueError('unfiltered full pytest command required')
    allowed = {'tests', '-q', '-v', '-vv', '--collect-only', '--disable-warnings',
               '--tb=short', '--tb=line', '--tb=no'}
    if any(arg not in allowed and not (arg.startswith('--junitxml=') and len(arg) > 11)
           for arg in args):
        raise ValueError('unfiltered full pytest command required')


def _full_backend_job(root, proof, candidate, gate):
    if gate not in {'api-full', 'worker-full'}:
        raise ValueError('typed full-job validator pending; no subset JUnit substitution')
    job = proof['validated_receipt'].get('full_job')
    if not isinstance(job, dict) or job.get('schema') != 'buyeros.full-backend-job.v1':
        raise ValueError('full backend job provenance required')
    if job.get('gate_id') != gate: raise ValueError('full job gate mismatch')
    service = 'api' if gate == 'api-full' else 'worker'
    if job.get('cwd') != 'services/' + service or job.get('test_root') != 'tests':
        raise ValueError('full job service/root mismatch')
    if proof['environment'] != 'owned-fixture' or job.get('strict_integration') is not True or job.get('fixture_scope') != 'owned-loopback-PG16':
        raise ValueError('strict owned backend fixture required')
    _full_pytest_command(job.get('discovery_command'), True)
    _full_pytest_command(job.get('execution_command'), False)
    inventory = _json(_artifact(root, job['required_inventory']))
    if not isinstance(inventory, dict) or inventory.get('schema') != 'buyeros.required-test-inventory.v1' or (
        inventory.get('source_sha'), inventory.get('source_tree')) != candidate or inventory.get('gate_id') != gate or inventory.get('environment') != proof['environment']:
        raise ValueError('full inventory source/gate/environment mismatch')
    cases = inventory.get('cases')
    if not isinstance(cases, list) or not cases or any(not isinstance(n, str) or '::' not in n for n in cases) or len(cases) != len(set(cases)):
        raise ValueError('unique full inventory cases required')
    if set(cases) != proof['validated_names']:
        raise ValueError('full inventory/discovery/JUnit mismatch')


def _controller_pnpm_args(command):
    if not isinstance(command, list) or not command or any(not isinstance(x, str) for x in command):
        raise ValueError('exact original controller pnpm argv required')
    args = list(command)
    if args[:3] == ['cmd.exe', '/d', '/c']: args = args[3:]
    if not args or args.pop(0) not in {'pnpm', 'pnpm.exe'}:
        raise ValueError('exact original controller pnpm argv required')
    return args


def _controller_command(step, command):
    args = _controller_pnpm_args(command)
    exact = {'types': ['cloudflare:types'], 'lint': ['cloudflare:lint'],
             'bindings': ['cloudflare:bindings']}
    valid = args == exact[step] if step in exact else False
    if step == 'frozen-install':
        valid = args in (['install', '--frozen-lockfile'], ['install', '--frozen-lockfile', '--offline'])
    elif step == 'discovery':
        valid = len(args) == 7 and args[:6] == ['exec', 'vitest', 'list', '--config', 'services/cloudflare-jobs/vitest.config.ts', '--json'] and bool(args[-1])
    elif step == 'tests':
        valid = len(args) == 4 and args[:3] == ['cloudflare:test', '--reporter=default', '--reporter=junit'] and args[-1].startswith('--outputFile.junit=') and len(args[-1]) > len('--outputFile.junit=')
    elif step == 'dry-run':
        valid = len(args) == 8 and args[:7] == ['exec', 'wrangler', 'deploy', '--dry-run', '--config', 'services/cloudflare-jobs/wrangler.jsonc', '--outdir'] and bool(args[-1])
    if not valid: raise ValueError('exact original controller command required: ' + step)


def _full_controller_job(root, proof, candidate):
    receipt = proof['validated_receipt']; job = receipt.get('full_job')
    if not isinstance(job, dict) or job.get('schema') != 'buyeros.full-controller-job.v1':
        raise ValueError('full controller job provenance required')
    if job.get('gate_id') != 'controller-full' or job.get('cwd') != '.':
        raise ValueError('full controller gate/root mismatch')
    if proof['environment'] != 'owned-fixture' or job.get('fixture_scope') != 'explicit-owned-Miniflare':
        raise ValueError('explicit owned controller fixture required')
    if job.get('dependency_scope') != 'fresh-owned-node_modules' or job.get('shared_node_modules') is not False or job.get('source_unchanged') is not True:
        raise ValueError('fresh unchanged controller source and dependencies required')
    _artifact(root, job['package_manifest'], 1024*1024)
    _artifact(root, job['lockfile'])
    if job.get('lockfile_after_sha256') != job['lockfile']['sha256']:
        raise ValueError('controller frozen lockfile changed')
    inventory = _json(_artifact(root, job['required_inventory']))
    if not isinstance(inventory, dict) or inventory.get('schema') != 'buyeros.required-test-inventory.v1' or (
        inventory.get('source_sha'), inventory.get('source_tree')) != candidate or inventory.get('gate_id') != 'controller-full' or inventory.get('environment') != proof['environment']:
        raise ValueError('controller full inventory source/gate/environment mismatch')
    names = inventory.get('cases')
    if not isinstance(names, list) or not names or any(not isinstance(n, str) or '::' not in n for n in names) or len(names) != len(set(names)):
        raise ValueError('unique controller full inventory required')
    if set(names) != proof['validated_names']:
        raise ValueError('controller full inventory/discovery/JUnit mismatch')
    steps = job.get('steps'); required = ['frozen-install', 'types', 'lint', 'bindings', 'discovery', 'tests', 'dry-run']
    if not isinstance(steps, list) or any(not isinstance(s, dict) for s in steps) or [s.get('step_id') for s in steps] != required:
        raise ValueError('all original controller job steps required in order')
    began, finished = (_utc(receipt[k]) for k in ('started_at_utc', 'finished_at_utc'))
    last = began
    for step in steps:
        _controller_command(step['step_id'], step.get('command'))
        if type(step.get('exit_code')) is not int or step['exit_code'] != 0:
            raise ValueError('native controller step exit must be zero')
        start, end = (_utc(step[k]) for k in ('started_at_utc', 'finished_at_utc'))
        if not began <= last <= start <= end <= finished:
            raise ValueError('controller step order/window mismatch')
        last = end
        _artifact(root, step['log'])


FRONTEND_NODE_GROUPS = {
    'candidate-client': ['tests/research-candidate-client.test.mjs'],
    'api-types': ['tests/api-types-generation.test.mjs'],
    'deployment': ['tests/vercel-services.test.mjs', 'tests/deployment/cloudflare-python-runtime.test.mjs', 'tests/deployment/cloudflare-acceptance.test.mjs', 'tests/deployment/built-ui-fixture.test.mjs'],
    'neon-session': ['tests/neon-session.test.mjs', 'tests/audit-auth-render.test.mjs', 'tests/job-poller-checks.mjs', 'tests/neon-security-proxy.test.mjs'],
    'neon-config': ['tests/neon-production-config.test.mjs', 'tests/neon-auth-boundary.test.mjs'],
    'neon-sdk': ['tests/neon-auth-server-production.test.mjs'],
    'neon-built': ['tests/neon-auth-built.test.mjs'],
    'render-and-release': ['tests/vercel-render.test.mjs', 'tests/deployment/cloudflare-release-config.test.mjs'],
}
FRONTEND_STEPS = ['frozen-install', 'domain', 'live-adapter', 'candidate-client', 'live-auth', 'audit', 'api-types', 'deployment', 'neon-session', 'neon-config', 'neon-sdk', 'types', 'lint', 'Sites-build', 'Vercel-build', 'neon-built', 'Playwright-install', 'Playwright-discovery', 'Playwright-tests', 'render-and-release']


def _frontend_node_command(command, files, server=False):
    if not isinstance(command, list) or any(not isinstance(x, str) for x in command) or not command:
        raise ValueError('exact original frontend Node argv required')
    args = list(command)
    if args.pop(0).replace('\\', '/').rsplit('/', 1)[-1].lower() not in {'node', 'node.exe'}:
        raise ValueError('exact original frontend Node argv required')
    required = ['--conditions=react-server'] if server else []
    required += ['--test', '--test-reporter=tap', '--test-reporter-destination=stdout', '--test-reporter=junit']
    if args[:len(required)] != required or len(args) != len(required)+1+len(files) or not args[len(required)].startswith('--test-reporter-destination=') or not args[len(required)].removeprefix('--test-reporter-destination=') or args[len(required)+1:] != files:
        raise ValueError('unfiltered original frontend Node group required')


def _frontend_command(sid, command, groups):
    if sid in groups:
        return _frontend_node_command(command, groups[sid], sid=='neon-sdk')
    bare = {'domain': ['node', 'tests/domain-checks.mjs'], 'live-adapter': ['node', 'tests/live-adapter-checks.mjs'], 'live-auth': ['node', 'tests/live-auth-checks.mjs'], 'Vercel-build': ['node', 'scripts/run-vercel.mjs', 'build']}
    if sid in bare:
        if command != bare[sid]: raise ValueError('exact original frontend command required: '+sid)
        return
    args = _controller_pnpm_args(command)
    exact = {'types': ['exec', 'tsc', '--noEmit'], 'lint': ['lint'], 'Sites-build': ['build'], 'Playwright-install': ['exec', 'playwright', 'install', '--with-deps', 'chromium'], 'Playwright-discovery': ['exec', 'playwright', 'test', '--config', 'playwright.neon-runtime-built.config.ts', '--list'], 'Playwright-tests': ['exec', 'playwright', 'test', '--config', 'playwright.neon-runtime-built.config.ts']}
    valid = args==exact.get(sid)
    if sid=='frozen-install': valid=args in (['install', '--frozen-lockfile'], ['install', '--frozen-lockfile', '--offline'])
    if not valid: raise ValueError('exact original frontend command required: '+sid)


def _frontend_playwright_names(raw):
    text = raw.decode('utf-8-sig')
    total = re.search(r'^Total: (\d+) tests? in (\d+) files?\s*$', text, re.M)
    rows = [line.strip() for line in text.splitlines() if ' › ' in line]
    names = []
    for row in rows:
        matched = re.fullmatch(r'(neon-(?:security|session)-production\.spec\.ts):\d+:\d+ › (.+)', row)
        if not matched: raise ValueError('native frontend Playwright inventory required')
        names.append(matched[1]+'::'+matched[2])
    if not total or not names or len(names)!=len(set(names)) or len(names)!=int(total[1]) or int(total[2])!=2 or {n.split('::',1)[0] for n in names}!={'neon-security-production.spec.ts', 'neon-session-production.spec.ts'}:
        raise ValueError('positive unique frontend Playwright discovery required')
    return set(names)


def _frontend_build_inventory(root, ref, candidate, platform):
    output = _json(_artifact(root, ref))
    if not isinstance(output, dict) or output.get('schema')!='buyeros.frontend-build-inventory.v1' or (output.get('source_sha'),output.get('source_tree'))!=candidate or output.get('platform')!=platform:
        raise ValueError('same-source frontend build inventory required')
    files = output.get('files')
    if not isinstance(files, dict) or not files: raise ValueError('positive frontend build output required')
    for path,record in files.items():
        if not isinstance(path,str) or Path(path).is_absolute() or '..' in Path(path).parts or '\\' in path or not isinstance(record,dict) or type(record.get('bytes')) is not int or record['bytes']<0 or not re.fullmatch('[0-9a-f]{64}',str(record.get('sha256',''))):
            raise ValueError('bounded frontend build inventory required')
    if not any(record['bytes']>0 for record in files.values()): raise ValueError('positive frontend build output required')


def _full_frontend_job(root, proof, candidate):
    receipt = proof['validated_receipt']; job = receipt.get('full_job')
    if not isinstance(job,dict) or job.get('schema')!='buyeros.full-frontend-job.v1': raise ValueError('full frontend job provenance required')
    if job.get('gate_id')!='frontend-full' or job.get('cwd')!='.': raise ValueError('full frontend gate/root mismatch')
    if proof['environment']!='built-fixture' or job.get('fixture_scope')!='loopback-Neon-protocol': raise ValueError('explicit frontend built fixture required')
    if job.get('dependency_scope')!='fresh-owned-node_modules' or job.get('shared_node_modules') is not False or job.get('source_unchanged') is not True: raise ValueError('fresh unchanged frontend source and dependencies required')
    _artifact(root,job['package_manifest'],1024*1024);_artifact(root,job['lockfile'])
    if job.get('lockfile_after_sha256')!=job['lockfile']['sha256']: raise ValueError('frontend frozen lockfile changed')
    source = _json(_artifact(root,job['source_inventory']))
    if not isinstance(source,dict) or source.get('schema')!='buyeros.frontend-source-inventory.v1' or (source.get('source_sha'),source.get('source_tree'))!=candidate: raise ValueError('frontend source inventory mismatch')
    files = source.get('tracked_test_files')
    if not isinstance(files,list) or not files or len(files)!=len(set(files)) or any(not isinstance(p,str) or not re.fullmatch(r'tests/(?:[a-zA-Z0-9_-]+/)*[a-zA-Z0-9_.-]+\.mjs',p) for p in files): raise ValueError('unique frontend source files required')
    groups = {k:list(v) for k,v in FRONTEND_NODE_GROUPS.items()}
    audits = sorted(p for p in files if re.fullmatch(r'tests/audit-[a-zA-Z0-9_-]+\.test\.mjs',p))
    if not audits or 'tests/audit-auth-render.test.mjs' not in audits: raise ValueError('complete original frontend audit files required')
    groups['audit'] = audits+['tests/job-poller-checks.mjs']
    required_files = {p for group in groups.values() for p in group}|{'tests/domain-checks.mjs','tests/live-adapter-checks.mjs','tests/live-auth-checks.mjs'}
    if not required_files<=set(files): raise ValueError('complete original frontend source inventory required')
    steps = job.get('steps')
    if not isinstance(steps,list) or any(not isinstance(s,dict) for s in steps) or [s.get('step_id') for s in steps]!=FRONTEND_STEPS: raise ValueError('all original frontend job steps required in order')
    began,finished = (_utc(receipt[k]) for k in ('started_at_utc','finished_at_utc'));last=began
    union=set();digests=set();browser=None;collected=None
    for step in steps:
        sid=step['step_id'];_frontend_command(sid,step.get('command'),groups)
        if type(step.get('exit_code')) is not int or step['exit_code']!=0: raise ValueError('native frontend step exit must be zero')
        start,end=(_utc(step[k]) for k in ('started_at_utc','finished_at_utc'))
        if not began<=last<=start<=end<=finished: raise ValueError('frontend step order/window mismatch')
        last=end;_artifact(root,step['log'])
        if sid in groups or sid=='Playwright-tests':
            raw=_artifact(root,step['junit']);digest=hashlib.sha256(raw).hexdigest()
            if digest in digests: raise ValueError('duplicate frontend group JUnit digest')
            names=_junit(raw);union.update(names);digests.add(digest)
            if sid=='Playwright-tests': browser=names
        elif sid=='Playwright-discovery': collected=_frontend_playwright_names(_artifact(root,step['discovery']))
        elif sid in {'Sites-build','Vercel-build'}: _frontend_build_inventory(root,step['build_inventory'],candidate,'Sites' if sid=='Sites-build' else 'Vercel')
    if collected!=browser: raise ValueError('frontend Playwright discovery/JUnit mismatch')
    if union!=proof['validated_names']: raise ValueError('full frontend group/aggregate JUnit mismatch')
    inventory=_json(_artifact(root,job['required_inventory']))
    if not isinstance(inventory,dict) or inventory.get('schema')!='buyeros.required-test-inventory.v1' or (inventory.get('source_sha'),inventory.get('source_tree'))!=candidate or inventory.get('gate_id')!='frontend-full' or inventory.get('environment')!=proof['environment'] or not isinstance(inventory.get('cases'),list) or len(inventory['cases'])!=len(set(inventory['cases'])) or set(inventory['cases'])!=union: raise ValueError('full frontend unique inventory mismatch')
    # Node has no collect-only API. Exact complete source-file argv and positive
    # native group reports establish command coverage; only Playwright carries
    # native pre-execution test-name discovery. Overlapping Node groups are unioned.
    if job.get('Node_discovery_scope')!='exact-source-file-inventory-no-collect-only' or job.get('browser_scope')!='unpatched-SDK-synthetic-loopback': raise ValueError('explicit frontend discovery and browser scope required')


BUILT_DEPENDENCY_STEPS = {'pnpm-frozen-install', 'Playwright-install', 'uv-sync-api', 'uv-sync-worker'}
BUILT_TEST_STEPS = {'audit-discovery', 'audit-tests', 'owner-discovery', 'owner-tests', 'react-discovery', 'react-tests', 'unicode-discovery', 'unicode-tests'}
BUILT_CONFIGS = {'audit': 'playwright.audit-fixes.config.ts', 'react': 'playwright.c61-react-regression.config.ts', 'unicode': 'playwright.c61-unicode-joined.config.ts'}
BUILT_AUDIT_FILES = {'audit-access-revocation.spec.ts','audit-auth-entry.spec.ts','audit-bulk-confirmation.spec.ts','audit-bulk-manifest.spec.ts','audit-candidate-review.spec.ts','audit-daily-journey.spec.ts','audit-daily-ux.spec.ts','audit-draft-dirty.spec.ts','audit-draft-reground.spec.ts','audit-job-scope.spec.ts','audit-keyboard-workbench.spec.ts','audit-keyboard.spec.ts','audit-maintenance-settings.spec.ts','audit-memberships.spec.ts','audit-native-run-progress.spec.ts','audit-operations.spec.ts','audit-research-intent.spec.ts','audit-template-copy.spec.ts','work-queue-counts.spec.ts'}


def _built_playwright_names(raw, group):
    report=_json(raw)
    if not isinstance(report,dict) or report.get('errors')!=[] or not isinstance(report.get('suites'),list): raise ValueError('native built JSON collection without errors required')
    names=[]; ids=[]
    def visit(suite,registration,parents):
        if not isinstance(suite,dict): raise ValueError('native built suite required')
        for spec in suite.get('specs',[]):
            if not isinstance(spec,dict) or not isinstance(spec.get('title'),str) or not spec['title'] or not isinstance(spec.get('id'),str) or not spec['id']: raise ValueError('native built spec identity required')
            definition=spec.get('file')
            if not isinstance(definition,str) or not re.fullmatch(r'(?:[\w.-]+/)*[\w.-]+\.ts',definition) or '..' in Path(definition).parts: raise ValueError('native built definition file required')
            tests=spec.get('tests')
            if not isinstance(tests,list) or len(tests)!=1 or not isinstance(tests[0],dict) or tests[0].get('results')!=[]: raise ValueError('native list must have one unexecuted project per spec')
            names.append(registration+'::'+' › '.join(parents+[spec['title']]));ids.append(spec['id'])
        for child in suite.get('suites',[]):
            if not isinstance(child,dict) or not isinstance(child.get('title'),str) or not child['title']: raise ValueError('native built nested suite title required')
            visit(child,registration,parents+[child['title']])
    for suite in report['suites']:
        if not isinstance(suite,dict) or not isinstance(suite.get('file'),str) or not re.fullmatch(r'[\w-]+\.spec\.ts',suite['file']): raise ValueError('native built registration spec file required')
        visit(suite,suite['file'],[])
    if not names or len(names)!=len(set(names)) or len(ids)!=len(set(ids)): raise ValueError('positive unique native built spec names and ids required')
    files={n.split('::',1)[0] for n in names}
    if group=='audit' and (not BUILT_AUDIT_FILES<=files or any(sum(n.startswith(file+'::') for n in names)<3 for file in ('audit-candidate-review.spec.ts','audit-native-run-progress.spec.ts'))): raise ValueError('all original audit and new candidate/native families required')
    if group=='react':
        required={'audit-candidate-review.spec.ts':3,'audit-bulk-manifest.spec.ts':2,'c61-eight-module-fixture.spec.ts':4,'c61-joined-authority-fixture.spec.ts':4,'c61-joined-bulk-fixture.spec.ts':4}
        counts={file:sum(n.startswith(file+'::') for n in names) for file in files}
        if len(names)!=17 or counts!=required: raise ValueError('complete original React9, joined authority4 and joined bulk4 native inventory required')
    if group=='unicode' and len(names)!=4: raise ValueError('complete joined native built inventory required')
    return set(names)


def _built_browser_args(command):
    # Keep the actual native argv in receipts; accept only the package's exact CLI.
    if isinstance(command,list) and len(command)>=2 and all(isinstance(a,str) for a in command) and command[0] in {'node','node.exe'} and command[1]=='node_modules/@playwright/test/cli.js':
        return ['exec','playwright',*command[2:]]
    return _controller_pnpm_args(command)


def _built_owner_args(command):
    if not isinstance(command,list) or not command or any(not isinstance(a,str) for a in command): raise ValueError('native built ownership command required')
    # CI uses the project frozen interpreter through uv; Windows uses that venv directly.
    if command[:6]==['uv','run','--frozen','--project','services/api','python']: command=command[5:]
    if not re.fullmatch(r'python(?:3(?:\.\d+)?)?(?:\.exe)?',command[0].replace('\\','/').rsplit('/',1)[-1].lower()): raise ValueError('native built ownership Python command required')
    args=command[1:]
    return args[2:] if args[:2]==['-X','utf8'] else args


def _full_built_job(root, proof, candidate):
    receipt=proof['validated_receipt'];job=receipt.get('full_job')
    if not isinstance(job,dict) or job.get('schema')!='buyeros.full-built-job.v1': raise ValueError('full built job provenance required')
    if job.get('gate_id')!='built-ui' or job.get('cwd')!='.': raise ValueError('full built gate/root mismatch')
    if proof['environment']!='built-fixture' or job.get('fixture_scope')!='owned-PG16-synthetic-Auth0-and-providers': raise ValueError('explicit owned built fixture required')
    if job.get('proper_Git_source_inventory') is not True or job.get('source_unchanged') is not True or job.get('dependency_scope')!='fresh-owned-node_modules-and-venvs': raise ValueError('proper unchanged built Git source and owned dependencies required')
    if job.get('browser_scope')!='native-JSON-list-equals-execution-no-live-claim' or job.get('owner_scope')!='native-seven-metadata-unit-assertions-not-Linux-process-proof': raise ValueError('explicit built browser and ownership scope required')
    inputs=job.get('dependency_inputs');required={'package.json','pnpm-lock.yaml','services/api/pyproject.toml','services/api/uv.lock','services/worker/pyproject.toml','services/worker/uv.lock'}
    if not isinstance(inputs,dict) or set(inputs)!=required: raise ValueError('all frozen built dependency inputs required')
    for ref in inputs.values(): _artifact(root,ref)
    if job.get('dependency_inputs_after_sha256')!={k:v['sha256'] for k,v in inputs.items()}: raise ValueError('frozen built dependency inputs changed')
    steps=job.get('steps')
    if not isinstance(steps,list) or len(steps)!=12 or any(not isinstance(s,dict) for s in steps) or len({s.get('step_id') for s in steps})!=12 or {s.get('step_id') for s in steps[:4]}!=BUILT_DEPENDENCY_STEPS or {s.get('step_id') for s in steps[4:]}!=BUILT_TEST_STEPS: raise ValueError('all built setup before complete native test steps required')
    began,finished=(_utc(receipt[k]) for k in ('started_at_utc','finished_at_utc'));last=began;discovered={};executed={};union=set();owner_discovered=None;owner_executed=None
    for step in steps:
        sid=step['step_id'];command=step.get('command')
        if type(step.get('exit_code')) is not int or step['exit_code']!=0: raise ValueError('native built step exit must be zero')
        start,end=(_utc(step[k]) for k in ('started_at_utc','finished_at_utc'))
        if not began<=last<=start<=end<=finished: raise ValueError('native built step order/window mismatch')
        last=end;raw=_artifact(root,step['log'])
        if sid in {'pnpm-frozen-install','Playwright-install'}:
            args=_controller_pnpm_args(command);valid=args in (['install','--frozen-lockfile'],['install','--frozen-lockfile','--offline']) if sid=='pnpm-frozen-install' else args==['exec','playwright','install','--with-deps','chromium']
            if not valid: raise ValueError('exact frozen built setup command required')
        elif sid.startswith('uv-sync-'):
            project='services/'+sid.removeprefix('uv-sync-')
            allowed=[['sync','--frozen','--project',project],['sync','--frozen','--python','3.12','--project',project]]
            if not isinstance(command,list) or not command or any(not isinstance(a,str) for a in command) or command[0].replace('\\','/').rsplit('/',1)[-1] not in {'uv','uv.exe'} or command[1:] not in allowed: raise ValueError('exact frozen built Python sync required')
        elif sid in {'owner-discovery','owner-tests'}:
            args=_built_owner_args(command)
            if sid=='owner-discovery':
                if len(args)!=2 or args[0]!='-c' or "unittest.defaultTestLoader.discover('tests',pattern='test_c61_built_owner.py')" not in args[1]: raise ValueError('native built ownership loader discovery required')
                names=_json(raw)
                if not isinstance(names,list) or len(names)!=7 or any(not isinstance(n,str) or not re.fullmatch(r'test_c61_built_owner\.BuiltOwnerTests\.test_\w+',n) for n in names) or len(set(names))!=7: raise ValueError('seven unique native ownership names required')
                owner_discovered=set(names)
            else:
                if args!=['-m','unittest','discover','-s','tests','-p','test_c61_built_owner.py','-v'] or owner_discovered is None: raise ValueError('native ownership discovery before unfiltered execution required')
                text=raw.decode('utf-8-sig').replace('\r\n','\n');names=re.findall(r'^test_\w+ \((test_c61_built_owner\.BuiltOwnerTests\.test_\w+)\) \.\.\. ok$',text,re.M)
                if len(names)!=7 or len(set(names))!=7 or not re.search(r'^Ran 7 tests in ',text,re.M) or not text.rstrip().endswith('OK'): raise ValueError('seven native ownership executions must pass')
                owner_executed=set(names)
        else:
            group,kind=sid.split('-',1);args=_built_browser_args(command);expected=['exec','playwright','test','--config',BUILT_CONFIGS[group]]+(['--list','--reporter=json'] if kind=='discovery' else [])
            if args!=expected: raise ValueError('unfiltered exact native built browser command required')
            if kind=='discovery':discovered[group]=_built_playwright_names(raw,group)
            else:
                if group not in discovered: raise ValueError('native built discovery must precede its execution')
                executed[group]=_junit(_artifact(root,step['junit']));union.update(executed[group])
    if owner_discovered!=owner_executed or discovered!=executed: raise ValueError('native built discovery/execution mismatch')
    if union!=proof['validated_names']: raise ValueError('full built native groups/aggregate JUnit mismatch')
    inventory=_json(_artifact(root,job['required_inventory']))
    if not isinstance(inventory,dict) or inventory.get('schema')!='buyeros.required-test-inventory.v1' or (inventory.get('source_sha'),inventory.get('source_tree'))!=candidate or inventory.get('gate_id')!='built-ui' or inventory.get('environment')!=proof['environment'] or not isinstance(inventory.get('cases'),list) or any(not isinstance(n,str) for n in inventory['cases']) or len(inventory['cases'])!=len(set(inventory['cases'])) or set(inventory['cases'])!=union: raise ValueError('full built unique inventory mismatch')
    # Owner unit assertions are separate metadata controls, not browser or Linux proof.



def _full_automated_job(root, proof, candidate, gate):
    if gate == 'built-ui':
        return _full_built_job(root, proof, candidate)
    if gate == 'frontend-full':
        return _full_frontend_job(root, proof, candidate)
    if gate == 'controller-full':
        return _full_controller_job(root, proof, candidate)
    return _full_backend_job(root, proof, candidate, gate)


MIGRATION_REQUIRED_NAMES = {
    'tests.test_identity_migration_db::test_fresh_0038_backfill_and_retained_rollback_preserve_canonical_history',
    'tests.test_identity_migration_db::test_identity_revision_preserves_runtime_off_and_rejects_unknown_future_head',
    'tests.test_identity_migration_db::test_supported_0038_upgrade_to_current_head_preserves_history_and_restricted_runtime',
    'tests.test_neon_cutover_db::test_identity_collision_stops_entire_cutover_batch[0]',
    'tests.test_neon_cutover_db::test_identity_collision_stops_entire_cutover_batch[1]',
    'tests.test_neon_cutover_db::test_later_denied_workspace_rolls_back_earlier_mapping',
    'tests.test_neon_cutover_db::test_unknown_batch_commit_has_one_transaction_and_only_readonly_recovery',
    'tests.test_neon_cutover_db::test_neon_cutover_rollback_preserves_new_users',
    'tests.test_neon_cutover_db::test_restore_replays_deletion_before_reopen',
    'tests.test_neon_cutover_db::test_atomic_manifest_scopes_multiple_workspaces_and_replays',
    'tests.test_delivery_admission_db::test_delivery_authority_schema_force_RLS_and_runtime_grants_are_real',
    'tests.test_delivery_admission_db::test_delivery_authority_force_RLS_owned_positive_foreign_denial_and_immutable_runtime_grants',
    'tests.test_delivery_admission_db::test_empty0050_downgrade_and_reupgrade_restore_exact_head_receipt_guards',
    'tests.test_delivery_admission_db::test_populated_authority_downgrade_refuses_and_retains_original_refs_and_full_hold',
}


def _migration_uuid(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', value) and value != '00000000-0000-0000-0000-000000000000'


def _migration_digest(value, length=64):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(length) + '}', value)


def _migration_snapshot(snapshot):
    if not isinstance(snapshot, dict): raise ValueError('actual nonempty migration snapshot required')
    ids = snapshot.get('canonical_ids')
    if not isinstance(ids, list) or len(ids) < 2 or not all(_migration_uuid(i) for i in ids) or len(ids) != len(set(ids)):
        raise ValueError('two unique historical and new canonical UUIDs required')
    identities = snapshot.get('identities')
    if not isinstance(identities, dict) or type(identities.get('count')) is not int or identities['count'] < len(ids) or not _migration_digest(identities.get('sha256')):
        raise ValueError('nonempty identity mapping readback required')
    fks = snapshot.get('historical_fks')
    if not isinstance(fks, dict) or set(fks) != set(ids) or any(not isinstance(rows, dict) or not rows or any(not isinstance(k, str) or not k or not _migration_digest(v) for k, v in rows.items()) for rows in fks.values()):
        raise ValueError('original historical FK digests required')
    ledger = snapshot.get('ledger_and_unknown')
    if not isinstance(ledger, dict) or set(ledger) != {'budget_accounts', 'budget_reservations', 'provider_operations', 'cost_events'} or any(not isinstance(row, dict) or type(row.get('count')) is not int or row['count'] < 1 or not _migration_digest(row.get('sha256')) for row in ledger.values()):
        raise ValueError('nonempty original ledger and unknown holds required')


def _migration_runtime_job(root, proof, candidate):
    # Reuse a complete source-bound native API proof once; a subset JUnit,
    # report label or boolean cannot substitute for the migration assertions.
    _full_backend_job(root, proof, candidate, 'api-full')
    receipt = proof['validated_receipt']
    job = receipt.get('migration_runtime')
    if not isinstance(job, dict) or job.get('schema') != 'buyeros.migration-runtime-job.v1' or job.get('gate_id') != 'migration-runtime':
        raise ValueError('typed migration runtime provenance required')
    if job.get('scope') != 'owned-PG16-supported0038-current0050-and-retained-app-rollback' or job.get('from_head') != '0038_c61_workspace_directory' or job.get('to_head') != '0050_c61_delivery_authorizations' or job.get('real_Neon_or_production_acceptance') is not False:
        raise ValueError('explicit owned supported-head migration scope only; no real Neon or production claim')
    if not MIGRATION_REQUIRED_NAMES <= proof['validated_names']:
        raise ValueError('all current upgrade, collision, retained rollback and real restricted-role assertions required')
    report = _json(_artifact(root, job['retained_rollback_report']))
    if not isinstance(report, dict): raise ValueError('retained migration report object required')
    before, after = report.get('before'), report.get('after')
    _migration_snapshot(before); _migration_snapshot(after)
    if any(before[key] != after[key] for key in ('canonical_ids', 'historical_fks', 'ledger_and_unknown')):
        raise ValueError('original canonical UUIDs, FK history and full unknown holds must remain exact')
    if any(report.get(key) is not True for key in ('unknown_holds_preserved', 'tombstone_replayed', 'old_epoch_fenced')):
        raise ValueError('actual retention replay and obsolete epoch refusal required')
    for key in ('closed_before', 'closed_after'):
        closed = report.get(key)
        if not isinstance(closed, dict) or closed.get('statuses') != dict(migrated=503, neon_only=503, revoked=503) or closed.get('codes') != dict(migrated='READ_DISABLED', neon_only='READ_DISABLED', revoked='READ_DISABLED'):
            raise ValueError('restored reads must stay closed before replay')
    reopened = report.get('reopened')
    if not isinstance(reopened, dict) or reopened.get('statuses') != dict(migrated=200, neon_only=200, revoked=404) or reopened.get('codes') != dict(migrated=None, neon_only=None, revoked='NOT_FOUND'):
        raise ValueError('matching owned canonical success and revoked denial required')
    projects = reopened.get('canonical_project_ids')
    if not isinstance(projects, dict) or set(projects) != {'migrated', 'neon_only'} or not all(_migration_uuid(p) for p in projects.values()) or projects['migrated'] != projects['neon_only']:
        raise ValueError('same retained owned project readback required')
    if reopened.get('ready') is not False or reopened.get('auth_package_from_archive') is not True or reopened.get('exception_metadata') != {} or type(reopened.get('approved_JWKS_fetches')) is not int or reopened['approved_JWKS_fetches'] < 1:
        raise ValueError('actual compatible archived auth load; workers remain unready, no fake readiness')
    if not _migration_digest(report.get('rollback_sha'), 40) or not _migration_digest(report.get('archive_sha256')):
        raise ValueError('retained compatible artifact identity required')
    timeline = report.get('timeline')
    if not isinstance(timeline, list) or not timeline or any(not isinstance(step, dict) or not isinstance(step.get('step'), str) for step in timeline):
        raise ValueError('actual migration timeline required')
    names = [step['step'] for step in timeline]
    required = ['current_receipt_privacy_schema_before_backup', 'older_backup', 'external_fixture_tombstone',
                'restored_backup_still_closed', 'tombstone_replayed_twice_and_ledger_reconciled_reads_still_closed',
                'old_epoch_cannot_resume_or_submit', 'local_reviewer_reopens_only_reads_with_compatible_neon_api_workers_unready']
    if len(names) != len(set(names)) or not set(required) <= set(names) or [names.index(s) for s in required] != sorted(names.index(s) for s in required):
        raise ValueError('backup, tombstone, closed restore, reconciliation, epoch fence and reopen order required')
    began, finished = (_utc(receipt[key]) for key in ('started_at_utc', 'finished_at_utc'))
    times = [_utc(step.get('utc')) for step in timeline]
    if times != sorted(times) or not began <= times[0] <= times[-1] <= finished:
        raise ValueError('migration observations outside current native proof window')
    if timeline[names.index('current_receipt_privacy_schema_before_backup')].get('schema') != job['to_head']:
        raise ValueError('current candidate migration schema readback required')



def validate(root, manifest, catalog, candidate):
    errors=[]; gates_blocked=[]; proofs={}; digests=set(); executed=0; unique=set()
    if not isinstance(manifest,dict): raise ValueError('manifest object required')
    if manifest.get('schema')!='buyeros.c61-evidence.v1': errors.append('manifest schema required')
    identity=(manifest.get('candidate_sha'),manifest.get('candidate_tree'))
    if identity!=candidate or any(not isinstance(x,str) or not re.fullmatch('[0-9a-f]{40}',x) for x in identity): errors.append('candidate identity mismatch')
    try:
        start,end=(_utc(manifest[k]) for k in ('window_start_utc','window_end_utc'))
        if start>end: raise ValueError('candidate window reversed')
    except (KeyError,TypeError,ValueError) as exc:
        errors.append(str(exc));start=end=None
    raw_proofs=manifest.get('proofs',[])
    if not isinstance(raw_proofs,list): raise ValueError('proof list required')
    ids=[p.get('id') for p in raw_proofs if isinstance(p,dict)]
    if len(ids)!=len(raw_proofs) or any(not isinstance(x,str) or not x for x in ids) or len(ids)!=len(set(ids)): errors.append('duplicate or invalid proof id')
    for proof in raw_proofs:
        if not isinstance(proof,dict): continue
        pid=proof.get('id','unnamed')
        try:
            if proof.get('kind')!='junit': raise ValueError('typed external evidence validator pending: '+str(proof.get('kind')))
            env=proof.get('environment')
            if env not in ENVIRONMENTS: raise ValueError('unsupported environment; historical/human labels cannot become JUnit acceptance')
            receipt=_json(_artifact(root,proof['provenance'],1024*1024))
            if (receipt.get('source_sha'),receipt.get('source_tree'))!=candidate or receipt.get('source_sha_after')!=candidate[0]: raise ValueError('source identity mismatch')
            if receipt.get('environment')!=env: raise ValueError('environment mismatch')
            if any(type(receipt.get(k)) is not int or receipt[k]!=0 for k in ('exit_code','required_gate_exit_code')): raise ValueError('nonzero execution or required gate')
            began,finished=(_utc(receipt[k]) for k in ('started_at_utc','finished_at_utc'))
            if start is None or not start<=began<=finished<=end: raise ValueError('execution outside candidate window')
            raw=_artifact(root,proof['junit']); digest=hashlib.sha256(raw).hexdigest()
            if digest in digests: raise ValueError('duplicate JUnit digest; no repeated totals')
            names=_junit(raw); discovered=_discovery(_artifact(root,proof['discovery']),proof['discovery_format'])
            if names!=discovered: raise ValueError('discovery/JUnit mismatch')
            digests.add(digest);proofs[pid]={**proof,'validated_names':names,'validated_receipt':receipt};executed+=len(names);unique.update((env,n) for n in names)
        except (OSError,KeyError,TypeError,ValueError,ET.ParseError) as exc: errors.append(str(pid)+': '+str(exc))
    if not raw_proofs: errors.append('no current automated proof')
    rows=manifest.get('cases',[])
    if not isinstance(rows,list): raise ValueError('case list required')
    by_id={}
    for row in rows:
        if not isinstance(row,dict): errors.append('case record required');continue
        case=row.get('case_id')
        if case in by_id: errors.append('duplicate case: '+str(case))
        by_id[case]=row
    if set(by_id)!=set(catalog): errors.append('case catalog mismatch; all114+16 dispositions required')
    valid_passes=set()
    for case,row in by_id.items():
        status=row.get('status'); refs=row.get('proof_ids',[])
        if status not in {'pending','blocked','passed','superseded'}: errors.append(str(case)+': current status required; historical result cannot be reused')
        if status=='superseded':
            if case!='B14' or row.get('successors')!=['B15','O26-05']: errors.append(str(case)+': unapproved supersession')
            elif any(by_id.get(s,{}).get('status')!='passed' or not by_id.get(s,{}).get('proof_ids') for s in ('B15','O26-05')): errors.append('B14: approved successors not verified')
        if status!='passed': continue
        if not isinstance(refs,list) or not refs or any(p not in proofs for p in refs): errors.append(str(case)+': pass requires valid proof');continue
        environments={proofs[p]['environment'] for p in refs}
        if catalog.get(case) in {'postdeploy','neon-only'} and environments!={'production-readback'}: errors.append(str(case)+': requires production-readback');continue
        if case in HUMAN: errors.append(str(case)+': requires actual human observations; JUnit is insufficient');continue
        if catalog.get(case)=='native-send': errors.append(str(case)+': native send typed receipt/readback validator pending');continue
        assertions=row.get('test_names')
        if not isinstance(assertions,list) or not assertions or any(not isinstance(n,str) for n in assertions): errors.append(str(case)+': case assertion names required');continue
        available=set().union(*(proofs[p]['validated_names'] for p in refs))
        if len(assertions)!=len(set(assertions)) or not set(assertions)<=available: errors.append(str(case)+': case assertions absent from its valid proof');continue
        valid_passes.add(case)
    gate_rows=manifest.get('gates',[])
    if not isinstance(gate_rows,list): raise ValueError('gate list required')
    seen=set();auto_passed=set();domain_passed=set()
    for gate in gate_rows:
        if not isinstance(gate,dict): errors.append('gate record required');continue
        gid=gate.get('gate_id');refs=gate.get('proof_ids',[])
        if gid in seen: errors.append('duplicate gate: '+str(gid))
        seen.add(gid)
        if gid=='migration-runtime':
            try:
                if not isinstance(refs,list) or len(refs)!=1 or refs[0] not in proofs: raise ValueError('one current independent full API proof required')
                _migration_runtime_job(root,proofs[refs[0]],candidate)
                domain_passed.add(gid)
            except (OSError,KeyError,TypeError,ValueError) as exc:
                gates_blocked.append(str(gid)+': '+str(exc))
            continue
        if gid in EXTERNAL_GATES:
            gates_blocked.append(str(gid)+': typed external evidence validator pending; no JUnit substitution');continue
        if gid not in AUTO_GATES: errors.append('unknown gate: '+str(gid));continue
        if not isinstance(refs,list) or not refs or any(p not in proofs for p in refs): gates_blocked.append(str(gid)+': current valid proof missing')
        else:
            try:
                if len(refs) != 1: raise ValueError('one independent full-job proof required')
                _full_automated_job(root, proofs[refs[0]], candidate, gid)
                auto_passed.add(gid)
            except (OSError, KeyError, TypeError, ValueError) as exc:
                gates_blocked.append(str(gid)+': '+str(exc))
    gates_blocked += [g+': current full-job evidence pending' for g in sorted(AUTO_GATES-auto_passed)]
    gates_blocked += [g+': typed external evidence validator pending' for g in sorted(EXTERNAL_GATES-seen)]
    pending=[c for c,p in catalog.items() if p=='predeploy' and c not in valid_passes]
    if pending:gates_blocked.append('predeploy cases pending/blocked: '+','.join(pending))
    if by_id.get('B14',{}).get('status')!='superseded':gates_blocked.append('B14: approved successor disposition pending')
    # Incident-specific proof must be validated by the typed gate before closure.
    gates_blocked.append('F21: historical workspace500 root cause remains open')
    blockers=errors+gates_blocked
    return {'schema':'buyeros.c61-evidence-result.v1','candidate_sha':candidate[0],'candidate_tree':candidate[1],
            'automated_evidence_valid':not errors, 'validated_test_executions':executed,
            'validated_automated_gates':sorted(auto_passed),'validated_domain_gates':sorted(domain_passed),'unique_automated_cases':len(unique),'catalog_cases':len(catalog),'required_predeploy_cases':sum(p=='predeploy' for p in catalog.values()),
            'predeploy_ready':not blockers,'release_accepted':False,'neon_only_accepted':False,'native_send_accepted':False,
            'blockers':blockers,'implementation_scope':'automated provenance/case disposition and independent full-backend/controller inventory gates; typed external gates pending; complete native frontend/built and source-bound owned migration/runtime gates supported; real Neon/provider/human/readback gates remain separate',
            'authority':'read-only local evidence validation','external_operations':0}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--output',type=Path);args=parser.parse_args(argv)
    try:
        manifest=_json(args.manifest.read_bytes())
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
        tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=REPO,text=True).strip()
        result=validate(REPO,manifest,load_catalog(REPO),(sha,tree))
    except (OSError,ValueError,TypeError,KeyError,AssertionError,subprocess.CalledProcessError) as exc:
        result={'predeploy_ready':False,'release_accepted':False,'neon_only_accepted':False,'native_send_accepted':False,'blockers':['invalid current evidence: '+str(exc)],'external_operations':0}
    body=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.output:
        with args.output.open('x',encoding='utf-8') as stream:stream.write(body)
    print(body,end='')
    return 0 if result['predeploy_ready'] else 1

if __name__=='__main__':raise SystemExit(main())
