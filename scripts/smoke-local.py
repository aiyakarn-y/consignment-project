"""Verify native start/stop and persistence from another cwd using isolated data."""
import io,json,os,socket,subprocess,sys,time,uuid
from pathlib import Path
import httpx,openpyxl
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/test/native'/uuid.uuid4().hex
DATA.mkdir(parents=True)
ENV=dict(os.environ,CONSIGN_DATA_DIR=str(DATA),CONSIGN_FRONTEND_PORT='3121',CONSIGN_BACKEND_PORT='8121')
PYTHON=str(ROOT/'.venv/bin/python');SCRIPT=str(ROOT/'scripts/local.py')
base='http://127.0.0.1:3121';process=None

def start():
    global process
    process=subprocess.Popen([PYTHON,SCRIPT,'start'],cwd='/private/tmp',env=ENV,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    for _ in range(100):
        if process.poll() is not None:raise RuntimeError(process.stdout.read())
        try:
            if httpx.get(base+'/api/health').status_code==200:return
        except httpx.RequestError:pass
        time.sleep(.2)
    raise RuntimeError('Startup timed out')

def stop():
    result=subprocess.run([PYTHON,SCRIPT,'stop'],cwd='/private/tmp',env=ENV,capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    process.wait(timeout=15)

try:
    start()
    runtime_before=(DATA/'logs/local-runtime.json').read_bytes()
    duplicate=subprocess.run([PYTHON,SCRIPT,'start'],cwd='/private/tmp',env=ENV,capture_output=True,text=True,timeout=10)
    assert duplicate.returncode==0 and base in duplicate.stdout and 'Traceback' not in duplicate.stderr
    assert (DATA/'logs/local-runtime.json').read_bytes()==runtime_before
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0));occupied.listen(1)
        port=occupied.getsockname()[1]
        conflict_env=dict(ENV,CONSIGN_DATA_DIR=str(DATA/'conflict'),CONSIGN_BACKEND_PORT=str(port))
        conflict=subprocess.run([PYTHON,SCRIPT,'start'],cwd='/private/tmp',env=conflict_env,capture_output=True,text=True,timeout=10)
        assert conflict.returncode==1 and str(port) in conflict.stderr and 'Backend' in conflict.stderr
        assert 'Traceback' not in conflict.stderr
        assert occupied.fileno()!=-1
    client=httpx.Client(base_url=base,timeout=20)
    profile=client.post('/api/profiles',json={'config':{'name':'Persistence check','sheet':'Sheet','columns':{'sku':'A','qty':'B','price':'C'},'customer':'Synthetic'}}).json()
    b=client.post('/api/batches',json={'period':'2026-09'}).json();url='/api/batches/'+b['id']
    w=openpyxl.Workbook();w.active.append(['SKU','Qty','Price']);w.active.append(['PERSISTENCE-TEST',2,100]);buf=io.BytesIO();w.save(buf)
    upload=client.post(url+'/upload',files={'files':('fixture.xlsx',buf.getvalue())},data={'profile_id':profile['id']});assert upload.status_code==200,upload.text
    download=client.get(url+'/export');assert download.status_code==200
    history=client.get('/api/export-history').json();source=client.get(url).json()['files'][0]
    stop();start()
    assert client.get(url).json()['rows']==1
    assert client.get('/api/export-history/'+history[0]['id']+'/file').content==download.content
    assert client.get(url+'/files/'+source['id']).content==buf.getvalue()
    assert client.get('/api/profiles').json()[0]['id']==profile['id']
    stop()
    result={'start_from_other_cwd':True,'stop':True,'restart_persistence':True,'export_redownload':True,'source_redownload':True,'data_isolated':True,'duplicate_start':True,'occupied_port_error':True}
    (ROOT/'_wrx-output/evidence/native-local-smoke.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
finally:
    if process and process.poll() is None:
        process.terminate();process.wait(timeout=20)
