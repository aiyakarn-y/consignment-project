from copy import deepcopy
import pytest
from test_grouping import client, seed, sale, read
from backend import app as service

@pytest.mark.parametrize('discount,net', [('20%', '80'), ('5%', '95'), ('0%', '100'), ('100%', '0'), ('20%+5%', '76')])
def test_single_discount_recalculates_known_net(client, discount, net):
    r = sale('A', 1, 100, '10%'); r['net'] = '90'
    url = seed(client, [r])
    response = client.patch(url+'/rows/0', json={'discount': discount})
    assert response.status_code == 200
    updated = response.json()
    assert updated['net'] == updated['calculated_net'] == net
    assert updated['status'] == 'ready'
    assert updated['source_reference']['net'] == '90'
    assert updated['edits'][-1]['before']['net'] == '90'
    assert updated['edits'][-1]['after']['net'] == net
    assert read(client.get(url+'/export'))


def test_bulk_recalculates_known_net_and_returns(client):
    rows = [sale('A', 2, 100, '10%'), sale('B', -1, 100, '10%'), sale('C', 1, 100, '10%')]
    for r in rows: r['net'] = r['calculated_net']
    url = seed(client, rows)
    assert client.post(url+'/bulk-edit', json={'ids':['0','1'], 'field':'discount', 'value':'20%'}).json()['blocked'] == 0
    stored = service.load(url.split('/')[-1])['rows']
    assert [r['net'] for r in stored] == ['160', '-80', '90']
    client.patch(url+'/rows/0', json={'discount':'5%'})
    assert service.load(url.split('/')[-1])['rows'][0]['source_reference']['net'] == '180'


@pytest.mark.parametrize('discount,expected', [('0%', '0.00%'), ('20%+5.555%', '20.00%+5.56%'), ('39.2525252525%', '39.25%'), ('100%', '100.00%')])
def test_export_discount_fixed_two_decimals(client, discount, expected):
    url = seed(client, [sale('A', 1, 100, discount)])
    before = deepcopy(service.load(url.split('/')[-1]))
    assert read(client.get(url+'/export'))[0][3] == expected
    assert service.load(url.split('/')[-1]) == before


def test_preview_is_decimal_and_never_persists(client):
    r = sale('A', 2, 990, '39.2525252525%'); r['net'] = '1202.8'
    url = seed(client, [r]); before = deepcopy(service.load(url.split('/')[-1]))
    preview = client.post(url+'/rows/0/preview', json={'discount':'39.25%'}).json()
    assert preview['net'] == '1202.85'
    assert service.load(url.split('/')[-1]) == before
    response = client.get(url+'/export')
    assert response.headers['X-Export-Rounding-Delta'] == '0.05'


@pytest.mark.parametrize('changes, gross, net', [({'price':'200'}, '400','360'), ({'qty':'-2'},'-200','-180'), ({'net':'160'},'200','160')])
def test_other_financial_edits_recalculate(client, changes, gross, net):
    r = sale('A', 2, 100, '10%'); r['net'] = '180'
    url = seed(client,[r])
    updated = client.patch(url+'/rows/0', json=changes).json()
    assert updated['gross'] == gross and updated['net'] == net
    assert updated['status'] == 'ready'
    state = client.get(url).json()['groups'][0]
    assert state['net'] == '180' and state['calculated_net'] == net


def test_resaving_discount_repairs_old_edit_but_keeps_unrelated_errors(client):
    old = sale('A', 1, 100, '20%'); old['net'] = '100'
    broken = sale('B', 1, 100, '20%'); broken.update(net='100',gross='999')
    url = seed(client, [old, broken])
    result = client.post(url+'/bulk-edit', json={'ids':['0','1'],'field':'discount','value':'20%'}).json()
    assert result['blocked'] == 1
    rows = service.load(url.split('/')[-1])['rows']
    assert rows[0]['net'] == '80' and rows[0]['status'] == 'ready'
    assert rows[1]['gross'] == '999' and rows[1]['status'] == 'blocked'


def test_net_edits_reverse_discount_single_preview_and_bulk(client):
    url=seed(client,[sale('A',2,100,'10%'),sale('B',4,100,'10%')])
    before=deepcopy(service.load(url.split('/')[-1]))
    preview=client.post(url+'/rows/0/preview',json={'net':'160'}).json()
    assert preview['discount']=='20%' and preview['calculated_net']=='160'
    assert service.load(url.split('/')[-1])==before
    single=client.patch(url+'/rows/0',json={'net':'150'}).json()
    assert single['discount']=='25%' and single['calculated_net']=='150'
    assert client.post(url+'/bulk-edit',json={'ids':['0','1'],'field':'net','value':'160'}).json()['blocked']==0
    rows=service.load(url.split('/')[-1])['rows']
    assert [r['discount'] for r in rows]==['20%','60%']
    assert [r['calculated_net'] for r in rows]==['160','160']
