import gzip,hashlib,json,zlib
from urllib.parse import unquote
import httpx
import pytest
from fastapi.testclient import TestClient
from backend import app as service
from backend.blob_storage import BlobFileStore
from backend.repository import JsonTransaction,WriteConflict,STATE_KEY
from test_operations import profile,upload,excel


@pytest.mark.parametrize('encoding,compress', [('gzip', gzip.compress), ('deflate', zlib.compress), ('identity', lambda data: data)])
def test_blob_decodes_response_once_and_preserves_etag(encoding, compress):
    payload = b'{"format":"consignment-json","version":1,"revision":0,"tables":{}}'
    wire = compress(payload)
    def handle(request):
        return httpx.Response(200, headers={
            'content-encoding': encoding, 'content-length': str(len(wire)),
            'etag': '"original-version"', 'content-type': 'application/json',
        }, stream=httpx.ByteStream(wire))
    store = BlobFileStore(token='vercel_blob_rw_TestStore_fixture', prefix='test', transport=httpx.MockTransport(handle))
    data, etag = store.read_version(STATE_KEY)
    assert data == payload
    assert etag == '"original-version"'
    with pytest.raises(OSError, match='size limit'):
        store.request('GET', 'https://vercel.com/api/blob', max_bytes=len(payload)-1)


class FakeBlob:
    def __init__(self): self.objects={};self.requests=[]
    def handle(self,r):
        self.requests.append(r)
        assert r.headers['authorization']=='Bearer vercel_blob_rw_TestStore_fixture'
        if r.url.host.endswith('.private.blob.vercel-storage.com'):
            assert r.url.params['cache']=='0'
            key=unquote(r.url.path).lstrip('/')
            if key not in self.objects:return httpx.Response(404)
            data=self.objects[key]
            return httpx.Response(200,content=data,headers={'etag':hashlib.sha256(data).hexdigest()})
        assert r.url.host=='vercel.com'
        if r.method=='PUT':
            key=r.url.params['pathname'];old=self.objects.get(key)
            assert r.headers['x-vercel-blob-access']=='private'
            assert r.headers['x-add-random-suffix']=='0'
            etag=hashlib.sha256(old).hexdigest() if old is not None else None
            if r.headers.get('x-if-match'):
                if r.headers['x-if-match']!=etag:return httpx.Response(412)
            elif old is not None:
                assert r.headers['x-allow-overwrite']=='0'
                return httpx.Response(409)
            self.objects[key]=r.read();return httpx.Response(200,json={'pathname':key})
        if r.url.path.endswith('/delete'):
            for key in json.loads(r.read())['urls']:self.objects.pop(key,None)
            return httpx.Response(200,json={})
        if 'url' in r.url.params:
            key=r.url.params['url']
            return httpx.Response(200,json={'pathname':key}) if key in self.objects else httpx.Response(404)
        prefix=r.url.params['prefix']
        return httpx.Response(200,json={'blobs':[{'pathname':k,'size':len(v)} for k,v in self.objects.items() if k.startswith(prefix)],'hasMore':False})
    def store(self):return BlobFileStore(token='vercel_blob_rw_TestStore_fixture',prefix='isolated-test',transport=httpx.MockTransport(self.handle))


class EncodedBlob(FakeBlob):
    """Delivery compression has a different validator from the stored object."""
    def handle(self, request):
        response = super().handle(request)
        if request.url.host.endswith('.private.blob.vercel-storage.com') and response.status_code == 200:
            if request.headers.get('accept-encoding') != 'identity':
                return httpx.Response(200, headers={
                    'etag': 'W/"compressed-representation"', 'content-encoding': 'gzip',
                }, stream=httpx.ByteStream(gzip.compress(response.content)))
        return response


def test_blob_versioned_writes_use_original_representation():
    fake = EncodedBlob()
    store = fake.store()
    first = JsonTransaction(store)
    first.put('rules', 'A', '10%'); first.commit()
    stale = JsonTransaction(store)
    current = JsonTransaction(store)
    current.put('rules', 'A', '20%'); current.commit()
    assert JsonTransaction(store).get('rules', 'A') == '20%'
    stale.put('rules', 'A', '30%')
    with pytest.raises(WriteConflict): stale.commit()


def test_blob_conditional_state_and_private_reads():
    fake=FakeBlob();store=fake.store()
    a=JsonTransaction(store);b=JsonTransaction(store)
    a.put('rules','A','10%');a.commit()
    b.put('rules','A','20%')
    with pytest.raises(WriteConflict):b.commit()
    assert JsonTransaction(store).get('rules','A')=='10%'
    a=JsonTransaction(store);a.put('rules','A','15%');a.commit()
    assert JsonTransaction(store).get('rules','A')=='15%'
    assert all(k.startswith('isolated-test/') for k in fake.objects)


@pytest.mark.parametrize('blob_type', [FakeBlob, EncodedBlob])
def test_blob_api_import_export_without_local_asset_paths(tmp_path,monkeypatch,blob_type):
    fake=blob_type()
    monkeypatch.setattr(service,'STATE_DRIVER','json');monkeypatch.setattr(service,'STORAGE_DRIVER','vercel_blob')
    monkeypatch.setattr(service,'DATA',tmp_path)
    monkeypatch.setattr(service,'storage',fake.store)
    with TestClient(service.app) as c:
        cfg=c.post('/api/profiles',json={'config':profile()}).json()
        b=c.post('/api/batches',json={}).json();url='/api/batches/'+b['id']
        result=upload(c,url,profile_id=cfg['id']);assert result.status_code==200,result.text
        response=c.get(url+'/export',headers={'X-Consign-Fetch':'1'})
        assert response.status_code==200,response.text
        assert response.headers['X-Consign-Download']=='1'
        assert response.headers['X-Exported-Rows']=='1'
        assert response.json()['download'].startswith('/cloud-download?ticket=')
        assert len(c.get('/api/export-history').json())==1
        assert c.delete('/api/history?confirm=true').status_code==200
        assert len(c.get('/api/export-history').json())==0
        archive=c.post('/api/backups');assert archive.status_code==200,archive.text
        assert len(c.get('/api/backups').json())==1
        assert c.delete('/api/batches').status_code==200
        assert not any('/imports/' in k for k in fake.objects)
        second = c.post('/api/batches', json={}).json()
        second_url = '/api/batches/'+second['id']
        assert upload(c,second_url,profile_id=cfg['id']).status_code==200
        file_id = c.get(second_url).json()['files'][0]['id']
        assert c.delete(second_url+'/files/'+file_id).status_code==200
        assert c.get(second_url).json()['files']==[]
        assert not list(tmp_path.rglob('*.db'))
        assert not list(tmp_path.rglob('*.xlsx'))


def test_staged_multipart_rehydrates_and_rejects_arbitrary_keys(monkeypatch):
    fake=FakeBlob();monkeypatch.setattr(service,'STATE_DRIVER','json');monkeypatch.setattr(service,'STORAGE_DRIVER','vercel_blob');monkeypatch.setattr(service,'storage',fake.store)
    req=httpx.Request('POST','http://unused',files={'file':('sheet.xlsx',excel())})
    content=req.read();key='staging/'+'a'*32;fake.store().write(key,content)
    with TestClient(service.app) as c:
        response=c.post('/api/profiles/inspect',headers={'X-Consign-Upload':key,'Content-Type':req.headers['content-type']})
        assert response.status_code==200,response.text
        assert response.json()['sheet']=='Sales'
        assert 'isolated-test/'+key not in fake.objects
        response=c.post('/api/profiles/inspect',headers={'X-Consign-Upload':'state/system.json','Content-Type':req.headers['content-type']})
        assert response.status_code==400


def test_blob_errors_do_not_expose_token():
    store=BlobFileStore(token='vercel_blob_rw_TestStore_fixture',prefix='test',transport=httpx.MockTransport(lambda r:httpx.Response(403)))
    with pytest.raises(OSError) as error:store.read(STATE_KEY)
    assert 'vercel_blob_rw' not in str(error.value)
    for key in ['../state','https://other/a','/root','a\\b']:
        with pytest.raises(ValueError):store.read(key)


@pytest.mark.parametrize('failure', ['before', 'after', 'after_read_failure', 'timeout', 'competing', 'persistent', 'forbidden'])
@pytest.mark.parametrize('existing', [False, True])
def test_blob_put_recovers_temporary_failure_without_overwriting(monkeypatch, failure, existing):
    monkeypatch.setattr('backend.blob_storage.time.sleep', lambda _: None)
    fake=FakeBlob(); base=fake.store()
    if existing:base.write(STATE_KEY,b'old')
    _,etag=base.read_version(STATE_KEY)
    attempts=[]
    read_failed=False
    def handle(request):
        nonlocal read_failed
        if failure=='after_read_failure' and request.method=='GET' and attempts and not read_failed:
            read_failed=True
            return httpx.Response(503)
        if request.method=='PUT':
            attempts.append(request.headers.get('x-if-match'))
            if failure=='forbidden':return httpx.Response(403)
            if failure=='persistent':return httpx.Response(503)
            if len(attempts)==1:
                if failure in ('after','after_read_failure'):fake.handle(request)
                if failure=='competing':fake.objects['isolated-test/'+STATE_KEY]=b'other writer'
                if failure=='timeout':raise httpx.ReadTimeout('fixture')
                return httpx.Response(503)
        return fake.handle(request)
    store=BlobFileStore(token=base.token,prefix=base.prefix,transport=httpx.MockTransport(handle))
    if failure=='competing':
        with pytest.raises(WriteConflict):store.compare_and_swap(STATE_KEY,b'new',etag)
        assert base.read(STATE_KEY)==b'other writer'
    elif failure in ('persistent','forbidden'):
        with pytest.raises(OSError):store.compare_and_swap(STATE_KEY,b'new',etag)
        assert base.read_version(STATE_KEY)[0]==(b'old' if existing else None)
        assert len(attempts)==(3 if failure=='persistent' else 1)
    else:
        store.compare_and_swap(STATE_KEY,b'new',etag)
        assert base.read(STATE_KEY)==b'new'
        assert len(attempts)==(1 if failure=='after' else 2)
    assert all(value==etag for value in attempts)


@pytest.mark.parametrize('status', [429, 500, 502, 503, 504])
@pytest.mark.parametrize('committed', [False, True])
def test_export_recovers_blob_failure_once(monkeypatch, status, committed):
    monkeypatch.setattr('backend.blob_storage.time.sleep', lambda _: None)
    fake=FakeBlob(); fault={'enabled':False, 'count':0}
    def handle(request):
        if request.method=='PUT' and request.url.params.get('pathname','').endswith('/'+STATE_KEY) and fault['enabled']:
            fault['enabled']=False;fault['count']+=1
            if committed:fake.handle(request)
            return httpx.Response(status)
        return fake.handle(request)
    store=BlobFileStore(token='vercel_blob_rw_TestStore_fixture',prefix='isolated-test',transport=httpx.MockTransport(handle))
    monkeypatch.setattr(service,'STATE_DRIVER','json')
    monkeypatch.setattr(service,'STORAGE_DRIVER','vercel_blob')
    monkeypatch.setattr(service,'storage',lambda:store)
    with TestClient(service.app) as client:
        cfg=client.post('/api/profiles',json={'config':profile()}).json()
        batch=client.post('/api/batches',json={}).json()
        url='/api/batches/'+batch['id']
        assert upload(client,url,profile_id=cfg['id']).status_code==200
        fault['enabled']=True
        result=client.get(url+'/export',headers={'X-Consign-Fetch':'1'})
        assert result.status_code==200,result.text
        assert fault['count']==1
        history=client.get('/api/export-history').json()
        assert len(history)==1
        assert sum('/exports/' in key for key in fake.objects)==1
        import io,openpyxl
        workbook=openpyxl.load_workbook(io.BytesIO(store.read(history[0]['path'])))
        assert workbook.active.cell(2,1).value=='NEW-SKU'
