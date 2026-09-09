import pytest
from backend.core import row,validate,sku_in
from test_grouping import client,seed,read

@pytest.mark.parametrize('reference',['LA-243TSACL15-AA-2L','WA-1590BG199-ไม่ระบุสี-XX-M','WA-1590BG199','WA-1590BG199-XX'])
def test_reference_preserved_without_requiring_color_size(reference):
    assert sku_in('ชื่อสินค้า '+reference)==reference
    assert validate(row('x','s',1,'Outlet G624','branch',reference,1,100))['status']=='ready'


def test_partner_reference_used_without_barcode_and_editable(client):
    r=row('x','s',1,'Outcast','branch','',1,100,partner='0026348',barcode='999')
    assert validate(r)['sku']=='0026348'
    assert 'อ้างอิง' in r['sku_origin']
    url=seed(client,[r]);assert read(client.get(url+'/export'))[0][0]=='0026348'
    assert client.patch(url+'/rows/0',json={'sku':'MY-SKU'}).json()['sku']=='MY-SKU'


def test_legacy_outlet_recovers_complete_reference():
    r=row('x','s',1,'Outlet G624','branch','',1,100,partner='G624P',raw={'D':'เสื้อ LA-243TSACL15-AA-2L'})
    assert validate(r)['sku']=='LA-243TSACL15-AA-2L'
    r=row('x','s',1,'x','branch','',1,100,barcode='123')
    assert validate(r)['status']=='blocked' and not r['sku']
