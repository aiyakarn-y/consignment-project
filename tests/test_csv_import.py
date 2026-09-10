import csv,io,json
import openpyxl
import pytest
from backend.csv_input import csv_workbook
from backend import app as service
from test_grouping import client
from test_operations import profile


def sample(delimiter=',',encoding='utf-8-sig'):
    stream=io.StringIO(newline='')
    writer=csv.writer(stream,delimiter=delimiter)
    writer.writerow(['Reference','Units','Sale','Cost','Total','Cost total','MG'])
    writer.writerow(['001234',2,107,101,214,202,'5.61'])
    return stream.getvalue().encode(encoding)


@pytest.mark.parametrize('driver',['sqlite','json'])
@pytest.mark.parametrize('delimiter,encoding',[(',', 'utf-8-sig'),(';','utf-8'),('\t','utf-16'),(',','cp874')])
def test_csv_mapping_import_export_restore(client,monkeypatch,driver,delimiter,encoding):
    monkeypatch.setattr(service,'STATE_DRIVER',driver)
    content=sample(delimiter,encoding)
    files={'file':('sales.csv',content)}
    result=client.post('/api/profiles/inspect',files=files)
    assert result.status_code==200,result.text
    assert result.json()['sheet']=='CSV'
    assert result.json()['sample'][0][0]=='001234'
    cfg=dict(profile(),sheet='CSV',customer='ร้านทดสอบ')
    preview=client.post('/api/profiles/preview',files=files,data={'config':json.dumps(cfg)})
    assert preview.status_code==200,preview.text
    cfg=client.post('/api/profiles',json={'config':preview.json()['config']}).json()
    b=client.post('/api/batches',json={}).json();url='/api/batches/'+b['id']
    result=client.post(url+'/upload',files={'files':('sales.csv',content)},data={'profile_id':cfg['id']})
    assert result.status_code==200,result.text
    assert result.json()['files'][0]['error'] is None
    rows=client.get(url+'/rows').json()['rows']
    assert rows[0]['sku']=='001234' and rows[0]['calculated_net']=='202'
    exported=client.get(url+'/export');assert exported.status_code==200,exported.text
    sheet=openpyxl.load_workbook(io.BytesIO(exported.content)).active
    assert sheet.cell(2,1).value=='001234'
    duplicate=client.post(url+'/upload',files={'files':('sales.csv',content)},data={'profile_id':cfg['id']})
    assert duplicate.status_code==409
    backup=client.post('/api/backups').json()
    archive=client.get('/api/backups/file/'+backup['name']).content
    preview=client.post('/api/backups/preview',files={'file':('backup.zip',archive)}).json()
    assert client.delete('/api/batches').status_code==200
    restored=client.post('/api/backups/restore',files={'file':('backup.zip',archive)},data={'confirm':'true','archive_hash':preview['archive_hash']})
    assert restored.status_code==200,restored.text
    assert client.get(url+'/rows').json()['rows'][0]['sku']=='001234'


def test_csv_literal_quotes_thai_and_multiline():
    text='SKU,Description,Qty\r\n001,"สีแดง, size M\nรุ่นใหม่",2\r\n=ABC,ธรรมดา,1\r\n'
    for encoding in ['utf-8-sig','utf-16','cp874']:
        book=csv_workbook(text.encode(encoding))
        assert book.active['A2'].value=='001'
        assert book.active['B2'].value=='สีแดง, size M\nรุ่นใหม่'
        assert book.active['A3'].data_type=='s'
        book.close()


@pytest.mark.parametrize('content',[b'',b'\x00abc',b'A,B\n"unterminated',(','.join(['x']*201)).encode()])
def test_csv_rejects_invalid_input(content):
    with pytest.raises(ValueError):csv_workbook(content)
