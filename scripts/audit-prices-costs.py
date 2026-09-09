"""Independent source-column reconciliation against normalized, shop and export data."""
from pathlib import Path
from decimal import Decimal as D, ROUND_HALF_UP
from collections import defaultdict
import json,openpyxl,pdfplumber,re,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.core import parse,review_and_merge,export_xlsx
from backend.app import summary
from backend.config import SAMPLES as BASE, TEMPLATE
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'_wrx-output/evidence/price-cost-audit';OUT.mkdir(parents=True,exist_ok=True)
def num(x):return None if x is None or x=='' else D(str(x).replace(',',''))
def cents(x):return x.quantize(D('.01'),rounding=ROUND_HALF_UP)
allrows=[];checks=[];reports=[]
for p in sorted(BASE.iterdir()):
 if p.suffix.lower() not in ('.xlsx','.pdf') or p.name=='Consign_sample.xlsx' or p.name.startswith('~$'):continue
 rows,kind=parse(p,p.name);w=openpyxl.load_workbook(p,data_only=True) if p.suffix=='.xlsx' else None
 source_totals=defaultdict(lambda:D(0));rounding_deltas=[]
 for r in rows:
  line=r['line'];q=price=unit=total=gross=net=exvat=None
  if w:
   ws=w[r['sheet']];v=lambda c:ws[f'{c}{line}'].value
   if kind=='Big C':
    q=num(v('K'));price=num(v('N'));gross=num(v('M'));net=num(v('T'));unit=num(v('L'));total=cents(unit*q);exvat=num(v('P'))
   elif kind=='KING POWER':q,price,unit,gross,total=[num(v(c)) for c in ('F','D','E','G','I')];net=total
   elif kind=='Outcast':q,price,unit,gross,total=[num(v(c)) for c in ('I','G','H','J','K')];net=total
   else:
    qc,gc=r['source_columns'].split('/');q=num(v(qc));gross=num(v(gc));price=gross/q
  else:
   # Parse the raw PDF line independently by splitting its final numeric tokens.
   parts=r['raw']['text'].split();q,gross,total=map(num,parts[-3:]);price=gross/q;unit=total/q;net=total
  assert num(r['qty'])==q and cents(num(r['price'])*q)==cents(gross),(kind,line,'sale')
  assert num(r['source_cost_price'])==unit and num(r['source_cost_total'])==total,(kind,line,'cost')
  assert num(r['net'])==net,(kind,line,'net')
  if net is not None:assert cents(num(r['calculated_net']))==cents(net),(kind,line,'computed net')
  if unit is not None:assert cents(unit*q)==cents(total),(kind,line,'unit cost')
  source_totals['qty']+=q;source_totals['sales_total']+=gross
  if total is not None:source_totals['cost_total']+=total
  if net is not None:source_totals['settlement_total']+=net
  if exvat is not None:source_totals['sales_ex_vat']+=exvat
  # Quantify the difference if the visible two-decimal discount is used as the actual rate.
  factor=D(1)
  for part in r['discount'].split('+'):factor*=1-cents(num(part.rstrip('%')))/100
  delta=cents(price*q*factor)-num(r['calculated_net']);rounding_deltas.append(delta)
  checks.append([kind,r['branch'],line,r['sku'],str(q),str(price),str(unit) if unit is not None else None,str(gross),str(total) if total is not None else None,str(net) if net is not None else None,r['calculated_net'],str(delta),r['source_cost_origin']])
  r['id']=str(len(allrows));allrows.append(r)
 # Check independent printed/cached control totals, not merely the same detail formula.
 if kind=='KING POWER':assert source_totals['qty']==num(w.active['F48'].value) and source_totals['sales_total']==num(w.active['G48'].value) and source_totals['cost_total']==num(w.active['I48'].value)
 if kind=='Outcast':assert source_totals['qty']==num(w.active['I25'].value) and source_totals['sales_total']==num(w.active['J25'].value) and source_totals['cost_total']==num(w.active['K25'].value)
 if kind=='Outlet G624':
  ws=w.active
  assert source_totals['qty']==num(ws['P61'].value) and source_totals['sales_total']==num(ws['AB61'].value)
  for j in range(5,16):
   assert sum(num(ws.cell(i,j).value) or D(0) for i in range(5,61))==num(ws.cell(61,j).value)
   assert sum(num(ws.cell(i,j+12).value) or D(0) for i in range(5,61))==num(ws.cell(61,j+12).value)
  for i in range(5,61):
   assert sum(num(ws.cell(i,j).value) or D(0) for j in range(5,16))==num(ws.cell(i,16).value)
   assert sum(num(ws.cell(i,j).value) or D(0) for j in range(17,28))==num(ws.cell(i,28).value)
 if kind=='Big C':
  ws=w['GNFBASCONSO_V5_07100727_202608'];assert cents(source_totals['settlement_total'])==cents(num(ws['T3773'].value))
  assert cents(source_totals['sales_ex_vat'])==cents(num(ws['P3773'].value))
  for values in w['Sheet3'].iter_rows(min_row=4,max_row=43,values_only=True):
   branch=str(values[1]);expected=num(values[2]);actual=sum((num(r['raw']['P']) for r in rows if r['branch_code']==branch),D(0))
   assert cents(expected)==cents(actual),branch
 if kind=='PDF ส่งเงินคืน':
  with pdfplumber.open(p) as pdf:
   m=re.search(r'รวม\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})',pdf.pages[-1].extract_text())
   assert source_totals['sales_total']==num(m[1]) and source_totals['cost_total']==num(m[2])
 reports.append(dict(source=kind,rows=len(rows),totals={k:str(v) for k,v in source_totals.items()},missing_cost_rows=sum(r['source_cost_total'] is None for r in rows),rounded_discount_changed_rows=sum(bool(d) for d in rounding_deltas),rounded_discount_total_delta=str(sum(rounding_deltas))))
 if w:w.close()
state=summary(dict(id='audit',created='',period='2026-08',files=[],rows=allrows))
for g in state['groups']:
 for key in ('qty','gross','net','calculated_net','source_cost_total','calculated_gross','source_sales_ex_vat'):
  assert sum(num(b[key]) for b in g['branch_groups'])==num(g[key])
merged=review_and_merge(allrows);export_xlsx(merged,TEMPLATE,OUT/'audited-export.xlsx')
w=openpyxl.load_workbook(OUT/'audited-export.xlsx',data_only=True);grouped=defaultdict(lambda:[D(0),D(0),D(0)])
for r in allrows:
 assert r['status']=='ready',(r['customer'],r['line'],r['errors'])
 t=grouped[r['sku']];t[0]+=num(r['qty']);t[1]+=cents(num(r['gross']));t[2]+=num(r['calculated_net'])
for sku,p,q,d in w.active.iter_rows(min_row=2,values_only=True):
 factor=D(1)
 for part in d.split('+'):factor*=1-num(part.rstrip('%'))/100
 assert [num(q),cents(num(p)*num(q)),cents(num(p)*num(q)*factor)]==grouped[sku],sku
assert w.active.max_row==len(grouped)+1;w.close()
book=openpyxl.Workbook();ws=book.active;ws.title='Source reconciliation';ws.append(['Source','Branch','Source row','SKU','Qty','Sale unit','Cost unit source','Sale total','Cost total source','Settlement total source','Calculated settlement','Delta if discount rounded 2dp','Cost origin'])
for line in checks:ws.append(line)
ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
book.save(OUT/'all-rows-reconciliation.xlsx')
result=dict(sources=reports,rows=len(allrows),sku_rows=len(merged),branch_groups=sum(g['branches'] for g in state['groups']),checks='All source detail, control totals, branch totals and reconstructed Excel SKU amounts passed',merged_totals={k:state[k] for k in ('merged_qty','merged_gross','merged_net')})
(OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
