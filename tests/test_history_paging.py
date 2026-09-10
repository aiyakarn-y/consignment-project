import json
import pytest
from test_grouping import client
from backend import app as service

@pytest.mark.parametrize('kind,table,count', [('export','export_history',221),('import','import_registry',521)])
def test_history_pages_beyond_old_limit(client,kind,table,count):
    with service.db() as c:
        c.executemany(f'INSERT INTO {table} VALUES (?,?)', [(str(i),json.dumps(dict(id=str(i),batch_id='a' if i%2 else 'b',snapshot={'period':'2026-08'}))) for i in range(count)])
    url=f'/api/{kind}-history'
    first=client.get(url+'?page=1&size=20').json()
    assert first['total']==count and len(first['rows'])==20
    assert [r['id'] for r in first['rows']]==[str(i) for i in range(count-1,count-21,-1)]
    second=client.get(url+'?page=2&size=20').json()
    assert not {r['id'] for r in first['rows']} & {r['id'] for r in second['rows']}
    last=client.get(url+'?page=999&size=20').json()
    assert last['page']==(count+19)//20 and last['rows'][-1]['id']=='0'
    assert isinstance(client.get(url).json(),list)
    if kind=='export':
        filtered=client.get(url+'?page=1&size=100&batch_id=a').json()
        assert filtered['total']==count//2
        assert all(r['batch_id']=='a' for r in filtered['rows'])

@pytest.mark.parametrize('kind',['import','export'])
def test_empty_and_invalid_paging(client,kind):
    url=f'/api/{kind}-history'
    assert client.get(url+'?page=20&size=50').json()==dict(rows=[],total=0,page=1,size=50,pages=1)
    for query in ('page=0','page=-1','page=x','page=1&size=0','page=1&size=101'):
        assert client.get(url+'?'+query).status_code==422
