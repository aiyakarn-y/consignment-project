from copy import deepcopy
from test_grouping import client,seed,sale
from backend import app as service


def test_bulk_edit_selected_only_and_audited(client):
    url=seed(client,[sale('A',1,100,'0%'),sale('B',2,100,'0%'),sale('C',1,100,'0%')])
    res=client.post(url+'/bulk-edit',json={'ids':['0','1'],'field':'discount','value':'20%'})
    assert res.status_code==200 and res.json()['updated']==2
    rows=service.load(url.split('/')[-1])['rows']
    assert [r['calculated_net'] for r in rows]==['80','160','100']
    assert [len(r['edits']) for r in rows]==[1,1,0]


def test_bulk_invalid_request_is_atomic_and_known_totals_recalculated(client):
    a=sale('A',1,100,'0%');a['net']='100'
    url=seed(client,[a,sale('B',1,100,'0%')]);before=deepcopy(service.load(url.split('/')[-1]))
    for data in ({'ids':['0','missing'],'field':'discount','value':'20%'},{'ids':['0','1'],'field':'price','value':'NaN'}):
        assert client.post(url+'/bulk-edit',json=data).status_code in (400,404)
        assert service.load(url.split('/')[-1])==before
    result=client.post(url+'/bulk-edit',json={'ids':['0','1'],'field':'discount','value':'20%'}).json()
    assert result['blocked']==0
    assert service.load(url.split('/')[-1])['rows'][0]['net']=='80'
