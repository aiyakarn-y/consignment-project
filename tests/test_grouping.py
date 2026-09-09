from decimal import Decimal as D
from copy import deepcopy
import io
import openpyxl
import pytest
from fastapi.testclient import TestClient
from backend import app as service
from backend.core import row,validate,percent,money

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(service,'DATA',tmp_path);monkeypatch.setattr(service,'DB',tmp_path/'test.db')
    return TestClient(service.app)

def seed(client,rows):
    b=client.post('/api/batches',json={}).json();batch=service.load(b['id'])
    for i,r in enumerate(rows):r.update(id=str(i),file_id='fixture')
    batch['rows']=rows;service.save(batch)
    return '/api/batches/'+b['id']

def sale(sku,q,p,discount,barcode='',customer='A'):
    return validate(row('fixture','Sheet',1,customer,'branch',sku,q,p,discount,barcode=barcode))

def read(response):
    assert response.status_code==200,response.text
    w=openpyxl.load_workbook(io.BytesIO(response.content));values=list(w.active.iter_rows(min_row=2,values_only=True));w.close();return values

def test_duplicate_sku_weighted_price_and_total_net(client):
    rows=[sale('SKU-A',2,100,'10%',customer='A'),sale('SKU-A',1,200,'20%',customer='B')]
    url=seed(client,rows);before=deepcopy(service.load(url.split('/')[-1]))
    response=client.get(url+'/export');values=read(response)
    assert len(values)==1
    sku,p,q,d=values[0]
    assert sku=='SKU-A' and q==3
    assert money(D(str(p))*D(str(q)))==D('400.00')
    assert money(D(str(p))*D(str(q))*percent(d))==D('340.00')
    assert response.headers['x-exported-rows']=='1'
    assert response.headers['x-exported-source-rows']=='2'
    assert response.headers['x-skipped-rows']=='0'
    assert service.load(url.split('/')[-1])==before

def test_barcode_is_not_a_grouping_key(client):
    url=seed(client,[sale('SKU-A',1,100,'0%','123'),sale('SKU-B',1,100,'0%','123'),sale('SKU-A',2,100,'0%','456')])
    summary=client.get(url).json()
    assert summary['blocked']==0 and summary['ready']==3
    values=read(client.get(url+'/export'))
    assert len(values)==2
    assert values[0][:3]==('SKU-A',100,3)
    assert values[1][:3]==('SKU-B',100,1)


def test_returns_and_zero_quantity_groups(client):
    url=seed(client,[sale('SKU-A',3,100,'10%'),sale('SKU-A',-1,100,'10%'),sale('SKU-B',1,100,'0%'),sale('SKU-B',-1,100,'0%')])
    response=client.get(url+'/export?scope=ready');values=read(response)
    assert values==[('SKU-A',100,2,'10%')]
    assert response.headers['x-skipped-rows']=='2'
    assert client.get(url).json()['blocked']==2

def test_same_barcode_same_sku_and_compound_discount(client):
    url=seed(client,[sale('SKU-A',1,100,'20%+5%','000123'),sale('SKU-A',2,100,'20%+5%','000123')])
    values=read(client.get(url+'/export'))
    assert len(values)==1 and values[0][2]==3
    assert money(D(str(values[0][1]))*3*percent(values[0][3]))==D('228.00')

def test_ready_subset_does_not_absorb_invalid_duplicate(client):
    invalid=sale('SKU-A',2,100,'10%');invalid['net']='999'
    url=seed(client,[sale('SKU-A',1,100,'10%'),sale('SKU-A',2,100,'10%'),invalid])
    response=client.get(url+'/export?scope=ready');values=read(response)
    assert len(values)==1 and values[0][2]==3
    assert response.headers['x-exported-source-rows']=='2' and response.headers['x-skipped-rows']=='1'
