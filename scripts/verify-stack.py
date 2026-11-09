#!/usr/bin/env python3
"""Build/verify local-only isolated stack. Keeps its named volume for inspection."""
import json, os, pathlib, subprocess, time
root=pathlib.Path(__file__).resolve().parents[1]
os.chdir(root)
env=dict(os.environ,KATANA_WEB_PORT=os.environ.get('KATANA_WEB_PORT','28182'),KATANA_API_PORT=os.environ.get('KATANA_API_PORT','28180'),KATANA_TCP_PORT=os.environ.get('KATANA_TCP_PORT','18300'))
project=os.environ.get('KATANA_TEST_PROJECT','katana-verify')
if project in ('katana-local','atalaya-laptop','atalaya') or not project.startswith('katana-'): raise SystemExit('An isolated katana-* project is required')
compose=['docker','compose','-p',project,'-f','compose.yaml','-f','compose.verify.yaml']
def run(args,**kwargs):return subprocess.run(args,env=env,check=True,**kwargs)
def output(args):return subprocess.check_output(args,env=env).decode().strip()
def counts():return output(compose+['exec','-T','katana-db','psql','-U','katana','-d','katana','-Atc',"SELECT (SELECT count(*) FROM system_logs),(SELECT count(*) FROM alarms),(SELECT count(*) FROM door_events),(SELECT count(*) FROM telemetry_samples)"])
def healthy():
    for _ in range(90):
        rows=[json.loads(line) for line in output(compose+['ps','--format','json']).splitlines() if line]
        if len(rows)==3 and all(r.get('Health')=='healthy' for r in rows): return
        time.sleep(1)
    raise RuntimeError('Stack did not become healthy')
# This destroys only test containers/network, retaining the test volume; no original service is selected.
run(compose+['down'],stdout=subprocess.DEVNULL)
run(compose+['up','-d','--build'])
healthy()
network=json.loads(output(['docker','network','inspect',project+'_default']))[0]
assert network['Internal'] is True,'WAN must be disabled in the verification stack'
env['PANTALLA_ORIGEN']=network['IPAM']['Config'][0]['Gateway']
run(compose+['up','-d','katana-backend'])
healthy()
# Internal bridges may suppress host port publication. On Linux, reach the
# containers through their isolated bridge; do not add an external network.
def address(service):
    container=output(compose+['ps','-q',service])
    info=json.loads(output(['docker','inspect',container]))[0]
    return info['NetworkSettings']['Networks'][project+'_default']['IPAddress']
env['KATANA_EXPECT_EL']='true'
env['KATANA_TEST_URL']='http://'+address('katana-web')+':8080'
env['KATANA_TCP_HOST']=address('katana-backend')
env['KATANA_TCP_PORT']='8300'
env['KATANA_ALLOW_TEST_PORT']='isolated-bridge'
# Non-secret test endpoints for Playwright and repeatable local checks.
pathlib.Path('.katana-test-endpoints.json').write_text(json.dumps({
    key:env[key] for key in ('KATANA_TEST_URL','KATANA_TCP_HOST','KATANA_TCP_PORT')
}))
run(['python3','scripts/smoke-local.py'])
before=counts()
run(compose+['restart','katana-db','katana-backend'])
healthy()
assert counts()==before,'Historical counts changed across restart'
run(['python3','scripts/smoke-local.py'])
run(['npm','test','--prefix','web'])
print('PASS: three healthy services, internal network without WAN, EL bridge, PostgreSQL persistence across restart')
