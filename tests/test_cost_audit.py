from decimal import Decimal as D
from backend.core import row,validate
from test_grouping import client,seed


def test_unit_cost_and_total_are_distinct_from_net_after_gp(client):
    r=validate(row('x','s',1,'Big C','branch','SKU',3,449,'25%',1347,1010.25,raw={'K':'3','L':'419.63','P':'1258.8785046728972'}))
    assert r['source_cost_price']=='419.63'
    assert r['source_cost_total']=='1258.89'
    assert r['source_sales_ex_vat']=='1258.8785046728972'
    assert r['calculated_net']=='1010.25' and r['calculated_gross']=='1347'
    url=seed(client,[r]);g=client.get(url).json()['groups'][0]
    assert g['source_cost_total']=='1258.89' and g['cost_rows']==1


def test_missing_cost_is_unknown_even_when_default_zero():
    r=validate(row('x','s',1,'Outlet G624','branch','SKU',2,100))
    assert r['source_cost_price'] is None and r['source_cost_total'] is None
    assert r['calculated_net']=='200'


def test_actual_cost_unit_times_qty_is_checked_and_not_rounded_discount():
    r=validate(row('x','s',1,'KING POWER','branch','SKU',2,990,net=1202.8,raw={'E':'601.4','F':'2','I':'1202.8'}))
    assert r['source_cost_total']=='1202.8' and r['source_cost_delta']=='0'
    r['raw']['I']='1200'
    assert validate(r)['source_cost_delta']=='2.8'
    assert any('ต้นทุน' in e for e in r['errors'])


def test_return_and_user_changes_do_not_rewrite_source_cost():
    r=validate(row('x','s',1,'Outcast','branch','SKU',-2,100,'35%',net=-130,raw={'H':'65','I':'-2','K':'-130'}))
    assert r['source_cost_total']=='-130'
    r['price']='90';r['qty']='3'
    validate(r)
    assert r['calculated_gross']=='270' and r['source_cost_total']=='-130'
    assert r['status']=='blocked'


def test_gp_mg_and_equivalent_discount_have_distinct_provenance():
    r=validate(row('x','s',1,'KING POWER','branch','SKU',2,990,net=1202.8,raw={'D':'990','E':'601.4','F':'2','G':'1980','I':'1202.8','J':'39.25'}))
    assert r['source_mg']=='39.25%' and r['source_gp'] is None
    assert 'เทียบเท่า' in r['discount_kind'] and r['discount']=='39.2525252525%'
    r=validate(row('x','s',1,'Big C','branch','SKU',1,199,'25%',199,149.25,raw={'J':'25','K':'1','L':'372.9','M':'199','T':'149.25'}))
    assert r['source_gp']=='25%' and r['source_mg'] is None and r['discount_kind']=='GP จากต้นทาง'
    assert r['status']=='ready' and any('สูงกว่า' in w for w in r['warnings'])
    r=validate(row('x','s',1,'KING POWER','branch','SKU',1,100,raw={'J':'35'}))
    assert r['source_mg']=='35%' and r['discount']=='0%' and r['discount_defaulted']


def test_loss_free_goods_and_compound_gp_do_not_get_silently_reinterpreted():
    r=validate(row('x','s',1,'x','b','SKU',1,100,net=120))
    assert r['status']=='blocked' and r['discount']!='0%'
    r=validate(row('x','s',1,'x','b','SKU',1,100,net=0))
    assert r['status']=='ready' and r['discount']=='100%'
    r=validate(row('x','s',1,'x','b','SKU',2,100,'20%+5%',net=152))
    assert r['status']=='ready' and r['discount']=='20%+5%'
