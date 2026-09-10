import io,json,zipfile,hashlib
from copy import deepcopy
from functools import lru_cache
import openpyxl
from backend import app as service
from backend.core import row,validate
from test_grouping import client,seed


@lru_cache(maxsize=1)
def excel():
    w=openpyxl.Workbook();s=w.active;s.title='Sales';s.append(['Reference','Units','Sale','Cost','Total','Cost total','MG'])
    s.append(['NEW-SKU',2,107,101,214,202,5.61]);b=io.BytesIO();w.save(b);return b.getvalue()

def profile():return dict(name='New branch',sheet='Sales',header_row=1,columns={'sku':'A','qty':'B','price':'C','cost_price':'D','gross':'E','cost_total':'F','mg':'G'},customer='New shop',discount_mode='auto',net_source='cost',expected_headers={'A':'Reference','B':'Units','C':'Sale','D':'Cost','E':'Total','F':'Cost total','G':'MG'})

def upload(client,url,**data):return client.post(url+'/upload',files={'files':('new.xlsx',excel())},data=data)

def test_profile_inspect_preview_versioned_import(client):
    content=excel();i=client.post('/api/profiles/inspect',files={'file':('new.xlsx',content)}).json()
    assert i['sheet']=='Sales' and i['columns'][0]['label']=='Reference'
    p=client.post('/api/profiles',json={'config':profile()});assert p.status_code==200,p.text
    cfg=p.json();preview=client.post('/api/profiles/preview',files={'file':('new.xlsx',content)},data={'config':json.dumps(profile())})
    assert preview.status_code==200 and preview.json()['ready']==1
    b=client.post('/api/batches',json={}).json();url='/api/batches/'+b['id']
    result=upload(client,url,profile_id=cfg['id']);assert result.status_code==200,result.text
    r=client.get(url+'/rows').json()['rows'][0]
    assert r['sku']=='NEW-SKU' and r['source_cost_price']=='101' and r['source_cost_total']=='202' and r['calculated_net']=='202'
    assert r['source_gp'] is None and r['source_mg']=='5.61%'
    updated=client.post('/api/profiles',json={'id':cfg['id'],'config':dict(profile(),name='Version 2')}).json()
    assert updated['version']==2
    assert service.load(b['id'])['files'][0]['profile_snapshot']['version']==1


def test_valuation_applies_without_changing_export_prices(client):
    cfg=client.post('/api/profiles',json={'config':profile()}).json();b=client.post('/api/batches',json={}).json();url='/api/batches/'+b['id'];upload(client,url,profile_id=cfg['id'])
    assert client.get(url+'/below-cost').json()['rows']==0
    settings=dict(sale_basis='included',cost_basis='excluded',settlement_basis='excluded',vat_rate='7',note='Confirmed')
    result=client.post('/api/valuations',json={'customer':'New shop','settings':settings,'batch_id':b['id']});assert result.status_code==200,result.text
    r=client.get(url+'/rows').json()['rows'][0]
    assert r['price']=='107' and r['source_cost_price']=='101' and r['comparison_sale_price']=='100'
    assert r['comparison_basis']=='ex_vat' and r['below_cost_difference']=='2'
    assert client.get(url+'/below-cost').json()['groups'][0]['after_discount_difference']=='0'
    assert client.get(url+'/export').status_code==200


def test_cross_batch_duplicates_export_history_and_clear(client):
    cfg=client.post('/api/profiles',json={'config':profile()}).json();b=client.post('/api/batches',json={}).json();url='/api/batches/'+b['id'];upload(client,url,profile_id=cfg['id'])
    first=client.get(url+'/export');assert first.status_code==200
    assert first.headers['x-previous-identical-exports']=='0'
    again=client.get(url+'/export');assert again.headers['x-previous-identical-exports']=='1'
    history=client.get('/api/export-history').json();assert len(history)==2
    assert client.get('/api/export-history/'+history[0]['id']+'/file').content==again.content
    b2=client.post('/api/batches',json={}).json();u2='/api/batches/'+b2['id']
    assert upload(client,u2,profile_id=cfg['id']).status_code==409
    check=client.post(u2+'/check-upload',files={'files':('renamed.xlsx',excel())}).json()
    assert check[0]['previous'][0]['batch_id']==b['id']
    assert upload(client,u2,profile_id=cfg['id'],allow_duplicate='true').status_code==200
    assert upload(client,u2,profile_id=cfg['id'],allow_duplicate='true').status_code==409
    client.delete('/api/batches');assert len(client.get('/api/import-history').json())==2
    assert client.get('/api/export-history/'+history[0]['id']+'/file').status_code==200
    b3=client.post('/api/batches',json={}).json();assert upload(client,'/api/batches/'+b3['id'],profile_id=cfg['id']).status_code==409


def test_backup_restore_roundtrip_and_safety_backup(client):
    cfg=client.post('/api/profiles',json={'config':profile()}).json();b=client.post('/api/batches',json={}).json();url='/api/batches/'+b['id'];upload(client,url,profile_id=cfg['id'])
    client.get(url+'/export');client.post('/api/valuations',json={'customer':'New shop','batch_id':b['id'],'settings':{'sale_basis':'included','cost_basis':'excluded','settlement_basis':'excluded'}})
    row_id=client.get(url+'/rows').json()['rows'][0]['id']
    assert client.post(url+'/rows/'+row_id+'/confirm-below-cost',json={'confirmed_by':'Confirmed Sales','reason':'Clearance','vat_basis':'Compared ex VAT','comparable':True}).status_code==200
    backup=client.post('/api/backups');assert backup.status_code==200,backup.text
    data=client.get('/api/backups/file/'+backup.json()['name']).content
    preview=client.post('/api/backups/preview',files={'file':('saved.zip',data)});assert preview.status_code==200,preview.text
    assert preview.json()['summary']['rows']==1 and preview.json()['summary']['exports']==1
    client.delete('/api/batches')
    restore=client.post('/api/backups/restore',files={'file':('saved.zip',data)},data={'archive_hash':preview.json()['archive_hash'],'confirm':'true'})
    assert restore.status_code==200,restore.text
    assert len(client.get('/api/batches').json())==1
    r=client.get(url+'/rows').json()['rows'][0];assert r['sku']=='NEW-SKU' and r['below_cost_status']=='confirmed' and r['below_cost_confirmation']['confirmed_by']=='Confirmed Sales'
    f=client.get(url).json()['files'][0];assert client.get(url+'/files/'+f['id']).content==excel()
    assert client.get('/api/backups/file/'+restore.json()['safety_backup']).status_code==200
    assert len(client.get('/api/profiles').json())==1 and len(client.get('/api/valuations').json())==1
    assert client.post('/api/backups').status_code==200


def test_bad_restore_rejected_without_mutation(client):
    b=client.post('/api/batches',json={}).json();backup=client.post('/api/backups').json();data=client.get('/api/backups/file/'+backup['name']).content
    before=deepcopy(client.get('/api/batches').json())
    source=zipfile.ZipFile(io.BytesIO(data));out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name in source.namelist():z.writestr(name,source.read(name))
        z.writestr('../outside.txt','escape')
    corrupt=out.getvalue()
    assert client.post('/api/backups/preview',files={'file':('bad.zip',corrupt)}).status_code==400
    assert client.post('/api/backups/restore',files={'file':('bad.zip',corrupt)},data={'confirm':'true','archive_hash':hashlib.sha256(corrupt).hexdigest()}).status_code==400
    assert client.post('/api/backups/restore',files={'file':('valid.zip',data)},data={'confirm':'true','archive_hash':'wrong'}).status_code==409
    assert client.get('/api/batches').json()==before


def test_profile_rejects_bad_mapping_and_amount_discount(client):
    assert client.post('/api/profiles',json={'config':dict(profile(),columns={'qty':'B'})}).status_code==400
    w=openpyxl.Workbook();s=w.active;s.title='Sales';s.append(['SKU','Qty','Price','Reduction']);s.append(['SKU',2,100,30]);buf=io.BytesIO();w.save(buf)
    cfg=dict(profile(),columns={'sku':'A','qty':'B','price':'C','discount':'D'},discount_mode='amount',net_source='mapped')
    r=client.post('/api/profiles/preview',files={'file':('amount.xlsx',buf.getvalue())},data={'config':json.dumps(cfg)})
    assert r.status_code==200 and r.json()['sample'][0]['discount']=='15%'
    assert r.json()['sample'][0]['calculated_net']=='170'


def test_restore_io_failure_rolls_back_database_and_new_files(client,monkeypatch):
    from pathlib import Path
    cfg=client.post('/api/profiles',json={'config':profile()}).json();b=client.post('/api/batches',json={}).json();url='/api/batches/'+b['id'];upload(client,url,profile_id=cfg['id']);client.get(url+'/export')
    info=client.post('/api/backups').json();data=client.get('/api/backups/file/'+info['name']).content
    before=deepcopy(service.load(b['id']));files_before={str(p.relative_to(service.DATA)) for p in service.DATA.rglob('*') if p.is_file() and p.suffix=='.xlsx'}
    original=Path.write_bytes;counter=0
    def fail_second(path,content):
        nonlocal counter
        if path.parent==service.DATA/'temp' and path.suffix=='.xlsx':
            counter+=1
            if counter==2:raise OSError('test write failure')
        return original(path,content)
    monkeypatch.setattr(Path,'write_bytes',fail_second)
    import pytest
    with pytest.raises(OSError):client.post('/api/backups/restore',files={'file':('saved.zip',data)},data={'confirm':'true','archive_hash':hashlib.sha256(data).hexdigest()})
    assert service.load(b['id'])==before
    assert {str(p.relative_to(service.DATA)) for p in service.DATA.rglob('*') if p.is_file() and p.suffix=='.xlsx'}==files_before
