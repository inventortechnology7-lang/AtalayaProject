#!/usr/bin/env python3
"""Restore backup and exercise isolated PostgreSQL schema/import, never legacy volumes."""
import argparse, hashlib, importlib.util, json, pathlib, subprocess, tempfile, time, uuid
root=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('migration',root/'scripts/import-katana.py')
migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
parser=argparse.ArgumentParser();parser.add_argument('--backup',type=pathlib.Path);args=parser.parse_args()
fixture_dir = tempfile.TemporaryDirectory()
if args.backup:
    backup=args.backup.resolve()
else:
    from tests.katana_fixture import create
    backup=pathlib.Path(fixture_dir.name); create(backup)
manifest=json.loads((backup/'manifest.json').read_text())
dump=(backup/'legacy-postgres.dump').read_bytes() if args.backup else None
if dump: assert hashlib.sha256(dump).hexdigest()==manifest['files']['legacy-postgres.dump']['sha256']
name='katana-migration-test-'+uuid.uuid4().hex[:10]
def run(*cmd,input=None):
    return subprocess.run(cmd,input=input,capture_output=True,check=True).stdout

def sql(statement,database='katana'):
    return run('docker','exec','-i',name,'psql','-X','-At','-v','ON_ERROR_STOP=1','-U','katana','-d',database,input=statement.encode()).decode().strip()
try:
    run('docker','run','-d','--name',name,'--network','none','--tmpfs','/var/lib/postgresql/data','-e','POSTGRES_USER=katana','-e','POSTGRES_DB=katana','-e','POSTGRES_PASSWORD=test-only-password','postgres:17-alpine')
    for _ in range(60):
        if subprocess.run(['docker','exec',name,'pg_isready','-U','katana'],capture_output=True).returncode==0: break
        time.sleep(0.5)
    if dump:
        sql('CREATE DATABASE restored;')
        run('docker','exec','-i',name,'pg_restore','--exit-on-error','--no-owner','--no-acl','-U','katana','-d','restored',input=dump)
        print('Legacy PostgreSQL archive restored successfully in isolated database.')
    sql((root/'backend/src/main/resources/db/katana/V1__katana_local.sql').read_text())
    statement,counts=migration.plan(backup)
    sql(statement)
    tables=['devices','doors','door_status','alarms','alarm_history','system_logs','telemetry_samples','users','legacy_records','import_runs']
    def snapshot():
        return {t:sql('SELECT count(*),md5(coalesce(string_agg(r::text,\'\' ORDER BY r::text),\'\')) FROM '+t+' r') for t in tables}
    first=snapshot();sql(statement);assert first==snapshot(),'Import duplicated or modified data'
    if not args.backup:
        assert sql('SELECT value FROM telemetry_samples')=='12.3'
        assert sql("SELECT active FROM alarms WHERE uid='alarm-1'")=='f'
        assert sql("SELECT role FROM users")=='OPERADOR'
        assert sql("SELECT count(*) FROM legacy_records WHERE source_table='ordenes_web'")=='1'
        original=(backup/'katana.db').read_bytes()
        (backup/'katana.db').write_bytes(original+b'tampered')
        try:
            migration.plan(backup)
            raise AssertionError('Tampered backup accepted')
        except ValueError:
            pass
        (backup/'katana.db').write_bytes(original)
    assert sql("SELECT count(*) FROM users WHERE password_hash IS NOT NULL OR NOT reset_required")=='0'
    assert sql('SELECT count(*) FROM devices WHERE connected')=='0'
    assert sql("SELECT count(*) FROM legacy_records WHERE payload ? 'sal' OR payload ? 'clave'")=='0'
    print('Source counts verified:',json.dumps(counts))
    print('Idempotent full row snapshots:',json.dumps(first))
    print('Password reset, no stale connections, and no copied password hashes: verified.')
finally:
    subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    fixture_dir.cleanup()
