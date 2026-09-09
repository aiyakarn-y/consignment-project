from decimal import Decimal
from backend.core import row,validate
from test_grouping import client,seed,sale


def test_shop_branch_totals_and_exact_drilldown(client):
    a=sale('SKU-A',2,100,'10%');a.update(branch='Rayong',branch_code='01',gross='200',net='180')
    returned=sale('SKU-A',-1,100,'10%');returned.update(branch='Rayong renamed',branch_code='01',gross='-100',net='-90')
    missing=validate(row('x','S',1,'A','Rayong','',1,50));missing.update(branch_code='02',gross='50')
    other=sale('SKU-A',1,200,'0%',customer='B');other.update(branch='Rayong',branch_code='01',gross='200')
    unnamed=sale('SKU-C',1,30,'0%');unnamed.update(branch='',gross='30')
    url=seed(client,[a,returned,missing,other,unnamed])
    state=client.get(url).json();groups=state['groups'];g=next(x for x in groups if x['customer']=='A')
    children=g['branch_groups'];assert len(children)==g['branches']==3
    branch=next(x for x in children if x['branch_code']=='01')
    assert (branch['qty'],branch['gross'],branch['net'],branch['calculated_net'])==('1','100','90','90')
    assert branch['ready']==2 and branch['blocked']==0
    assert next(x for x in children if x['branch_code']=='02')['default_discount_rows']==1
    for key in ('rows','ready','blocked','qty','gross','net','calculated_net','net_rows','calculated_rows','default_discount_rows'):
        assert sum(Decimal(str(x[key])) for x in children)==Decimal(str(g[key]))
    result=client.get(url+'/rows',params={'customer':'A','branch_key':branch['key']}).json()
    assert result['total']==2 and {x['id'] for x in result['rows']}=={'0','1'}
    assert client.get(url+'/rows',params={'customer':'A','branch_key':branch['key'],'status':'blocked'}).json()['total']==0
    # Editing changes both branch and parent totals, and SKU-only export stays independent.
    assert client.patch(url+'/rows/0',json={'discount':'20%','net':'160'}).status_code==200
    g=next(x for x in client.get(url).json()['groups'] if x['customer']=='A')
    assert next(x for x in g['branch_groups'] if x['branch_code']=='01')['calculated_net']=='70'
    assert client.get(url+'/merged').json()['total']==2
