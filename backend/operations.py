"""Profiles, valuation settings, import/export audit, portable backup and restore."""
from pathlib import Path
from datetime import datetime,timezone
from copy import deepcopy
from decimal import Decimal
import hashlib,io,json,re,uuid,zipfile
from fastapi import APIRouter,UploadFile,Form,HTTPException,Query
from fastapi.responses import FileResponse
from pydantic import ValidationError
from backend.import_profiles import ImportProfile,Valuation,inspect_workbook,parse_profile,bind_profile_headers,require_profile_headers,inspect_sheet_choices
from backend.core import validate,review_and_merge,fmt,dec

router=APIRouter(prefix='/api')
TABLES=('batches','mappings','rules','profiles','valuations','import_registry','export_history')
from backend.storage import ASSET
MAX_BACKUP=250*1024*1024

def service():
    from backend import app
    return app

def now():return datetime.now(timezone.utc).isoformat()
def digest(data):return hashlib.sha256(data).hexdigest()
def json_rows(table):
    with service().repository() as repo: return [body for _, body in repo.items(table, reverse=True)]
def put(table,key,body):
    with service().repository() as repo: repo.put(table,key,body)
def get_profile(key):
    with service().repository() as repo: body=repo.get('profiles',key)
    if body is None: raise HTTPException(404,'ไม่พบรูปแบบนำเข้า')
    return body
def valuation_for(customer):
    with service().repository() as repo: body=repo.get('valuations',customer)
    return body['settings'] if body else None

def backfill_registry(repo):
    for _, b in repo.items('batches'):
        for f in b['files']:
            if f.get('history_cleared'):continue
            r=dict(id=f['id'],hash=f['hash'],name=f['name'],batch_id=b['id'],period=b['period'],at=f.get('imported_at',b['created']),duplicate_override=f.get('duplicate_override',False),error=f.get('error'))
            repo.put('import_registry',f['id'],r,ignore=True)


def duplicate_matches(content_hash,exclude_batch=''):
    # Include older pre-registry batches until they are next saved.
    records={r['id']:r for r in json_rows('import_registry')}
    for b in json_rows('batches'):
        for f in b['files']:
            records.setdefault(f['id'],dict(id=f['id'],hash=f['hash'],name=f['name'],batch_id=b['id'],period=b['period'],at=b['created']))
    return [r for r in records.values() if r['hash']==content_hash and r['batch_id']!=exclude_batch]

@router.get('/profiles')
def list_profiles():return json_rows('profiles')

@router.post('/profiles')
def save_profile(payload:dict):
    try:
        cfg=ImportProfile.model_validate(payload.get('config',{}));require_profile_headers(cfg);profile=cfg.model_dump()
    except (ValidationError,ValueError) as ex:raise HTTPException(400,str(ex))
    key=payload.get('id') or uuid.uuid4().hex
    old=get_profile(key) if payload.get('id') else None
    body=dict(id=key,version=old['version']+1 if old else 1,updated=now(),config=profile)
    put('profiles',key,body);return body

@router.post('/profiles/inspect')
def inspect(file:UploadFile,sheet:str=Form(''),header_row:int=Form(1)):
    try:return inspect_workbook(file.file.read(25*1024*1024+1),sheet,header_row)
    except Exception as ex:raise HTTPException(400,str(ex)[:1000])

@router.post('/profiles/preview')
def preview(file:UploadFile,config:str=Form(...)):
    try:
        content=file.file.read(25*1024*1024+1)
        bound=bind_profile_headers(content,json.loads(config))
        rows,kind=parse_profile(content,file.filename or 'preview.xlsx',bound)
    except Exception as ex:raise HTTPException(400,str(ex)[:1000])
    review_and_merge(rows)
    return dict(config=bound,kind=kind,rows=len(rows),ready=sum(r['status']=='ready' for r in rows),blocked=sum(r['status']=='blocked' for r in rows),sample=rows[:20])

@router.get('/valuations')
def valuations():return json_rows('valuations')

@router.post('/valuations')
def set_valuation(payload:dict):
    customer=str(payload.get('customer','')).strip()
    if not customer or len(customer)>150:raise HTTPException(400,'ระบุลูกค้า')
    try:settings=Valuation.model_validate(payload.get('settings',{})).model_dump()
    except (ValidationError,ValueError) as ex:raise HTTPException(400,str(ex))
    batch=service().load(payload['batch_id']) if payload.get('batch_id') else None
    body=dict(id=customer,customer=customer,settings=settings,updated=now())
    # Saving both settings and current batch atomically.
    count=0
    if batch:
        for r in batch['rows']:
            if r['customer']==customer:
                previous=r.get('valuation');r['valuation']=deepcopy(settings)
                r.setdefault('edits',[]).append(dict(at=now(),before={'valuation':previous},after={'valuation':settings}));validate(r);count+=1
    with service().repository() as repo:
        repo.put('valuations',customer,body)
        if batch:repo.put('batches',batch['id'],batch)
    return dict(updated=count,settings=body)

@router.post('/batches/{batch_id}/check-upload')
def check_upload(batch_id:str,files:list[UploadFile],profile_id:str=Form('')):
    b=service().load(batch_id);results=[]
    profile=get_profile(profile_id)['config'] if profile_id else None
    if len(files)>10:raise HTTPException(400,'สูงสุด 10 ไฟล์')
    for f in files:
        content=f.file.read(25*1024*1024+1)
        if len(content)>25*1024*1024:raise HTTPException(413,'ไฟล์ต้องไม่เกิน 25 MB')
        sha=digest(content)
        sheets=[]
        if (f.filename or '').lower().endswith('.xlsx'):
            try:sheets=inspect_sheet_choices(content,profile)
            except ValueError as ex:raise HTTPException(400,str(ex))
        results.append(dict(sheets=sheets,name=f.filename,hash=sha,same_batch=any(x['hash']==sha for x in b['files']),previous=duplicate_matches(sha,batch_id)))
    return results

@router.delete('/history')
def clear_history(confirm:bool=False):
    if not confirm:raise HTTPException(400,'ต้องยืนยันก่อนล้างประวัติ Import / Export')
    with service().repository() as repo:
        backfill_registry(repo)
        imports=len(repo.items('import_registry'))
        exports=len(repo.items('export_history'))
        for batch_id,batch in repo.items('batches'):
            for f in batch['files']:f['history_cleared']=True
            repo.put('batches',batch_id,batch)
        repo.clear('import_registry')
        repo.clear('export_history')
    return dict(cleared_imports=imports,cleared_exports=exports)


def history_page(table, page, size, batch_id=''):
    # Keep database-level paging for the SQLite adapter; JSON Beta pages a snapshot.
    if service().STATE_DRIVER == 'sqlite':
        where=" WHERE json_extract(body, '$.batch_id')=?" if batch_id else ''
        args=(batch_id,) if batch_id else ()
        with service().db() as c:
            c.execute('BEGIN')
            total=c.execute(f'SELECT COUNT(*) FROM {table}'+where,args).fetchone()[0]
            pages=max(1,(total+size-1)//size);page=min(page,pages)
            rows=[json.loads(body) for body, in c.execute(f'SELECT body FROM {table}'+where+' ORDER BY rowid DESC LIMIT ? OFFSET ?',(*args,size,(page-1)*size))]
    else:
        rows=[r for r in json_rows(table) if not batch_id or r.get('batch_id')==batch_id]
        total=len(rows);pages=max(1,(total+size-1)//size);page=min(page,pages)
        rows=rows[(page-1)*size:page*size]
    return dict(rows=rows,total=total,page=page,size=size,pages=pages)


@router.get('/import-history')
def import_history(page:int|None=Query(None,ge=1),size:int=Query(20,ge=1,le=100)):
    with service().repository() as repo:backfill_registry(repo)
    result=history_page('import_registry',page or 1,size if page is not None else 500)
    # Check availability only for batches represented on this page.
    ids={r['batch_id'] for r in result['rows']}
    active=set()
    if ids:
        with service().repository() as repo: bodies=[repo.get('batches',key) for key in ids]
        active={f['id'] for body in bodies if body for f in body['files'] if service().storage().exists(f['path'])}
    result['rows']=[dict(r,source_available=r['id'] in active) for r in result['rows']]
    return result if page is not None else result['rows']


@router.get('/export-history')
def export_history(batch_id:str='',page:int|None=Query(None,ge=1),size:int=Query(20,ge=1,le=100)):
    result=history_page('export_history',page or 1,size if page is not None else 200,batch_id)
    return result if page is not None else result['rows']

@router.get('/export-history/{export_id}/file')
def export_file(export_id:str):
    r=next((r for r in json_rows('export_history') if r['id']==export_id),None)
    if not r:raise HTTPException(404,'ไม่พบประวัติ Export')
    if not service().storage().exists(r['path']):raise HTTPException(404,'ไม่พบไฟล์ Export ที่บันทึกไว้')
    return service().storage().response(r['path'],filename=r['filename'])


def create_backup(connection=None):
    s=service()
    def capture(repo):
        backfill_registry(repo)
        return {name:[[key,body if name in ('mappings','rules') else json.dumps(body,ensure_ascii=False)] for key,body in repo.items(name)] for name in TABLES}
    if connection is None:
        with s.repository() as repo:tables=capture(repo)
    else:tables=capture(connection)
    assets={}
    for _,body in tables['batches']:
        for f in json.loads(body)['files']:assets[f['path']]=None
    for _,body in tables['export_history']:assets[json.loads(body)['path']]=None
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name in assets:
            if not ASSET.fullmatch(name):raise HTTPException(400,'ชื่อไฟล์ในข้อมูลไม่ถูกต้อง')
            if not s.storage().exists(name):raise HTTPException(409,'สำรองไม่ได้: ไม่พบไฟล์ '+name)
            content=s.storage().read(name);assets[name]=digest(content);z.writestr('files/'+name,content)
        manifest=dict(format='consignment-system-backup',version=2,created=now(),tables=tables,assets=assets)
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False))
    data=archive.getvalue()
    if len(data)>MAX_BACKUP:raise HTTPException(413,'ข้อมูลสำรองใหญ่เกิน 250 MB')
    try:checked_backup(data)
    except Exception as ex:raise HTTPException(409,'สำรองไม่ได้: '+str(ex)[:500])
    return data,manifest


def checked_backup(data):
    if len(data)>MAX_BACKUP:raise ValueError('ไฟล์สำรองต้องไม่เกิน 250 MB')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or len(names)>10000:raise ValueError('รายการ ZIP ซ้ำหรือมากเกินกำหนด')
        if any(i.file_size>MAX_BACKUP for i in z.infolist()) or sum(i.file_size for i in z.infolist())>500*1024*1024:raise ValueError('ข้อมูลหลังคลาย ZIP ใหญ่เกินกำหนด')
        if 'manifest.json' not in names or z.getinfo('manifest.json').file_size>100*1024*1024:raise ValueError('ไม่มี manifest ที่รองรับ')
        manifest=json.loads(z.read('manifest.json'))
        if (manifest.get('format'),manifest.get('version')) not in (('consign-demo-backup',1),('consignment-system-backup',2)):raise ValueError('ไม่รองรับเวอร์ชันข้อมูลสำรอง')
        tables=manifest.get('tables');assets=manifest.get('assets')
        if not isinstance(tables,dict) or set(tables)!=set(TABLES) or not isinstance(assets,dict):raise ValueError('โครงสร้างข้อมูลสำรองไม่ครบ')
        if any(not ASSET.fullmatch(k) for k in assets):raise ValueError('ชื่อไฟล์สำรองไม่ปลอดภัย')
        if set(names)!={'manifest.json',*('files/'+k for k in assets)}:raise ValueError('พบไฟล์นอก manifest')
        contents={}
        for name,sha in assets.items():
            content=z.read('files/'+name)
            if digest(content)!=sha:raise ValueError('Checksum ไม่ตรง: '+name)
            contents[name]=content
        references=set()
        for table,records in tables.items():
            if not isinstance(records,list) or len(records)>100000:raise ValueError('ตารางเกินขอบเขต')
            ids=set()
            for record in records:
                if not isinstance(record,list) or len(record)!=2 or not all(isinstance(v,str) for v in record):raise ValueError('โครงสร้างแถวไม่ถูกต้อง')
                key,body=record
                if not key or key in ids:raise ValueError('รหัสซ้ำในตาราง')
                ids.add(key)
                if table=='rules':
                    from backend.core import discount_text
                    discount_text(body);continue
                if table=='mappings':continue
                obj=json.loads(body)
                if not isinstance(obj,dict) or obj.get('id')!=key:raise ValueError('รหัสข้อมูลสำรองไม่ตรง')
                if table=='profiles':ImportProfile.model_validate(obj['config']);int(obj['version'])
                elif table=='valuations':Valuation.model_validate(obj['settings'])
                elif table=='batches':
                    if not isinstance(obj.get('rows'),list) or not isinstance(obj.get('files'),list) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',obj.get('period','')) or not obj.get('created'):raise ValueError('ชุดข้อมูลสำรองไม่สมบูรณ์')
                    fids={f['id'] for f in obj['files']}
                    if len(fids)!=len(obj['files']):raise ValueError('รหัสไฟล์ซ้ำ')
                    rids=set()
                    for r in obj['rows']:
                        required={'id','file_id','source','sheet','line','customer','branch','sku','qty','price','discount','gross','net','raw','edits','barcode','partner'}
                        if not isinstance(r,dict) or not required.issubset(r) or r['id'] in rids or r['file_id'] not in fids:raise ValueError('รายการขายสำรองไม่ครบ')
                        rids.add(r['id']);validate(deepcopy(r))
                    for f in obj['files']:
                        if not {'id','path','hash','name','rows','kind','error'}.issubset(f) or f['path'] not in assets:raise ValueError('ไฟล์ต้นทางอ้างอิงไม่ครบ')
                        if f['hash']!=assets[f['path']]:raise ValueError('Hash ต้นทางไม่ตรง')
                        references.add(f['path'])
                elif table=='export_history':
                    if not {'batch_id','path','filename','hash','at','scope','rows','source_rows','snapshot_hash','snapshot','skipped_rows','skipped_files'}.issubset(obj) or obj['path'] not in assets:raise ValueError('ประวัติ Export ไม่ครบ')
                    if obj['hash']!=assets[obj['path']]:raise ValueError('Hash Export ไม่ตรง')
                    references.add(obj['path'])
                elif table=='import_registry':
                    if not {'hash','batch_id','name','period','at'}.issubset(obj):raise ValueError('ทะเบียนนำเข้าไม่ครบ')
        if references!=set(assets):raise ValueError('ไฟล์แนบไม่ตรงกับข้อมูลอ้างอิง')
        return manifest,contents


def backup_summary(m):
    return dict(created=m['created'],batches=len(m['tables']['batches']),rows=sum(len(json.loads(r[1])['rows']) for r in m['tables']['batches']),profiles=len(m['tables']['profiles']),valuations=len(m['tables']['valuations']),mappings=len(m['tables']['mappings']),rules=len(m['tables']['rules']),imports=len(m['tables']['import_registry']),exports=len(m['tables']['export_history']),files=len(m['assets']))

@router.get('/backups')
def list_backups():
    return [dict(name=Path(item['key']).name,bytes=item['bytes']) for item in reversed(service().storage().list('backups')) if item['key'].endswith('.zip')]

@router.get('/backups/file/{name}')
def backup_file(name:str):
    if not re.fullmatch(r'[0-9a-zT_-]+\.zip',name):raise HTTPException(400,'ชื่อสำรองไม่ถูกต้อง')
    key='backups/'+name
    if not service().storage().exists(key):raise HTTPException(404,'ไม่พบไฟล์สำรอง')
    return service().storage().response(key,filename=name)

@router.post('/backups')
def backup():
    data,m=create_backup()
    name='manual-'+uuid.uuid4().hex+'.zip';service().storage().write('backups/'+name, data)
    return dict(name=name,summary=backup_summary(m))

@router.post('/backups/preview')
def backup_preview(file:UploadFile):
    data=file.file.read(MAX_BACKUP+1)
    try:m,_=checked_backup(data)
    except Exception as ex:raise HTTPException(400,'ไฟล์สำรองไม่ถูกต้อง: '+str(ex)[:500])
    return dict(archive_hash=digest(data),summary=backup_summary(m))

@router.post('/backups/restore')
def restore(file:UploadFile,archive_hash:str=Form(...),confirm:bool=Form(False)):
    if not confirm:raise HTTPException(400,'ต้องยืนยันก่อนกู้คืน')
    data=file.file.read(MAX_BACKUP+1)
    if digest(data)!=archive_hash:raise HTTPException(409,'ไฟล์เปลี่ยนจากที่ตรวจตัวอย่าง กรุณาตรวจใหม่')
    try:m,contents=checked_backup(data)
    except Exception as ex:raise HTTPException(400,'ไฟล์สำรองไม่ถูกต้อง: '+str(ex)[:500])
    s=service();written=[]
    safety='before-restore-'+uuid.uuid4().hex+'.zip'
    try:
        with s.repository() as repo:
            current,_=create_backup(repo);s.storage().write('backups/'+safety, current)
            # New names avoid replacing any current file before the database commits.
            rename = {}
            for _, body in m['tables']['batches']:
                batch = json.loads(body)
                for f in batch['files']:
                    rename[f['path']] = f"imports/{batch['id']}/{uuid.uuid4().hex}{Path(f['path']).suffix}"
            for _, body in m['tables']['export_history']:
                rename[json.loads(body)['path']] = 'exports/'+uuid.uuid4().hex+'.xlsx'
            for name,content in contents.items():
                key=rename[name];written.append(key);s.storage().write(key,content)
            for table in TABLES:
                records=deepcopy(m['tables'][table])
                if table in ('batches','export_history'):
                    for record in records:
                        obj=json.loads(record[1])
                        if table=='batches':
                            for f in obj['files']:f['path']=rename[f['path']]
                        else:obj['path']=rename[obj['path']]
                        record[1]=json.dumps(obj,ensure_ascii=False)
                repo.clear(table)
                for key,body in records:repo.put(table,key,body if table in ('mappings','rules') else json.loads(body))
    except Exception:
        for key in written:s.delete_asset(key)
        raise
    return dict(restored=backup_summary(m),safety_backup=safety)
