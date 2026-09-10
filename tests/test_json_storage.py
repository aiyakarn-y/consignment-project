import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import app as service
from backend.repository import JsonTransaction, WriteConflict, STATE_KEY
from backend.storage import LocalFileStore
from test_operations import profile, upload, excel


@pytest.fixture
def json_client(tmp_path, monkeypatch):
    monkeypatch.setattr(service, 'DATA', tmp_path)
    monkeypatch.setattr(service, 'DB', tmp_path/'must-not-exist.sqlite3')
    monkeypatch.setattr(service, 'STATE_DRIVER', 'json')
    monkeypatch.setattr(service, 'STORAGE_DRIVER', 'local')
    with TestClient(service.app) as client: yield client
    assert not list(tmp_path.rglob('*.sqlite3'))
    assert not list(tmp_path.rglob('*.db'))


def test_json_import_edit_export_restart_restore(json_client, tmp_path):
    c=json_client
    cfg=c.post('/api/profiles',json={'config':profile()}).json()
    batch=c.post('/api/batches',json={}).json();url='/api/batches/'+batch['id']
    assert upload(c,url,profile_id=cfg['id']).status_code==200
    rows=c.get(url+'/rows').json()['rows'];row=rows[0]
    response=c.patch(url+'/rows/'+row['id'],json={'discount':'10%'})
    assert response.status_code==200,response.text
    assert c.get(url+'/rows').json()['rows'][0]['calculated_net']=='192.6'
    exported=c.get(url+'/export');assert exported.status_code==200,exported.text
    import io,openpyxl
    w=openpyxl.load_workbook(io.BytesIO(exported.content))
    assert list(w.active.values)[0]==('Items','Price','Qty','Discount')
    assert list(w.active.values)[1]==('NEW-SKU',107,2,'10.00%')
    w.close()
    state=json.loads((tmp_path/STATE_KEY).read_text())
    assert state['tables']['batches'][batch['id']]['rows'][0]['discount']=='10%'
    fresh=JsonTransaction(LocalFileStore(tmp_path))
    assert fresh.get('batches',batch['id'])['rows'][0]['discount']=='10%'
    backup=c.post('/api/backups');assert backup.status_code==200,backup.text
    archive=c.get('/api/backups/file/'+backup.json()['name']).content
    assert c.delete('/api/batches').status_code==200
    assert c.get('/api/batches').json()==[]
    preview=c.post('/api/backups/preview',files={'file':('backup.zip',archive)}).json()
    restored=c.post('/api/backups/restore',files={'file':('backup.zip',archive)},data={'confirm':'true','archive_hash':preview['archive_hash']})
    assert restored.status_code==200,restored.text
    assert c.get(url+'/export').status_code==200
    assert c.delete('/api/history?confirm=true').status_code==200
    assert c.get('/api/import-history?page=1&size=20').json()['total']==0
    assert c.get('/api/export-history').json()==[]
    assert c.get(url+'/rows').json()['rows'][0]['discount']=='10%'


def test_compare_and_swap_rejects_lost_update(tmp_path):
    store=LocalFileStore(tmp_path)
    first=JsonTransaction(store);stale=JsonTransaction(store)
    first.put('rules','shop','10%');first.commit()
    stale.put('rules','shop','20%')
    with pytest.raises(WriteConflict):stale.commit()
    assert JsonTransaction(store).get('rules','shop')=='10%'
    a=JsonTransaction(store);b=JsonTransaction(store)
    a.put('rules','shop','30%');a.commit()
    b.clear('rules')
    with pytest.raises(WriteConflict):b.commit()
    assert JsonTransaction(store).get('rules','shop')=='30%'


def test_http_commit_conflict_returns_409_without_partial_tables(json_client, tmp_path, monkeypatch):
    c=json_client
    c.post('/api/batches',json={})
    before=(tmp_path/STATE_KEY).read_bytes()
    def conflict(*args):raise WriteConflict('simulated concurrent writer')
    monkeypatch.setattr(LocalFileStore,'compare_and_swap',conflict)
    response=c.post('/api/profiles',json={'config':profile()})
    assert response.status_code==409,response.text
    assert (tmp_path/STATE_KEY).read_bytes()==before


def test_json_cleanup_failure_remains_retryable(json_client,tmp_path,monkeypatch):
    c=json_client
    cfg=c.post('/api/profiles',json={'config':profile()}).json()
    b=c.post('/api/batches',json={}).json();url='/api/batches/'+b['id']
    upload(c,url,profile_id=cfg['id'])
    key=c.get(url).json()['files'][0]['path']
    original=LocalFileStore.delete
    def fail(store,path):raise OSError('temporary disk failure')
    monkeypatch.setattr(LocalFileStore,'delete',fail)
    assert c.delete('/api/batches').status_code==200
    assert c.get('/api/batches').json()==[]
    assert (tmp_path/key).exists()
    assert key in JsonTransaction(LocalFileStore(tmp_path)).table('file_cleanup')
    monkeypatch.setattr(LocalFileStore,'delete',original)
    assert c.post('/api/storage/cleanup').status_code==200
    assert not (tmp_path/key).exists()
    assert JsonTransaction(LocalFileStore(tmp_path)).items('file_cleanup')==[]


def test_failed_import_does_not_commit_partial_json(json_client, tmp_path):
    c=json_client
    cfg=c.post('/api/profiles',json={'config':profile()}).json()
    b=c.post('/api/batches',json={}).json();url='/api/batches/'+b['id']
    before=(tmp_path/STATE_KEY).read_bytes()
    result=c.post(url+'/upload',data={'profile_id':cfg['id']},files=[('files',('ok.xlsx',excel())),('files',('broken.xlsx',b'broken'))])
    assert result.status_code==400
    assert (tmp_path/STATE_KEY).read_bytes()==before
    assert c.get(url).json()['rows']==0


def test_backup_from_sqlite_restores_into_json(tmp_path, monkeypatch):
    sqlite_root=tmp_path/'sqlite';sqlite_root.mkdir()
    monkeypatch.setattr(service,'DATA',sqlite_root);monkeypatch.setattr(service,'DB',sqlite_root/'original.sqlite3')
    monkeypatch.setattr(service,'STATE_DRIVER','sqlite')
    with TestClient(service.app) as c:
        cfg=c.post('/api/profiles',json={'config':profile()}).json()
        b=c.post('/api/batches',json={}).json();url='/api/batches/'+b['id']
        assert upload(c,url,profile_id=cfg['id']).status_code==200
        exported=c.get(url+'/export')
        name=c.post('/api/backups').json()['name'];archive=c.get('/api/backups/file/'+name).content
    before=(sqlite_root/'original.sqlite3').read_bytes()
    monkeypatch.setattr(service,'DATA',tmp_path/'json');monkeypatch.setattr(service,'STATE_DRIVER','json')
    with TestClient(service.app) as c:
        preview=c.post('/api/backups/preview',files={'file':('a.zip',archive)}).json()
        result=c.post('/api/backups/restore',files={'file':('a.zip',archive)},data={'confirm':'true','archive_hash':preview['archive_hash']})
        assert result.status_code==200,result.text
        assert c.get(url+'/rows').json()['rows'][0]['sku']=='NEW-SKU'
        history=c.get('/api/export-history').json()
        assert c.get('/api/export-history/'+history[0]['id']+'/file').content==exported.content
    assert (sqlite_root/'original.sqlite3').read_bytes()==before
