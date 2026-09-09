from backend.core import row,validate
from test_grouping import client,seed,sale


def test_missing_discount_defaults_zero_but_is_marked():
    r=validate(row('x','x',1,'A','branch','SKU-A',2,100))
    assert r['status']=='ready' and r['discount']=='0%'
    assert r['discount_defaulted'] is True
    assert r['calculated_net']=='200'
    assert 'ค่าเริ่มต้น' in r['discount_origin']


def test_known_net_still_derives_and_missing_sku_still_blocks():
    r=validate(row('x','x',1,'A','branch','SKU-A',2,100,net=150))
    assert r['discount']=='25%' and not r.get('discount_defaulted')
    r=validate(row('x','x',1,'A','branch','',2,100))
    assert r['discount']=='0%' and r['status']=='blocked'
    assert any('SKU' in e for e in r['errors'])


def test_legacy_row_default_can_be_edited_later(client):
    r=validate(row('x','x',1,'A','branch','SKU-A',2,100))
    r['discount']='';r.pop('discount_defaulted',None)
    url=seed(client,[r]);current=client.get(url+'/rows').json()['rows'][0]
    assert current['discount']=='0%' and current['discount_defaulted']
    changed=client.patch(url+'/rows/0',json={'discount':'20%'}).json()
    assert changed['discount']=='20%' and not changed.get('discount_defaulted')
    assert changed['calculated_net']=='160'
    assert len(changed['edits'])==1
    assert client.get(url+'/merged').json()['rows'][0]['net']=='160'


def test_default_zero_bulk_edit_does_not_change_explicit_zero(client):
    default=validate(row('x','x',1,'A','branch','SKU-A',2,100))
    explicit=sale('SKU-B',1,100,'0%')
    url=seed(client,[default,explicit])
    result=client.post(url+'/discount-rule',json={'customer':'A','discount':'10%','remember':True})
    assert result.status_code==200 and result.json()['updated']==1
    rows=client.get(url+'/rows').json()['rows']
    assert rows[0]['discount']=='10%' and rows[1]['discount']=='0%'


def test_uncomputable_input_uses_default_without_hiding_bad_totals():
    r=validate(row('x','x',1,'A','branch','SKU-A',1,100,'0.35'))
    assert r['discount']=='0%' and r['discount_defaulted']
    r=validate(row('x','x',1,'A','branch','SKU-A',1,100,'10%',net=70))
    assert r['status']=='blocked' and r['discount']=='10%'
