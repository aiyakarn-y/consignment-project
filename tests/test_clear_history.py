from copy import deepcopy
from test_grouping import client
from test_operations import profile, upload
from backend import app as service


def test_clear_history_preserves_data_files_and_stays_empty(client):
    cfg=client.post('/api/profiles',json={'config':profile()}).json()
    batch=client.post('/api/batches',json={}).json();url='/api/batches/'+batch['id']
    assert upload(client,url,profile_id=cfg['id']).status_code==200
    assert client.get(url+'/export').status_code==200
    before=deepcopy(service.load(batch['id']))
    exports=client.get('/api/export-history').json()
    paths=[f['path'] for f in before['files']]+[e['path'] for e in exports]
    contents={p:service.storage().path(p).read_bytes() for p in paths}
    assert client.delete('/api/history').status_code==400
    assert len(client.get('/api/export-history').json())==1
    result=client.delete('/api/history?confirm=true')
    assert result.status_code==200
    assert result.json()=={'cleared_imports':1,'cleared_exports':1}
    after=service.load(batch['id'])
    assert after['rows']==before['rows']
    assert client.get('/api/profiles').json()[0]['id']==cfg['id']
    service.save(after)
    for _ in range(2):
        assert client.get('/api/import-history').json()==[]
        assert client.get('/api/export-history').json()==[]
    assert {p:service.storage().path(p).read_bytes() for p in paths}==contents
    assert client.get('/api/export-history/'+exports[0]['id']+'/file').status_code==404
    assert client.delete('/api/history?confirm=true').json()=={'cleared_imports':0,'cleared_exports':0}
    assert client.get(url+'/export').headers['X-Previous-Identical-Exports']=='0'
    assert len(client.get('/api/export-history').json())==1
    other=client.post('/api/batches',json={}).json()
    assert upload(client,'/api/batches/'+other['id'],profile_id=cfg['id'],allow_duplicate='true').status_code==200
    assert len(client.get('/api/import-history').json())==1


def test_clear_failure_rolls_back_registry_and_batch_flags(client):
    import pytest
    cfg=client.post('/api/profiles',json={'config':profile()}).json()
    b=client.post('/api/batches',json={}).json();url='/api/batches/'+b['id']
    upload(client,url,profile_id=cfg['id']);client.get(url+'/export')
    before=deepcopy(service.load(b['id']))
    with service.db() as c:
        c.execute("CREATE TRIGGER prevent_history_clear BEFORE DELETE ON export_history BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(Exception,match='test failure'):
        client.delete('/api/history?confirm=true')
    assert service.load(b['id'])==before
    assert len(client.get('/api/import-history').json())==1
    assert len(client.get('/api/export-history').json())==1
