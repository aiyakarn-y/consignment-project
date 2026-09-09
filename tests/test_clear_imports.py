from backend import app as service
from test_grouping import client,seed,sale


def test_clear_imports_preserves_configuration_and_originals(client):
    url=seed(client,[sale('SKU-A',1,100,'0%')])
    with service.db() as c:
        c.execute('INSERT INTO mappings VALUES (?,?)',('partner:A:P1','SKU-A'))
        c.execute('INSERT INTO rules VALUES (?,?)',('A','10%'))
    cached=service.DATA/('a'*32+'.xlsx');cached.write_bytes(b'cache')
    original=service.DATA/'Consign_sample.xlsx';original.write_bytes(b'original')
    result=client.delete('/api/batches')
    assert result.status_code==200 and result.json()['deleted_batches']==1
    assert client.get('/api/batches').json()==[]
    assert client.get(url).status_code==404
    assert not cached.exists() and original.read_bytes()==b'original'
    with service.db() as c:
        assert c.execute('SELECT COUNT(*) FROM mappings').fetchone()[0]==1
        assert c.execute('SELECT COUNT(*) FROM rules').fetchone()[0]==1
    assert client.delete('/api/batches').json()['deleted_batches']==0
    assert client.post('/api/batches',json={}).json()['rows']==0
