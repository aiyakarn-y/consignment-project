import io
from pathlib import Path
from unittest.mock import patch
import pytest
from backend import app as service
from test_grouping import client
from test_operations import excel,profile,upload


def test_import_export_paths_and_clear_preserves_export(client):
    p=client.post('/api/profiles',json={'config':profile()}).json()
    batch=client.post('/api/batches',json={}).json();url='/api/batches/'+batch['id']
    assert upload(client,url,profile_id=p['id']).status_code==200
    f=client.get(url).json()['files'][0]
    assert f['path'].startswith('imports/'+batch['id']+'/')
    exported=client.get(url+'/export');assert exported.status_code==200
    record=client.get('/api/export-history').json()[0]
    assert record['path'].startswith('exports/')
    result=client.delete('/api/batches');assert result.status_code==200
    assert not (service.DATA/f['path']).exists()
    assert client.get('/api/export-history/'+record['id']+'/file').content==exported.content
    assert client.get('/api/import-history').json()[0]['source_available'] is False


def test_clear_unlink_failure_does_not_resurrect_batch(client):
    p=client.post('/api/profiles',json={'config':profile()}).json()
    batch=client.post('/api/batches',json={}).json();url='/api/batches/'+batch['id']
    upload(client,url,profile_id=p['id']);f=client.get(url).json()['files'][0]
    original=Path.unlink
    def fail(path,*a,**kw):
        if path==service.DATA/f['path']:raise OSError('simulated disk failure')
        return original(path,*a,**kw)
    with patch.object(Path,'unlink',fail):
        result=client.delete('/api/batches')
    assert result.status_code==200 and result.json()['cleanup_pending']==1
    assert client.get('/api/batches').json()==[]
    assert (service.DATA/f['path']).exists()
    assert client.post('/api/storage/cleanup').json()['remaining']==0
    assert not (service.DATA/f['path']).exists()


def legacy_copy(client, folder):
    """Create the legacy flat layout with a populated database for compatibility tests."""
    import sqlite3,json,shutil
    from backend.operations import TABLES
    folder.mkdir()
    with service.db() as current:
        with sqlite3.connect(folder/'demo.sqlite3') as legacy:
            current.backup(legacy)
            for table in ('batches','export_history'):
                for key,body in legacy.execute(f'SELECT id,body FROM {table}').fetchall():
                    obj=json.loads(body)
                    files=obj['files'] if table=='batches' else [obj]
                    for f in files:
                        old=service.DATA/f['path'];f['path']=old.name
                        (folder/f['path']).write_bytes(old.read_bytes())
                    legacy.execute(f'UPDATE {table} SET body=? WHERE id=?',(json.dumps(obj,ensure_ascii=False),key))
    return folder


def test_legacy_migration_and_backup_restore(client,tmp_path):
    import importlib.util,json,sqlite3,hashlib
    p=client.post('/api/profiles',json={'config':profile()}).json()
    b=client.post('/api/batches',json={}).json();url='/api/batches/'+b['id']
    upload(client,url,profile_id=p['id']);exported=client.get(url+'/export').content
    source=legacy_copy(client,tmp_path/'legacy')
    before=(source/'demo.sqlite3').read_bytes()
    spec=importlib.util.spec_from_file_location('migration',Path('scripts/migrate-demo.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    dest=tmp_path/'new'
    report=module.migrate(source,dest)
    assert report['rows']==1 and report['referenced_files']==2 and report['business_records_preserved']
    assert (source/'demo.sqlite3').read_bytes()==before
    with sqlite3.connect(dest/'database/consignment-system.sqlite3') as c:
        restored=json.loads(c.execute('SELECT body FROM batches').fetchone()[0])
        assert restored['id']==b['id'] and restored['files'][0]['path'].startswith('imports/')
        assert c.execute('PRAGMA user_version').fetchone()[0]==2
    assert next((dest/'exports').glob('*.xlsx')).read_bytes()==exported
    archive=(dest/report['migration_backup']).read_bytes()
    preview=client.post('/api/backups/preview',files={'file':('legacy.zip',archive)})
    assert preview.status_code==200 and preview.json()['summary']['rows']==1
    restored=client.post('/api/backups/restore',files={'file':('legacy.zip',archive)},data={'confirm':'true','archive_hash':hashlib.sha256(archive).hexdigest()})
    assert restored.status_code==200,restored.text
    assert client.get(url+'/rows').json()['rows'][0]['sku']=='NEW-SKU'
    h=client.get('/api/export-history').json()[0]
    assert client.get('/api/export-history/'+h['id']+'/file').content==exported
    with pytest.raises(FileExistsError):module.migrate(source,dest)


def test_store_atomic_failure_and_traversal(tmp_path):
    from backend.storage import LocalFileStore
    store=LocalFileStore(tmp_path);store.prepare()
    with pytest.raises(ValueError):store.write('../outside.xlsx',b'bad')
    key='exports/'+'a'*32+'.xlsx'
    def partial(path):
        path.write_bytes(b'partial')
        raise OSError('Disk failure')
    with pytest.raises(OSError):store.write_from(key,partial)
    assert not store.exists(key) and not list((tmp_path/'temp').iterdir())
    store.write(key,b'complete')
    with pytest.raises(FileExistsError):store.write(key,b'overwrite')
    assert store.read(key)==b'complete'
