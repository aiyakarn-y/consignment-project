from pathlib import Path
from typing import Literal
from datetime import datetime, timezone
from decimal import Decimal
from collections import defaultdict
from contextlib import contextmanager
import re
import csv, hashlib, io, json, os, sqlite3, uuid, zipfile
from fastapi import FastAPI, UploadFile, HTTPException, Query, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from backend.core import parse, validate, export_xlsx, dec, fmt, money, percent, discount_text, reverse_discount, export_discount, export_net, code, review_and_merge, below_cost_snapshot
import openpyxl

from backend.config import APP_VERSION, ROOT, DATA, DB, TEMPLATE, SAMPLES, STATE_DRIVER, STORAGE_DRIVER
from backend.storage import LocalFileStore, ASSET, LEGACY_ASSET
from backend.repository import SqliteRepository, json_repository, CURRENT, JsonTransaction, WriteConflict, StateTooLarge
from contextlib import asynccontextmanager

SOURCES = SAMPLES


def storage():
    if STORAGE_DRIVER == "vercel_blob":
        from backend.blob_storage import BlobFileStore
        return BlobFileStore()
    return LocalFileStore(DATA)


@asynccontextmanager
async def lifespan(app):
    storage().prepare()
    with repository():
        pass
    retry_cleanup()
    yield


app = FastAPI(title='ConsignmentSystem', version=APP_VERSION, lifespan=lifespan)

@contextmanager
def db():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c=sqlite3.connect(DB,timeout=20)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS mappings (key TEXT PRIMARY KEY, sku TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS rules (customer TEXT PRIMARY KEY, discount TEXT NOT NULL)')
    for table in ('profiles','valuations','import_registry','export_history'):
        c.execute(f'CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS file_cleanup (path TEXT PRIMARY KEY, last_error TEXT)')
    c.execute('PRAGMA user_version=2')
    try:
        yield c
        c.commit()
    finally:
        c.close()


@contextmanager
def repository():
    if STATE_DRIVER == 'json':
        with json_repository(storage()) as repo: yield repo
    else:
        with db() as connection: yield SqliteRepository(connection)


def delete_asset(key):
    active = CURRENT.get()
    if active is not None: active.deletes.add(key)
    else: storage().delete(key)


def load(batch_id):
    with repository() as repo: batch = repo.get('batches', batch_id)
    if batch is None: raise HTTPException(404,'ไม่พบชุดข้อมูล')
    return batch


def save(b):
    with repository() as repo:
        repo.put('batches', b['id'], b)
        for f in b['files']:
            if f.get('history_cleared'): continue
            record=dict(id=f['id'],hash=f['hash'],name=f['name'],batch_id=b['id'],period=b['period'],at=f.get('imported_at',b['created']),duplicate_override=f.get('duplicate_override',False),error=f.get('error'))
            repo.put('import_registry', f['id'], record, ignore=True)


def mapped(b,extra_maps=None):
    with repository() as repo:
        maps=dict(repo.items('mappings'))
        rules=dict(repo.items('rules'))
    if extra_maps:maps.update(extra_maps)
    for r in b['rows']:
        if not r['sku'] or r.get('sku_origin')=='ใช้รหัสอ้างอิงสินค้าต้นทาง · แก้ไขได้':
            sku=maps.get('barcode:'+r['barcode']) if r['barcode'] else None
            sku=sku or maps.get('partner:'+r['customer']+':'+r['partner'])
            if sku:
                before={'sku':r['sku'],'sku_origin':r.get('sku_origin')}
                r.update(sku=sku,sku_origin='ตารางอ้างอิง')
                r.setdefault('edits',[]).append(dict(at=datetime.now(timezone.utc).isoformat(),before=before,after={'sku':sku,'sku_origin':r['sku_origin']},reason='Master Mapping'))
        if (not r['discount'] or r.get('discount_defaulted')) and r['customer'] in rules:
            r.pop('discount_issue',None)
            r.update(discount=rules[r['customer']],discount_origin='กติกาที่บันทึกไว้',discount_defaulted=False)
        validate(r)
    return b


def branch_identity(r):
    branch_code=str(r.get('branch_code') or '').strip()
    return 'code:'+branch_code if branch_code else 'name:'+str(r.get('branch') or '').strip()


def summary(b):
    merged=review_and_merge(b['rows'])
    groups={}
    def empty():
        return dict(rows=0,ready=0,blocked=0,qty=Decimal(0),gross=Decimal(0),net=Decimal(0),net_rows=0,calculated_net=Decimal(0),calculated_rows=0,default_discount_rows=0,source_cost_total=Decimal(0),cost_rows=0,calculated_gross=Decimal(0),gross_rows=0,source_sales_ex_vat=Decimal(0),exvat_rows=0)
    def add(g,r):
        g['rows']+=1;g[r['status']]+=1
        for k in ('qty','gross','net','calculated_net','source_cost_total','calculated_gross','source_sales_ex_vat'):
            value=r.get('source_reference',r).get(k) if k in ('gross','net') else r.get(k)
            if value is not None:g[k]+=dec(value)
        g['cost_rows']+=r.get('source_cost_total') is not None
        g['gross_rows']+=r.get('calculated_gross') is not None
        g['exvat_rows']+=r.get('source_sales_ex_vat') is not None
        g['net_rows']+=r.get('source_reference',r).get('net') is not None
        g['calculated_rows']+=r.get('calculated_net') is not None
        g['default_discount_rows']+=bool(r.get('discount_defaulted'))
    def finish(g):
        for k in ('qty','gross','net','calculated_net','source_cost_total','calculated_gross','source_sales_ex_vat'):g[k]=fmt(g[k])
        return g
    for r in b['rows']:
        customer=r['customer']
        if customer not in groups:groups[customer]=dict(customer=customer,branch_groups={},**empty())
        g=groups[customer];key=branch_identity(r)
        if key not in g['branch_groups']:
            g['branch_groups'][key]=dict(key=key,branch=r.get('branch') or 'ไม่ระบุสาขา',branch_code=r.get('branch_code') or '',**empty())
        add(g,r);add(g['branch_groups'][key],r)
    result=[]
    for g in groups.values():
        g['branches']=len(g['branch_groups'])
        g['branch_groups']=[finish(x) for x in sorted(g['branch_groups'].values(),key=lambda x:(x['branch_code'],x['branch']))]
        result.append(finish(g))
    blocked=sum(bool(r['errors']) for r in b['rows'])
    return dict(id=b['id'],created=b['created'],files=b['files'],period=b['period'],rows=len(b['rows']),
                ready=len(b['rows'])-blocked,blocked=blocked,groups=result,
                below_cost_rows=sum(r.get('below_cost_status')!='none' for r in b['rows']),
                merged_rows=len(merged),
                merged_qty=fmt(sum((dec(r['qty']) for r in merged),Decimal(0))),
                merged_gross=fmt(sum((dec(r['gross']) for r in merged),Decimal(0))),
                merged_net=fmt(sum((dec(r['net']) for r in merged),Decimal(0))),
                file_errors=sum(bool(f.get('error')) for f in b['files']),
                exportable=bool(b['rows']) and not blocked and not any(f.get('error') for f in b['files']))


def add_file(b,content,name,profile=None,allow_duplicate=False,check_history=False,sheets=None):
    name=Path(name).name
    digest=hashlib.sha256(content).hexdigest()
    if any(f['hash']==digest for f in b['files']):
        raise HTTPException(409,f'ไฟล์ซ้ำในชุดเดียวกัน: {name}')
    from backend.operations import duplicate_matches,valuation_for
    prior=duplicate_matches(digest,b['id']) if check_history else []
    if prior and not allow_duplicate:raise HTTPException(409,'ไฟล์นี้เคยนำเข้าแล้วในชุดอื่น กรุณาตรวจประวัติและยืนยันนำเข้าซ้ำ')
    file_id=uuid.uuid4().hex
    key=f"imports/{b['id']}/{file_id}{Path(name).suffix.lower()}"
    info=dict(id=file_id,name=name,hash=digest,path=key,rows=0,kind='',error=None,imported_at=datetime.now(timezone.utc).isoformat(),duplicate_override=bool(prior),profile_snapshot=profile)
    # Validate before saving untrusted archives; never extract ZIP entries.
    if len(content)>25*1024*1024: raise HTTPException(413,'ไฟล์ต้องไม่เกิน 25 MB')
    if name.lower().endswith('.xlsx'):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if sum(i.file_size for i in z.infolist())>150*1024*1024:
                    raise HTTPException(413,'Excel หลังคลายข้อมูลใหญ่เกิน 150 MB')
        except zipfile.BadZipFile:
            raise HTTPException(400,'ไฟล์ไม่ใช่ Excel .xlsx ที่สมบูรณ์')
    elif name.lower().endswith('.csv'):
        from backend.csv_input import csv_workbook
        try: csv_workbook(content).close()
        except ValueError as ex: raise HTTPException(400,str(ex))
    elif not name.lower().endswith('.pdf') or not content.startswith(b'%PDF-'):
        raise HTTPException(400,'รองรับ Excel .xlsx, CSV และ PDF เท่านั้น')
    storage().write(key, content)
    try:
        if profile:
            if not name.lower().endswith(('.xlsx','.csv')):raise ValueError('รูปแบบที่ตั้งค่าใช้กับ Excel หรือ CSV เท่านั้น')
            from backend.import_profiles import parse_profile
            rows,kind=parse_profile(content,name,profile['config'],sheets=sheets)
        else:
            with storage().materialize(key) as path: rows,kind=parse(path,name,sheets=sheets)
        if name.lower().endswith(('.xlsx','.csv')):
            from backend.import_profiles import inspect_sheet_choices
            info['sheet_review']=inspect_sheet_choices(content,profile['config'] if profile else None,name=name)
            for item in info['sheet_review']:
                members=[r for r in rows if r['sheet']==item['name']]
                item.update(selected=bool(members),rows=len(members),gross=fmt(sum((dec(r.get('gross')) or Decimal(0) for r in members),Decimal(0))))
        for r in rows:
            r.update(id=uuid.uuid4().hex,file_id=file_id)
            settings=valuation_for(r['customer'])
            if settings:r['valuation']=settings
            validate(r)
        b['rows'].extend(rows);info.update(rows=len(rows),kind=kind)
    except Exception as ex:
        info['error']=str(ex)[:400];info['kind']='อ่านไม่สำเร็จ'
    b['files'].append(info)


class NewBatch(BaseModel):
    period:str=Field(default='2026-08',pattern=r'^\d{4}-(0[1-9]|1[0-2])$')


@app.get('/api/health')
def health(): return {'ok':True,'version':APP_VERSION,'name':'ConsignmentSystem','state_driver':STATE_DRIVER,'storage_driver':STORAGE_DRIVER}

@app.get('/api/batches')
def batches():
    with repository() as repo: rows = repo.items('batches', reverse=True)[:20]
    return [dict(id=b['id'],created=b['created'],period=b['period'],rows=len(b['rows'])) for _, b in rows]


def retry_cleanup():
    with repository() as repo: pending = repo.items('file_cleanup')
    removed = 0
    for key, _ in pending:
        try: delete_asset(key)
        except (OSError, ValueError) as ex:
            with repository() as repo: repo.put('file_cleanup', key, str(ex)[:300])
        else:
            if CURRENT.get() is None:
                with repository() as repo: repo.delete('file_cleanup', key)
                removed += 1
    with repository() as repo: remaining = len(repo.items('file_cleanup'))
    return dict(removed=removed, remaining=remaining)


@app.post('/api/storage/cleanup')
def cleanup_files():
    return retry_cleanup()


@app.delete('/api/batches')
def clear_batches():
    # Commit logical deletion before touching file bytes. Cleanup is idempotent.
    with repository() as repo:
        from backend.operations import backfill_registry
        backfill_registry(repo)
        bodies = repo.items('batches')
        keep = {row['path'] for _, row in repo.items('export_history')}
        targets = {f['path'] for _, body in bodies for f in body['files']}
        # JSON requests only delete referenced assets: sweeping unreferenced files
        # could remove a concurrent request's not-yet-committed upload.
        if STATE_DRIVER == 'sqlite':
            targets.update(item['key'] for item in storage().list('imports'))
            targets.update(item['key'] for item in storage().list() if LEGACY_ASSET.fullmatch(item['key']))
        targets = {key for key in targets if key not in keep and ASSET.fullmatch(key)}
        for key in targets: repo.put('file_cleanup', key, None, ignore=True)
        for key, entry in repo.items('import_registry'):
            entry['source_available'] = False
            entry.setdefault('source_deleted_at', datetime.now(timezone.utc).isoformat())
            repo.put('import_registry', key, entry)
        repo.clear('batches')
    cleanup = retry_cleanup()
    return {'deleted_batches': len(bodies), 'cleanup_pending': cleanup['remaining']}


@app.post('/api/batches')
def create(payload:NewBatch):
    b=dict(id=uuid.uuid4().hex,created=datetime.now(timezone.utc).isoformat(),period=payload.period,files=[],rows=[])
    save(b);return summary(b)

@app.post('/api/batches/{batch_id}/sample')
def sample(batch_id:str):
    b=load(batch_id)
    if not SOURCES.is_dir():raise HTTPException(404,'ยังไม่ได้ตั้งค่าไฟล์ตัวอย่าง')
    sources=sorted(p for p in SOURCES.iterdir() if p.suffix.lower() in ('.xlsx','.pdf') and p.name!='Consign_sample.xlsx' and not p.name.startswith('~$'))
    if not sources: raise HTTPException(404,'ไม่พบไฟล์ในโฟลเดอร์ตัวอย่างที่ตั้งค่า')
    digests={f['hash'] for f in b['files']}
    if any(hashlib.sha256(p.read_bytes()).hexdigest() in digests for p in sources):
        raise HTTPException(409,'ชุดนี้มีไฟล์ตัวอย่างแล้ว กรุณาสร้างชุดใหม่')
    for path in sources: add_file(b,path.read_bytes(),path.name)
    save(mapped(b));return summary(b)

@app.post('/api/batches/{batch_id}/upload')
def upload(batch_id:str,files:list[UploadFile],profile_id:str=Form(''),allow_duplicate:bool=Form(False),sheet_selection:str=Form('{}')):
    if len(files)>10: raise HTTPException(400,'อัปโหลดครั้งละไม่เกิน 10 ไฟล์')
    from backend.operations import get_profile
    profile=get_profile(profile_id) if profile_id else None
    try:
        selections=json.loads(sheet_selection)
        if not isinstance(selections,dict) or any(not key.isdigit() or int(key)>=len(files) or not isinstance(names,list) or not names or any(not isinstance(n,str) for n in names) for key,names in selections.items()):
            raise ValueError('รูปแบบการเลือกชีตไม่ถูกต้อง')
    except (ValueError,TypeError) as ex:raise HTTPException(400,str(ex))
    b=load(batch_id)
    previous = {f['id'] for f in b['files']}
    try:
        for index,f in enumerate(files):
            add_file(b,f.file.read(25*1024*1024+1),f.filename or 'unknown',profile,allow_duplicate,True,sheets=selections.get(str(index)))
        save(mapped(b))
    except Exception:
        with repository() as repo:
            for f in b['files']:
                if f['id'] not in previous: repo.put('file_cleanup', f['path'], None, ignore=True)
        retry_cleanup()
        raise
    return summary(b)

@app.get('/api/batches/{batch_id}')
def get_batch(batch_id:str): return summary(load(batch_id))

@app.get('/api/batches/{batch_id}/rows')
def get_rows(batch_id:str,q:str='',customer:str='',status:str='',sku:str='',branch_key:str='',below_cost:Literal['','all','pending','confirmed']='',page:int=Query(1,ge=1),size:int=Query(30,ge=1,le=100)):
    b=load(batch_id)
    review_and_merge(b['rows'])
    rows=b['rows']
    if sku: rows=[r for r in rows if r['sku'].strip()==sku]
    if customer: rows=[r for r in rows if r['customer']==customer]
    if branch_key: rows=[r for r in rows if branch_identity(r)==branch_key]
    if status: rows=[r for r in rows if r['status']==status]
    if below_cost:rows=[r for r in rows if r['below_cost_status']!='none' and (below_cost=='all' or r['below_cost_status']==below_cost)]
    if q: rows=[r for r in rows if q.lower() in ' '.join(str(r.get(k,'')) for k in ('sku','barcode','branch','branch_code','source')).lower()]
    return dict(total=len(rows),rows=rows[(page-1)*size:page*size])

@app.get('/api/batches/{batch_id}/merged')
def merged_preview(batch_id:str,q:str='',page:int=Query(1,ge=1),size:int=Query(30,ge=1,le=100)):
    b=load(batch_id)
    rows=review_and_merge(b['rows'])
    if q:rows=[r for r in rows if q.lower() in r['sku'].lower()]
    return dict(total=len(rows),rows=rows[(page-1)*size:page*size])

class BelowCostConfirmation(BaseModel):
    confirmed_by:str=Field(min_length=1,max_length=150)
    reason:str=Field(min_length=1,max_length=1000)
    vat_basis:str=Field(min_length=1,max_length=500)
    comparable:bool
    evidence:str=Field(default='',max_length=1000)


@app.post('/api/batches/{batch_id}/rows/{row_id}/confirm-below-cost')
def confirm_below_cost(batch_id:str,row_id:str,payload:BelowCostConfirmation):
    b=load(batch_id);r=next((r for r in b['rows'] if r['id']==row_id),None)
    if r is None:raise HTTPException(404,'ไม่พบรายการ')
    validate(r)
    if r['below_cost_status']=='none':raise HTTPException(409,'รายการนี้ไม่ได้ขายต่ำกว่าต้นทุน')
    if r['errors']:raise HTTPException(409,'แก้ข้อผิดพลาดการคำนวณก่อนยืนยันข้อมูล')
    data=payload.model_dump()
    for key in ('confirmed_by','reason','vat_basis','evidence'):data[key]=data[key].strip()
    if any(not data[k] for k in ('confirmed_by','reason','vat_basis')):raise HTTPException(400,'กรอกผู้ยืนยัน เหตุผล และฐาน VAT ให้ครบ')
    data.update(at=datetime.now(timezone.utc).isoformat(),snapshot=below_cost_snapshot(r))
    r.setdefault('below_cost_confirmations',[]).append(data)
    validate(r);save(b);return r


@app.get('/api/batches/{batch_id}/below-cost')
def below_cost_report(batch_id:str):
    b=load(batch_id);review_and_merge(b['rows'])
    rows=[r for r in b['rows'] if r['below_cost_status']!='none'];groups={}
    for r in rows:
        key=(r['customer'],branch_identity(r),r['comparison_basis'])
        if key not in groups:groups[key]=dict(customer=r['customer'],branch=r['branch'],branch_code=r.get('branch_code',''),key=key[1],comparison_basis=key[2],rows=0,pending=0,confirmed=0,comparable_rows=0,qty=Decimal(0),sales=Decimal(0),cost=Decimal(0),difference=Decimal(0),after_discount_difference=Decimal(0),after_discount_rows=0)
        g=groups[key];g['rows']+=1;g[r['below_cost_status']]+=1
        g['comparable_rows']+=bool((r.get('below_cost_confirmation') or {}).get('comparable'))
        g['qty']+=dec(r['qty'])
        for dest,src in (('sales','below_cost_sales'),('cost','below_cost_total'),('difference','below_cost_difference'),('after_discount_difference','below_cost_after_discount_difference')):
            if r.get(src) is not None:g[dest]+=dec(r[src])
        g['after_discount_rows']+=r.get('below_cost_after_discount_difference') is not None
    for g in groups.values():
        for k in ('qty','sales','cost','difference','after_discount_difference'):g[k]=fmt(g[k])
    return dict(rows=len(rows),pending=sum(r['below_cost_status']=='pending' for r in rows),confirmed=sum(r['below_cost_status']=='confirmed' for r in rows),groups=list(groups.values()))


class Edit(BaseModel):
    sku:str|None=None
    price:str|None=None
    qty:str|None=None
    discount:str|None=None
    net:str|None=None
    remember:bool=False

def apply_row_changes(r,changes):
    if 'discount' in changes or 'net' in changes:
        r.pop('discount_issue',None)
        r['discount_defaulted']=False
    before={k:r.get(k) for k in set(changes) | {'gross','net','discount'}}
    original={k:r.get(k) for k in ('price','qty','discount','gross','net')}
    try:
        for k,v in changes.items():
            if k in ('qty','price','net'):
                r[k]=fmt(dec(v))
            elif k=='discount':
                r[k]=discount_text(v) if v else ''
                r['discount_origin']='ผู้ใช้กรอก'
            else:
                value=(v or '').strip()
                if value!=r.get(k):r['sku_origin']='ผู้ใช้กรอก'
                r[k]=value
        if 'net' in changes and r.get('net') is not None and 'discount' not in changes:
            r['discount']=reverse_discount(dec(r['price'])*dec(r['qty']),dec(r['net'])) or ''
            r['discount_origin']='คำนวณจากยอดสุทธิที่ผู้ใช้ระบุ'
        amounts_changed = 'discount' in changes or any(
            k in changes and r.get(k) != original[k] for k in ('price','qty','net'))
        if amounts_changed:
            r.setdefault('source_reference', original)
            p, q, factor = dec(r.get('price')), dec(r.get('qty')), percent(r.get('discount'))
            if p is not None and q is not None:
                if any(k in changes and r.get(k) != original[k] for k in ('price','qty')):
                    r['gross'] = fmt(money(p*q))
                if 'net' not in changes and factor is not None:
                    r['net'] = fmt(money(p*q*factor))
        validate(r)
    except (ValueError,TypeError) as ex: raise HTTPException(400,str(ex))
    r['edits'].append(dict(at=datetime.now(timezone.utc).isoformat(),before=before,after={k:r.get(k) for k in before}))


class BulkEdit(BaseModel):
    ids:list[str]=Field(min_length=1,max_length=100)
    field:Literal['sku','price','qty','discount','net']
    value:str=Field(min_length=1,max_length=200)


@app.post('/api/batches/{batch_id}/bulk-edit')
def bulk_edit(batch_id:str,payload:BulkEdit):
    b=load(batch_id);ids=set(payload.ids)
    selected=[r for r in b['rows'] if r['id'] in ids]
    if len(selected)!=len(ids):raise HTTPException(404,'มีรายการที่เลือกไม่อยู่ในชุดข้อมูลนี้ กรุณาเลือกใหม่')
    for r in selected:apply_row_changes(r,{payload.field:payload.value})
    # Save once: malformed inputs cannot leave a partially updated batch.
    summary(b);save(b)
    return {'updated':len(selected),'blocked':sum(r['status']=='blocked' for r in selected)}


@app.post('/api/batches/{batch_id}/rows/{row_id}/preview')
def preview_edit(batch_id:str,row_id:str,payload:Edit):
    b=load(batch_id)
    r=next((r for r in b['rows'] if r['id']==row_id),None)
    if r is None:raise HTTPException(404,'ไม่พบรายการ')
    apply_row_changes(r,payload.model_dump(exclude_unset=True,exclude={'remember'}))
    return r  # Loaded copy only: previews never persist edits or confirmations.


@app.patch('/api/batches/{batch_id}/rows/{row_id}')
def edit(batch_id:str,row_id:str,payload:Edit):
    b=load(batch_id);r=next((r for r in b['rows'] if r['id']==row_id),None)
    if r is None:raise HTTPException(404,'ไม่พบรายการ')
    changes=payload.model_dump(exclude_unset=True,exclude={'remember'})
    apply_row_changes(r,changes)
    if payload.remember and r['sku'] and not any('SKU' in e for e in r['errors']):
        key='barcode:'+r['barcode'] if r['barcode'] else ('partner:'+r['customer']+':'+r['partner'] if r['partner'] else None)
        if key:
            with repository() as repo:
                old=repo.get('mappings',key)
                if old and old!=r['sku']: raise HTTPException(409,'รหัสนี้มี Mapping อื่นแล้ว ใช้การแก้เฉพาะแถวหรือตรวจตารางอ้างอิง')
                repo.put('mappings',key,r['sku'])
    save(mapped(b));return r

class Rule(BaseModel):
    customer:str
    discount:str
    remember:bool=True

@app.post('/api/batches/{batch_id}/discount-rule')
def rule(batch_id:str,payload:Rule):
    try: discount=discount_text(payload.discount)
    except ValueError as ex: raise HTTPException(400,str(ex))
    b=load(batch_id);count=0
    for r in b['rows']:
        if r['customer']==payload.customer and (not r['discount'] or r.get('discount_defaulted')):
            apply_row_changes(r,{'discount':discount})
            r['discount_origin']='ผู้ใช้กำหนดแทนค่าเริ่มต้น'
            count+=1
    if payload.remember:
        with repository() as repo: repo.put('rules',payload.customer,discount)
    save(b);return {'updated':count}

@app.post('/api/batches/{batch_id}/master')
def master(batch_id:str,file:UploadFile,preview:bool=Form(False)):
    b=load(batch_id);content=file.file.read(10*1024*1024+1)
    if len(content)>10*1024*1024: raise HTTPException(413,'ตารางอ้างอิงต้องไม่เกิน 10 MB')
    try:
        if (file.filename or '').lower().endswith('.csv'):
            records=list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))
        elif (file.filename or '').lower().endswith('.xlsx'):
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                if sum(i.file_size for i in z.infolist())>50*1024*1024: raise ValueError('ตารางอ้างอิงใหญ่เกินกำหนด')
            wb=openpyxl.load_workbook(io.BytesIO(content),data_only=True,read_only=True)
            values=wb.active.iter_rows(values_only=True);headers=[code(v) for v in next(values)]
            records=[dict(zip(headers,vals)) for vals in values];wb.close()
        else: raise ValueError('ใช้ตารางอ้างอิง .csv หรือ .xlsx')
        entries={}
        for i,record in enumerate(records,2):
            r={str(k).strip().lower():code(v) for k,v in record.items()}
            if not any(r.values()):continue
            sku=r.get('sku') or r.get('items')
            if not sku:raise ValueError(f'แถว {i} ขาด SKU หรือ Items')
            probe=validate(dict(sku=sku,qty='1',price='1',discount='0%'))
            if any('SKU' in e for e in probe['errors']):raise ValueError(f'แถว {i} SKU ไม่ถูกต้อง')
            keys=[]
            if r.get('barcode'):keys.append('barcode:'+r['barcode'])
            if r.get('partnercode') and r.get('customer'):keys.append('partner:'+r['customer']+':'+r['partnercode'])
            if not keys:raise ValueError(f'แถว {i} ต้องมี Barcode หรือ Customer + PartnerCode')
            for key in keys:
                if key in entries and entries[key]!=sku:raise ValueError(f'รหัสซ้ำจับคู่หลาย SKU ในแถว {i}')
                entries[key]=sku
        if not entries:raise ValueError('ไม่พบรายการ Mapping')
        with repository() as repo:
            for key,sku in entries.items():
                old=repo.get('mappings',key)
                if old and old!=sku:raise ValueError('Mapping ขัดแย้งกับข้อมูลที่บันทึกไว้: '+key)
            if not preview:
                for key,sku in entries.items(): repo.put('mappings',key,sku)
    except Exception as ex:raise HTTPException(400,str(ex)[:300])
    before=[r['sku'] for r in b['rows']];mapped(b,entries)
    changes=[dict(id=r['id'],before=old,after=r['sku']) for old,r in zip(before,b['rows']) if old!=r['sku']]
    if not preview:save(b)
    return {'mappings':len(entries),'resolved':len(changes),'changes':changes[:100],'preview':preview}

@app.get('/api/batches/{batch_id}/files/{file_id}')
def source_file(batch_id:str,file_id:str):
    b=load(batch_id);f=next((f for f in b['files'] if f['id']==file_id),None)
    if not f:raise HTTPException(404,'ไม่พบไฟล์')
    if not storage().exists(f['path']):raise HTTPException(404,'ไฟล์ต้นฉบับถูกล้างหรือไม่พบไฟล์')
    return storage().response(f['path'],filename=f['name'])

@app.delete('/api/batches/{batch_id}/files/{file_id}')
def remove_file(batch_id:str,file_id:str):
    b=load(batch_id)
    if not any(f['id']==file_id for f in b['files']):raise HTTPException(404,'ไม่พบไฟล์')
    b['files']=[f for f in b['files'] if f['id']!=file_id];b['rows']=[r for r in b['rows'] if r['file_id']!=file_id]
    save(b);return summary(b)

@app.get('/api/batches/{batch_id}/export')
def export(batch_id:str,scope:Literal['all','ready']='all'):
    b=load(batch_id)
    state=summary(b)  # Revalidate server-side; do not trust UI counts or stored status.
    if scope=='all' and not state['exportable']:
        raise HTTPException(409,'ยังมีรายการหรือไฟล์ที่ต้องแก้ก่อน export ทั้งหมด')
    rows=review_and_merge(b['rows'])
    included=sum(r['source_count'] for r in rows)
    if not rows:
        raise HTTPException(409,'ยังไม่มีรายการที่พร้อมส่งออก')
    key='exports/'+uuid.uuid4().hex+'.xlsx'
    try:storage().write_from(key, lambda temp: export_xlsx(rows,TEMPLATE,temp))
    except ValueError as ex:raise HTTPException(409,str(ex))
    suffix='_ready' if scope=='ready' else ''
    from backend.operations import json_rows,put
    rounding_delta=fmt(sum((export_net(r)-dec(r['net']) for r in rows),Decimal(0)))
    snapshot=dict(period=b['period'],template_hash=hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),rows=[dict(sku=r['sku'],price=str(float(dec(r['price']))),qty=str(float(dec(r['qty']))),discount=export_discount(r['discount'])) for r in sorted(rows,key=lambda r:r['sku'])])
    snapshot_hash=hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    previous=sum(e['snapshot_hash']==snapshot_hash for e in json_rows('export_history'))
    record=dict(id=uuid.uuid4().hex,batch_id=batch_id,at=datetime.now(timezone.utc).isoformat(),scope=scope,rows=len(rows),source_rows=included,skipped_rows=state['blocked'],skipped_files=state['file_errors'],filename=f'Consign_{b["period"]}{suffix}.xlsx',path=key,hash=hashlib.sha256(storage().read(key)).hexdigest(),snapshot_hash=snapshot_hash,snapshot=snapshot,rounding_delta=rounding_delta,source_files=[{k:f[k] for k in ('id','name','hash')} for f in b['files']],previous_identical_exports=previous)
    put('export_history',record['id'],record)
    return storage().response(key,filename=f'Consign_{b["period"]}{suffix}.xlsx',
        headers={'X-Export-Rounding-Delta':rounding_delta,'X-Export-ID':record['id'],'X-Previous-Identical-Exports':str(previous),'X-Exported-Rows':str(len(rows)),
                 'X-Exported-Source-Rows':str(included),
                 'X-Skipped-Rows':str(len(b['rows'])-included),
                 'X-Skipped-Files':str(state['file_errors'])},
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# Serialize state-changing HTTP operations in this single-process local demo.
import asyncio
_operation_lock=asyncio.Lock()
@app.middleware('http')
async def operation_lock(request,call_next):
    if request.method in ('POST','PATCH','DELETE') or request.url.path.endswith('/export'):
        async with _operation_lock:return await call_next(request)
    return await call_next(request)

from backend.operations import router as operations_router
app.include_router(operations_router)

@app.middleware('http')
async def json_unit_of_work(request, call_next):
    if STATE_DRIVER != 'json': return await call_next(request)
    from starlette.concurrency import run_in_threadpool
    from starlette.responses import JSONResponse
    try: transaction = await run_in_threadpool(JsonTransaction, storage())
    except (OSError, ValueError):
        return JSONResponse({'detail':'อ่านข้อมูลจัดเก็บไม่สำเร็จ กรุณาตรวจการตั้งค่า Storage'},status_code=503)
    token = CURRENT.set(transaction)
    try:
        response = await call_next(request)
        if response.status_code < 400:
            await run_in_threadpool(transaction.commit)
        return response
    except WriteConflict:
        return JSONResponse({'detail':'ข้อมูลถูกแก้ไขโดยคำขออื่น กรุณาโหลดใหม่ก่อนบันทึก'}, status_code=409)
    except StateTooLarge:
        return JSONResponse({'detail':'ข้อมูล JSON เกินขนาด Beta 64 MiB กรุณาสำรองและลดข้อมูล'}, status_code=413)
    except OSError:
        return JSONResponse({'detail':'บันทึกหรืออ่านไฟล์ไม่สำเร็จ กรุณาลองใหม่'},status_code=503)
    finally:
        CURRENT.reset(token)

from backend.beta_auth import install_beta_auth
from backend.cloud_transport import CloudTransportMiddleware
app.add_middleware(CloudTransportMiddleware)
install_beta_auth(app)
