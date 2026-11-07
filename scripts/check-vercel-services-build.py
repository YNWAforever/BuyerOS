"""Build a credential-free two-service fixture outside the checkout (Linux CI)."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def check(cli_package):
    checkout=Path(__file__).resolve().parents[1]
    package=cli_package.resolve(strict=True)
    if json.loads((package/'package.json').read_text())['version']!='54.17.2':
        raise ValueError('CLI 54.17.2 required')
    cli=package/'dist/vc.js'
    if not cli.is_file():raise ValueError('CLI entrypoint missing')
    if sys.platform!='linux' or sys.version_info[:2]!=(3,12):
        raise ValueError('Linux and CI-provided Python 3.12 required')
    parent=Path(tempfile.gettempdir()).resolve()
    if parent==checkout or parent.is_relative_to(checkout):
        raise ValueError('temporary directory must be outside checkout')
    fixture=Path(tempfile.mkdtemp(prefix='buyeros-services-ci-',dir=parent)).resolve()
    started=time.monotonic()
    report={'schema':'buyeros.services-build-check.v1','cli_version':'54.17.2',
            'scope':'synthetic_local_build_no_deployment','passed':False,'phase':'fixture_setup'}
    try:
        workspace=fixture/'workspace'
        for name in ('workspace/app','workspace/services/api','global-config','tmp','npm-cache','uv-cache'):
            (fixture/name).mkdir(parents=True,exist_ok=True)
        (fixture/'empty.npmrc').write_text('',encoding='utf-8')
        (fixture/'empty-global.npmrc').write_text('',encoding='utf-8')
        write_json(fixture/'global-config/config.json',{'collectMetrics':False})
        write_json(workspace/'.vercel/project.json',{
            'projectId':'prj_fixtureonly','orgId':'team_fixtureonly','projectName':'buyeros-ci-fixture',
            'settings':{'framework':'services','nodeVersion':'24.x','rootDirectory':None,
                        'installCommand':None,'buildCommand':None,'outputDirectory':None}})
        (workspace/'.vercel/.env.production.local').write_text(
            '# Synthetic fixture only\nFIXTURE_MARKER="services-build-check"\n',encoding='utf-8')
        binding={'type':'service','service':'api','format':'url','env':'BUYEROS_INTERNAL_API_URL'}
        write_json(workspace/'vercel.json',{'services':{
            'app':{'root':'app','framework':'express','entrypoint':'index.js','bindings':[binding]},
            'api':{'root':'services/api','framework':'fastapi','entrypoint':'main:app',
                   'functions':{'main.py':{'maxDuration':90}}}},
            'rewrites':[{'source':'/(.*)','destination':{'service':'app'}}]})
        for directory,name,deps in [(workspace,'buyeros-ci-fixture',{}),
                                    (workspace/'app','buyeros-ci-app',{'express':'4.21.2'})]:
            pkg={'name':name,'private':True,'version':'1.0.0','dependencies':deps}
            write_json(directory/'package.json',pkg)
            write_json(directory/'package-lock.json',{'name':name,'version':'1.0.0',
                'lockfileVersion':3,'requires':True,'packages':{'':pkg}})
        (workspace/'app/index.js').write_text(
            "const app=require('express')(); app.get('/',(req,res)=>res.json({service:'app'})); module.exports=app;\n",
            encoding='utf-8')
        (workspace/'services/api/main.py').write_text(
            "from fastapi import FastAPI\napp=FastAPI()\n@app.get('/')\ndef index():\n    return {'service':'api'}\n",
            encoding='utf-8')
        (workspace/'services/api/requirements.txt').write_text('fastapi==0.115.12\n',encoding='utf-8')
        (workspace/'services/api/.python-version').write_text('3.12\n',encoding='utf-8')
        # Deliberately no inherited HOME, tokens, proxy credentials, or app config.
        # Python is supplied by CI; uv may download packages, never interpreters.
        env={'PATH':os.environ.get('PATH',''),'CI':'1','NO_COLOR':'1','PYTHONUTF8':'1',
             'VERCEL_TELEMETRY_DISABLED':'1','DO_NOT_TRACK':'1','VERCEL_ENV':'production',
             'VERCEL_URL':'buyeros-ci-fixture.vercel.app','UV_NO_CONFIG':'1',
             'UV_PYTHON_DOWNLOADS':'never','UV_CACHE_DIR':str(fixture/'uv-cache'),
             'npm_config_userconfig':str(fixture/'empty.npmrc'),
             'npm_config_globalconfig':str(fixture/'empty-global.npmrc'),
             'npm_config_cache':str(fixture/'npm-cache'),'TMPDIR':str(fixture/'tmp')}
        # Parent boundary prevents resolveProjectCwd walking to another project.
        (fixture/'.git').mkdir()
        argv=['node',str(cli),'build','--prod','--global-config',str(fixture/'global-config')]
        report['phase']='services_build'
        with (fixture/'build.log').open('w',encoding='utf-8') as log:
            process=subprocess.Popen(argv,cwd=workspace,env=env,stdout=log,stderr=subprocess.STDOUT,
                                     start_new_session=True)
            try:code=process.wait(timeout=780)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
                code=124
        report['exit_code']=code
        if code:
            report['failure']='build_failed' if code!=124 else 'build_timeout'
            report['build_log_tail']=(fixture/'build.log').read_text(encoding='utf-8',errors='replace')[-4000:]
            return report
        output=workspace/'.vercel/output'
        report['phase']='root_config_validation'
        root=json.loads((output/'config.json').read_text())
        assert root.get('version')==3
        report['phase']='build_metadata_validation'
        builds=json.loads((output/'builds.json').read_text())
        assert builds.get('target')=='production' and builds.get('cliVersion')=='54.17.2'
        assert not builds.get('error') and not any(build.get('error') for build in builds.get('builds',[]))
        report['phase']='route_binding_validation'
        assert any(route.get('destination',{}).get('service')=='app'
                   for route in root.get('routes',[]) if isinstance(route.get('destination'),dict))
        services={service['name']:service for service in root.get('services',[])}
        assert set(services)=={'app','api'} and services['app'].get('bindings')==[binding]
        report['service_outputs']={}
        for name,expected_runtime in [('app','nodejs24.x'),('api','python3.12')]:
            report['phase']='app_output_validation' if name=='app' else 'api_output_validation'
            service_dir=output/'services'/name
            config=json.loads((service_dir/'config.json').read_text())
            assert config.get('version')==3 and config.get('routes')
            functions=[json.loads(path.read_text()) for path in service_dir.rglob('.vc-config.json')]
            assert functions and any(value.get('runtime')==expected_runtime and value.get('handler') for value in functions)
            report['service_outputs'][name]={'function_count':len(functions),'runtime':expected_runtime}
        report['passed']=True
        report['phase']='complete'
        return report
    except Exception:
        report['failure']='harness_or_output_validation_failed'
        return report
    finally:
        report['elapsed_seconds']=round(time.monotonic()-started,2)
        # Never clean a computed path until its exact parent/name/symlink bounds pass.
        if (fixture.parent!=parent or not fixture.name.startswith('buyeros-services-ci-')
                or fixture==checkout or fixture.is_relative_to(checkout) or fixture.is_symlink()
                or fixture.resolve()!=fixture):
            raise ValueError('fixture cleanup boundary invalid')
        shutil.rmtree(fixture)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli-package',type=Path,required=True)
    parser.add_argument('--output-report',type=Path)
    args=parser.parse_args()
    try:report=check(args.cli_package)
    except Exception:
        report={'schema':'buyeros.services-build-check.v1','passed':False,'phase':'preflight_or_cleanup',
                'failure':'harness_or_output_validation_failed'}
    if args.output_report:write_json(args.output_report,report)
    print(json.dumps(report))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
