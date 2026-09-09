from copy import deepcopy
from backend.core import row,validate
from backend import app as service
from test_grouping import client,seed


def loss(q=1):
    return row('Big C.xlsx','S',577,'Big C','Branch','WA-20FBM03-YD-M',q,199,'25%',199*q,149.25*q,raw={'J':'25','K':str(q),'L':'372.9','M':str(199*q),'T':str(149.25*q)})


def test_warning_confirmation_and_export_keep_real_values(client):
    url=seed(client,[validate(loss())]);r=client.get(url+'/rows').json()['rows'][0]
    assert r['below_cost_status']=='pending' and r['status']=='ready'
    # A business warning alone is not an export error.
    assert client.get(url+'/export').status_code==200
    response=client.post(url+'/rows/0/confirm-below-cost',json={'confirmed_by':'Sales branch','reason':'Clearance','vat_basis':'Both inclusive VAT','comparable':True,'evidence':'Report 577'})
    assert response.status_code==200,response.text
    r=response.json();assert r['below_cost_status']=='confirmed' and r['discount']=='25%'
    assert r['price']=='199' and r['source_cost_price']=='372.9' and r['calculated_net']=='149.25'
    assert r['below_cost_confirmations'][0]['confirmed_by']=='Sales branch'
    report=client.get(url+'/below-cost').json()
    assert report['confirmed']==1 and report['pending']==0
    assert report['groups'][0]['sales']=='199' and report['groups'][0]['cost']=='372.9'
    assert report['groups'][0]['difference']=='173.9' and report['groups'][0]['after_discount_difference']=='223.65'
    assert client.get(url+'/rows',params={'below_cost':'confirmed'}).json()['total']==1
    client.patch(url+'/rows/0',json={'discount':'20%'})
    r=client.get(url+'/rows').json()['rows'][0]
    assert r['below_cost_status']=='pending' and r['status']=='blocked'
    assert len(r['below_cost_confirmations'])==1
    assert client.get(url+'/export').status_code==409


def test_confirmation_validation_preserves_batch_and_no_false_return_loss(client):
    url=seed(client,[validate(loss()),validate(loss(-1)),validate(row('x','s',1,'Outlet G624','B','SKU',1,100))])
    before=deepcopy(service.load(url.split('/')[-1]))
    assert client.post(url+'/rows/0/confirm-below-cost',json={'confirmed_by':' ','reason':'','vat_basis':'','comparable':False}).status_code in (400,422)
    assert service.load(url.split('/')[-1])==before
    rows=client.get(url+'/rows').json()['rows']
    assert [r['below_cost_status'] for r in rows]==['pending','none','none']
    assert client.get(url+'/below-cost').json()['rows']==1
    assert client.post(url+'/rows/2/confirm-below-cost',json={'confirmed_by':'S','reason':'R','vat_basis':'unknown','comparable':False}).status_code==409
