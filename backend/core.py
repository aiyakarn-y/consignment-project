"""Decimal-based normalization. No spreadsheet formulas are evaluated."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from pathlib import Path
from copy import copy
import re
import openpyxl
import pdfplumber

D = Decimal
CENT = D('0.01')
PERCENT_STEP = D('0.0000000001')
SKU_RE = re.compile(r'(?<![A-Z0-9])((?:WA|WP|WS|WR|CA|WC|LA)-[A-Z0-9]+(?:-[A-Za-z0-9_\u0E00-\u0E7F]+)*)', re.I)


def dec(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        n = D(str(value).replace(',', '').strip())
        if not n.is_finite() or abs(n) > D('1e14'):
            raise ValueError('ตัวเลขอยู่นอกช่วงที่รองรับ')
        return n
    except InvalidOperation:
        raise ValueError(f'ไม่ใช่ตัวเลข: {str(value)[:60]}')


def fmt(n):
    if n is None:
        return None
    s = format(n, 'f')
    return s.rstrip('0').rstrip('.') if '.' in s else s


def money(n):
    return n.quantize(CENT, rounding=ROUND_HALF_UP)


def percent(text):
    """Return retained fraction; 20%+5% means successive reductions."""
    if text is None or str(text).strip() == '':
        return None
    result = D(1)
    parts = str(text).replace(' ', '').split('+')
    for part in parts:
        if not re.fullmatch(r'\d+(?:\.\d+)?%?', part):
            raise ValueError('ส่วนลดต้องเป็น 25% หรือ 20%+5%')
        n = dec(part.rstrip('%'))
        if n < 0 or n > 100:
            raise ValueError('ส่วนลดต้องอยู่ระหว่าง 0–100%')
        result *= 1 - n / 100
    return result


def discount_text(text):
    percent(text)
    return '+'.join(fmt(dec(p.strip().rstrip('%'))) + '%' for p in str(text).split('+'))


def export_discount(text):
    """Excel's text Discount column uses two decimals per sequential component."""
    percent(text)
    return '+'.join(f"{dec(part.strip().rstrip('%')).quantize(CENT, rounding=ROUND_HALF_UP):.2f}%"
                    for part in str(text).split('+'))


def export_net(r):
    return money(dec(str(float(dec(r['price'])))) * dec(str(float(dec(r['qty']))))
                 * percent(export_discount(r['discount'])))


def reverse_discount(price, net):
    if price is None or net is None or price == 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 40
        return fmt(((1 - net / price) * 100).quantize(PERCENT_STEP, rounding=ROUND_HALF_UP)) + '%'


def source_discount(value,gross,net,qty):
    """Resolve unlabeled input only when sales totals substantiate its meaning."""
    text=str(value).strip()
    if '%' in text or '+' in text:
        return discount_text(text),'อ่านจากไฟล์'
    cash=text.endswith('บาท')
    amount=dec(text.removesuffix('บาท').strip())
    if amount is None:
        return '', 'รอข้อมูล'
    candidates=[]
    if not cash and 0<=amount<=100:
        candidates.append((discount_text(fmt(amount)),'อ่านจากไฟล์'))
    if not cash and 0<amount<1:
        candidates.append((discount_text(fmt(amount*100)),'ตรวจอัตราส่วนกับยอดขายสุทธิ'))
    if gross is not None and net is not None and gross!=0:
        matches=[c for c in candidates if money(gross*percent(c[0]))==money(net)]
        if len(matches)==1:
            return matches[0]
        if matches:
            raise ValueError('อัตราส่วน/เปอร์เซ็นต์ตีความได้หลายแบบ กรุณาระบุ % ให้ชัดเจน')
        # A numeric discount may be an amount for the line or per unit.
        amounts=[amount]+([amount*qty] if qty is not None else [])
        if any(money(gross-a)==money(net) for a in amounts):
            return reverse_discount(gross,net),'คำนวณจากยอดขายและส่วนลดเป็นเงิน'
    if cash:
        if net is None:return '', 'ข้อมูลไม่พอคำนวณจากส่วนลดเป็นเงิน'
        raise ValueError('ส่วนลดเป็นเงินต้องมียอดขายก่อนหักและยอดสุทธิที่ตรงกันให้ตรวจสอบ')
    if 0<amount<1 and net is None:
        return '', 'ไม่มีฐานสุทธิให้ยืนยันเปอร์เซ็นต์'
    if candidates:
        return candidates[0]  # validate() will expose a net mismatch, never hide it.
    raise ValueError('ส่วนลดไม่อยู่ในช่วงเปอร์เซ็นต์และเทียบยอดขายไม่ได้')


def code(value):
    if value is None:
        return ''
    return str(int(value)) if isinstance(value, (int, float)) and value == int(value) else str(value).strip()


def sku_in(text):
    m = SKU_RE.search(str(text or '').upper())
    return m.group(1) if m else ''


def row(source, sheet, line, customer, branch, sku, qty, price=None,
        discount=None, gross=None, net=None, barcode='', partner='', vat='ไม่ระบุ',
        date='', notes=None, raw=None):
    qty, price, gross, net = map(dec, (qty, price, gross, net))
    if price is None and qty and gross is not None:
        price = gross / qty
    if gross is None and price is not None and qty is not None:
        gross = price * qty
    origin = 'อ่านจากไฟล์'
    discount_issue = None
    if discount is not None and str(discount).strip()=='':
        discount=None
    if discount is None and price and qty and net is not None:
        discount = reverse_discount(price * qty, net)
        origin = 'คำนวณย้อนกลับ'
    elif discount is not None:
        try:
            discount,origin=source_discount(discount,gross,net,qty)
        except ValueError as ex:
            discount_issue=str(ex)
            discount=None
    if discount is None:
        origin = 'รอข้อมูล'
    return dict(source=source, sheet=sheet, line=line, customer=customer,
                branch=branch or 'ไม่ระบุสาขา', sku=sku or '', barcode=code(barcode), partner=code(partner),
                qty=fmt(qty), price=fmt(price), discount=discount or '', gross=fmt(gross),
                net=fmt(net), vat=vat, date=str(date or ''), notes=notes or [], raw=raw or {},
                discount_issue=discount_issue, discount_origin=origin, sku_origin='อ่านจากไฟล์' if sku else 'รอข้อมูล', edits=[])


def source_costs(r):
    """Read immutable source cost columns, separate from editable settlement net."""
    raw=r.get('raw',{});customer=r.get('customer')
    unit=total=q=exvat=None;origin='ต้นทางไม่ระบุต้นทุน'
    if r.get('custom_source') is not None:
        source=r['custom_source'];unit=dec(source.get('cost_price'));total=dec(source.get('cost_total'));q=dec(source.get('qty'))
        if unit is None and total is not None and q:unit=total/q
        origin='คอลัมน์ต้นทุนจากรูปแบบนำเข้าที่ตั้งค่า'
    elif customer=='Big C':
        unit=dec(raw.get('L'));q=dec(raw.get('K'));exvat=dec(raw.get('P'))
        total=money(unit*q) if unit is not None and q is not None else None
        origin='ราคาทุน L × จำนวน K; คนละยอดกับยอดหลัง GP'
    elif customer=='KING POWER':
        unit=dec(raw.get('E'));q=dec(raw.get('F'));total=dec(raw.get('I'))
        origin='UNIT COST E / COST AMT I'
    elif customer=='Outcast':
        unit=dec(raw.get('H'));q=dec(raw.get('I'));total=dec(raw.get('K'))
        origin='Cost Inc. Vat H / AMT Inc. Vat K'
    elif customer=='PDF ส่งเงินคืน':
        m=re.search(r'\s(\d+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$',raw.get('text',''))
        if m:
            q=dec(m[1]);total=dec(m[3]);unit=total/q if q else None
            origin='ต้นทุนส่งคืนรวม ÷ จำนวน (คำนวณราคาต่อหน่วย)'
    delta=money(unit*q)-money(total) if None not in (unit,q,total) else None
    r.update(source_cost_price=fmt(unit),source_cost_total=fmt(total),source_cost_delta=fmt(delta),
             source_cost_origin=origin,source_sales_ex_vat=fmt(exvat))
    return delta


def rate_provenance(r):
    raw=r.get('raw',{});gp=mg=None
    if r.get('custom_source') is not None:
        gp=r['custom_source'].get('gp');mg=r['custom_source'].get('mg')
        if mg and not str(mg).endswith('%'):mg=str(mg)+'%'
    elif r.get('customer')=='Big C' and raw.get('J') not in (None,''):
        gp=source_discount(raw['J'],dec(raw.get('M')),dec(raw.get('T')),dec(raw.get('K')))[0] or None
    elif r.get('customer')=='Outcast' and raw.get('F') not in (None,''):
        gp=source_discount(raw['F'],dec(raw.get('J')),dec(raw.get('K')),dec(raw.get('I')))[0] or None
    elif r.get('customer')=='KING POWER' and raw.get('J') not in (None,''):
        # MG is informational; never feed it into GP or fallback discount selection.
        mg=code(raw['J']).rstrip('%')+'%'
    origin=r.get('discount_origin','')
    if r.get('discount_defaulted'):kind='ค่าเริ่มต้น 0%'
    elif 'ผู้ใช้' in origin or 'กติกา' in origin:kind='ส่วนลดที่ผู้ใช้กำหนด'
    elif gp is not None:kind='ส่วนลด/GP ตามคอลัมน์ที่ตั้งค่า' if r.get('custom_source') is not None else 'GP จากต้นทาง'
    elif 'คำนวณ' in origin:kind='ส่วนลดเทียบเท่าจากยอดขาย/ต้นทุนหรือยอดส่งคืน (ไม่ยืนยัน GP)'
    else:kind='ส่วนลดจากต้นทาง'
    r.update(source_gp=gp,source_mg=mg,discount_kind=kind)


def below_cost_snapshot(r):
    return {k:r.get(k) for k in ('sku','customer','branch','branch_code','price','qty','discount','net','gross','source_cost_price','source_cost_total','vat','valuation')}


def comparison_values(r):
    p,q,c,n=(dec(r.get(k)) for k in ('price','qty','source_cost_price','calculated_net'))
    cfg=r.get('valuation') or {};known=cfg.get('sale_basis') in ('included','excluded') and cfg.get('cost_basis') in ('included','excluded')
    if known:
        divisor=1+dec(cfg.get('vat_rate','7'))/100
        if cfg['sale_basis']=='included' and p is not None:p=p/divisor
        if cfg['cost_basis']=='included' and c is not None:c=c/divisor
        if cfg.get('settlement_basis')=='included' and n is not None:n=n/divisor
        elif cfg.get('settlement_basis')!='excluded':n=None
    return p,q,c,n,'ex_vat' if known else 'source_unverified'


def below_cost_review(r):
    p,q,c,n,basis=comparison_values(r)
    flag=None not in (p,q,c) and q>0 and p<c
    history=r.setdefault('below_cost_confirmations',[])
    latest=history[-1] if history else None
    current=bool(flag and latest and latest.get('snapshot')==below_cost_snapshot(r))
    r.update(comparison_basis=basis,comparison_sale_price=fmt(p),comparison_cost_price=fmt(c),
             below_cost_status=('confirmed' if current else 'pending') if flag else 'none',
             below_cost_confirmation=latest if current else None,
             below_cost_sales=fmt(money(p*q)) if flag else None,
             below_cost_total=fmt(money(c*q)) if flag else None,
             below_cost_difference=fmt(money(c*q)-money(p*q)) if flag else None,
             below_cost_after_discount_difference=fmt(money(c*q)-money(n)) if flag and n is not None else None)


def validate(r):
    errors = [r['discount_issue']] if r.get('discount_issue') else []
    warnings = list(r.get('notes', []))
    # Existing rows also recover references; never invent missing color/size or use barcode.
    if not r.get('sku'):
        reference=sku_in(r.get('raw',{}).get('D')) if r.get('customer')=='Outlet G624' else ''
        if reference:
            r.update(sku=reference,sku_origin='รหัสจากชื่อสินค้าต้นทาง')
        elif r.get('partner'):
            r.update(sku=code(r['partner']),sku_origin='ใช้รหัสอ้างอิงสินค้าต้นทาง · แก้ไขได้')
    if not r.get('sku') or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.\-/\u0E00-\u0E7F]*', r['sku']):
        errors.append('ต้องระบุ SKU ที่ถูกต้อง')
    r['calculated_gross']=None
    try:
        cost_delta=source_costs(r)
        if cost_delta is not None and cost_delta!=0:errors.append('ราคาต้นทุน × จำนวนไม่ตรงยอดต้นทุนต้นทาง')
        q, p, g, n = (dec(r.get(k)) for k in ('qty', 'price', 'gross', 'net'))
        # Covers both new uploads and historical batches without rewriting originals.
        if not str(r.get('discount') or '').strip() and not r.get('discount_issue'):
            if p and q and n is not None:
                r['discount']=reverse_discount(p*q,n)
                r['discount_origin']='คำนวณย้อนกลับ'
                r['discount_defaulted']=False
            else:
                r['discount']='0%'
                r['discount_origin']='ค่าเริ่มต้น 0% · แก้ไขได้'
                r['discount_defaulted']=True
        if r.get('discount_defaulted'):
            warnings.append('ต้นทางไม่มีส่วนลดหรือข้อมูลไม่พอคำนวณ: ใช้ค่าเริ่มต้น 0% แก้ไขได้')
        compared_p,compared_q,compared_c,_,_=comparison_values(r)
        if None not in (compared_p,compared_q,compared_c) and compared_q>0 and compared_c>compared_p:
            warnings.append('ราคาต้นทุนต่อหน่วยสูงกว่าราคาขายในฐานที่ใช้เทียบ: คงค่าต้นทางไว้ให้ตรวจสอบ')
        factor = percent(r.get('discount'))
        if q is None or q == 0:
            errors.append('จำนวนต้องไม่เป็นศูนย์')
        if p is None or p <= 0:
            errors.append('ต้องระบุราคาก่อนหักมากกว่า 0')
        if factor is None:
            errors.append('ขาดส่วนลดหรือราคาสุทธิสำหรับคำนวณ')
        r['calculated_gross']=fmt(money(p*q)) if None not in (p,q) else None
        calculated = p * q * factor if None not in (p, q, factor) else None
        if g is not None and p is not None and q is not None and money(p*q) != money(g):
            errors.append('ราคา × จำนวนไม่ตรงยอดก่อนหักต้นทาง')
        if n is not None and calculated is not None and money(calculated) != money(n):
            errors.append('ยอดสุทธิไม่ตรงต้นทาง')
        if q is not None and q < 0:
            warnings.append('จำนวนติดลบ: คงตามต้นทาง')
        delta = money(calculated) - money(n) if calculated is not None and n is not None else None
        r.update(calculated_net=fmt(money(calculated)) if calculated is not None else None, delta=fmt(delta))
    except (ValueError, InvalidOperation) as ex:
        errors.append(str(ex))
        r.update(calculated_net=None, delta=None)
    try:rate_provenance(r)
    except (ValueError,InvalidOperation):
        r.update(source_gp=None,source_mg=None,discount_kind='ต้องตรวจรูปแบบอัตราต้นทาง')
    if r.get('vat') == 'ไม่ระบุ':
        warnings.append('ไม่ทราบฐาน VAT: ไม่มีการบวกหรือถอด VAT เพิ่ม')
    try:below_cost_review(r)
    except (ValueError,InvalidOperation):r.update(below_cost_status='none',below_cost_confirmation=None)
    r.update(errors=errors, warnings=list(dict.fromkeys(warnings)), status='blocked' if errors else 'ready')
    return r


def sheet_kind(ws):
    if str(ws['A1'].value).strip()=='รหัสร้านค้า' and str(ws['G1'].value).strip()=='รหัสสาขา':return 'Big C'
    if ws['C3'].value=='รหัสสินค้า' and 'ยอดขาย' in str(ws['E3'].value):return 'Outlet G624'
    if 'REFERENCE' in str(ws['C2'].value) and 'QTY' in str(ws['F2'].value):return 'KING POWER'
    if str(ws['B6'].value).strip()=='BARCODE EAN13':return 'Outcast'
    return ''


def parse_xlsx(path, name, sheets=None):
    wb=openpyxl.load_workbook(path,data_only=True)
    try:
        if len(wb.sheetnames)==1 and [wb.active.cell(1,c).value for c in range(1,5)]==['Items','Price','Qty','Discount']:
            raise ValueError('ไฟล์รูปแบบแม่แบบ: ใช้รายงานขายต้นทางแทนไฟล์ Export')
        candidates=[ws.title for ws in wb if sheet_kind(ws)]
        if sheets is None and len(candidates)>1:
            raise ValueError('พบหลายชีตข้อมูล กรุณาเลือกชีตที่ต้องการนำเข้าก่อน: '+', '.join(candidates))
        selected=candidates if sheets is None else sheets
        if not selected or len(selected)!=len(set(selected)) or any(n not in candidates for n in selected):
            raise ValueError('เลือกชีตข้อมูลที่รองรับอย่างน้อยหนึ่งชีตโดยไม่ซ้ำ')
        rows=[];kinds=[]
        for name_in_book in selected:
            parsed,kind=parse_xlsx_sheet(wb,wb[name_in_book],name)
            if not parsed:raise ValueError('ไม่พบรายการในชีตที่เลือก: '+name_in_book)
            rows.extend(parsed)
            if kind not in kinds:kinds.append(kind)
        return rows,' / '.join(kinds)
    finally:wb.close()


def parse_xlsx_sheet(wb, ws, name):
    out=[]
    def raw(ws, idx):
        return {c.column_letter: str(c.value) for c in ws[idx] if c.value is not None}
    detail = ws if sheet_kind(ws)=='Big C' else None
    if detail is not None:
        names = {}
        for ws in wb:
            if ws.title == 'Sheet3':
                for vals in ws.iter_rows(min_row=4, values_only=True):
                    if len(vals)>3 and code(vals[1]).isdigit() and vals[3] and not str(vals[3]).startswith('#'):
                        names[code(vals[1])] = str(vals[3]).strip()
        for i in range(2, detail.max_row+1):
            c = [detail.cell(i,j).value for j in range(1,21)]
            if c[0] is None:
                continue
            if not code(c[0]).isdigit():
                raise ValueError(f'แถว {i} ไม่ตรงรูปแบบรายละเอียด Big C')
            sku = code(c[3])
            if sku.startswith('#'):
                sku = ''
            notes = ['SKU จากค่าที่ Excel บันทึกไว้; ไม่คำนวณลิงก์ workbook ภายนอกใหม่']
            if str(c[8]).endswith('07-2026'):
                notes.append('วันที่กรกฎาคมในรายงานสิงหาคม: คงตามต้นทาง')
            out.append(row(name, detail.title, i, 'Big C', names.get(code(c[6]), code(c[7])), sku,
                c[10], c[13], c[9], c[12], c[19], c[2], c[4], 'รวม VAT ตามปลีก (invat)',
                str(c[8]), notes, raw(detail,i)))
            out[-1]['branch_code'] = code(c[6])
        return out, 'Big C'
    if ws['C3'].value == 'รหัสสินค้า' and 'ยอดขาย' in str(ws['E3'].value):
        for i in range(5,ws.max_row+1):
            if not ws.cell(i,3).value or str(ws.cell(i,1).value).lower().startswith('grand'):
                continue
            for j in range(5,16):
                q, g = dec(ws.cell(i,j).value), dec(ws.cell(i,j+12).value)
                if not q and not g:
                    continue
                out.append(row(name,ws.title,i,'Outlet G624',str(ws.cell(4,j).value),sku_in(ws.cell(i,4).value),
                    q,gross=g,partner=ws.cell(i,3).value,
                    notes=['SKU แยกจากชื่อสินค้า','ต้นทางไม่ระบุ GP: ใช้ค่าเริ่มต้น 0% และแก้ไขได้'],raw=raw(ws,i)))
                out[-1]['source_columns'] = f'{openpyxl.utils.get_column_letter(j)}/{openpyxl.utils.get_column_letter(j+12)}'
        return out,'Outlet G624'
    if 'REFERENCE' in str(ws['C2'].value) and 'QTY' in str(ws['F2'].value):
        for i in range(4,ws.max_row+1):
            if not code(ws.cell(i,1).value).isdigit():
                continue
            out.append(row(name,ws.title,i,'KING POWER','ไม่ระบุสาขา',code(ws.cell(i,3).value),
                ws.cell(i,6).value,ws.cell(i,4).value,gross=ws.cell(i,7).value,net=ws.cell(i,9).value,
                partner=ws.cell(i,1).value,
                notes=['ใช้ส่วนต่างรวมราคา/ต้นทุน; ไม่ใช้ MG% เป็น GP และไม่ถอด VAT ซ้ำ'],raw=raw(ws,i)))
        return out,'KING POWER'
    if str(ws['B6'].value).strip() == 'BARCODE EAN13':
        branch = 'ไม่ระบุสาขา'
        for i in range(7,ws.max_row+1):
            a,b = ws.cell(i,1).value,ws.cell(i,2).value
            if a and not b:
                branch = str(a)
            if not b:
                continue
            gp = ws.cell(i,6).value
            out.append(row(name,ws.title,i,'Outcast',branch,'',ws.cell(i,9).value,ws.cell(i,7).value,
                gp,ws.cell(i,10).value,ws.cell(i,11).value,b,a,
                'ยอดหลัง GP ระบุ Inc. Vat; Retail Price ไม่ระบุโดยตรง',notes=['ใช้รหัสสินค้าอ้างอิงต้นทางเมื่อไม่มี SKU; แก้ไขภายหลังได้'],raw=raw(ws,i)))
        return out,'Outcast'
    raise ValueError('ยังไม่รองรับรูปแบบ Excel นี้ กรุณาใช้รายงานรูปแบบเดียวกับชุดตัวอย่าง')


def parse_pdf(path,name):
    out=[]
    with pdfplumber.open(path) as pdf:
        for page_num,page in enumerate(pdf.pages,1):
            text=page.extract_text(layout=False) or ''
            if not text.strip():
                raise ValueError(f'PDF หน้า {page_num} ไม่มีข้อความ รองรับ PDF ข้อความเท่านั้นในเดโม')
            for i,line in enumerate(text.splitlines(),1):
                sku=sku_in(line)
                if not sku:
                    continue
                m=re.search(r'\s(\d+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s*$',line)
                if not m:
                    raise ValueError(f'อ่านจำนวนและยอด PDF หน้า {page_num} บรรทัด {i} ไม่ครบ')
                q,g,n=m.groups()
                out.append(row(name,f'หน้า {page_num}',i,'PDF ส่งเงินคืน','ไม่ระบุสาขา',sku,q,gross=g,net=n,
                    notes=['ส่วนลดคำนวณจากมูลค่าขายและต้นทุนส่งคืน'],raw={'text':line}))
            if page_num == len(pdf.pages):
                totals=re.search(r'รวม\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})',text)
                if totals and (money(sum((dec(r['gross']) for r in out),D(0))) != money(dec(totals[1])) or
                               money(sum((dec(r['net']) for r in out),D(0))) != money(dec(totals[2]))):
                    raise ValueError('ยอด PDF ที่อ่านได้ไม่ตรงบรรทัดรวม')
    if not out:
        raise ValueError('ไม่พบรายการ SKU และยอดใน PDF รูปแบบที่รองรับ')
    return out,'PDF ส่งเงินคืน'


def parse(path,name,sheets=None):
    if name.lower().endswith('.csv'):
        raise ValueError('CSV ต้องเลือกรูปแบบนำเข้า: สร้าง Mapping จากไฟล์ตัวอย่างในเมนูรูปแบบนำเข้า แล้วเลือกรูปแบบที่บันทึกไว้')
    if name.lower().endswith('.pdf'):
        rows,kind=parse_pdf(path,name)
    elif name.lower().endswith('.xlsx'):
        rows,kind=parse_xlsx(path,name,sheets=sheets)
    else:
        raise ValueError('รองรับ .xlsx และ .pdf เท่านั้น')
    if not rows:
        raise ValueError('ไม่พบรายการขายในไฟล์')
    return [validate(r) for r in rows],kind


def merge_sku(rows):
    """One SKU only, signed quantities, cent-level source totals preserved."""
    if not rows:
        raise ValueError('ไม่พบรายการสำหรับรวม SKU')
    sku=rows[0]['sku'].strip()
    if any(r['sku'].strip()!=sku for r in rows):
        raise ValueError('รวมได้เฉพาะ SKU เดียวกัน')
    qty=sum((dec(r['qty']) for r in rows),D(0))
    gross=sum((money(dec(r['price'])*dec(r['qty'])) for r in rows),D(0))
    net=sum((money(dec(r['calculated_net'])) for r in rows),D(0))
    if qty==0:
        raise ValueError(f'SKU {sku}: จำนวนรวมเป็นศูนย์ กรุณาตรวจรายการขาย/คืนก่อนส่งออก')
    price=(gross/qty).quantize(PERCENT_STEP,rounding=ROUND_HALF_UP)
    if price<=0:
        raise ValueError(f'SKU {sku}: ราคาหลังรวมไม่เป็นบวก กรุณาตรวจราคาและรายการคืน')
    discounts={r['discount'] for r in rows}
    discount=next(iter(discounts)) if len(discounts)==1 else None
    if discount is None or money(price*qty*percent(discount))!=money(net):
        discount=reverse_discount(price*qty,net)
    result=row('รวม SKU','รวมรายการ',0,'ทุกลูกค้า','ทุกสาขา',sku,qty,price,discount,gross,net,
        notes=['รวมตาม SKU เท่านั้น; ไม่ใช้ Barcode เป็นเงื่อนไข'])
    result['source_count']=len(rows)
    result['source_ids']=[r.get('id') for r in rows]
    if validate(result)['errors']:
        raise ValueError(f'SKU {sku}: รวมแล้วแสดงยอดในแม่แบบไม่ได้ — '+ '; '.join(result['errors']))
    # Match Excel's stored number precision as well as our Decimal calculation.
    numeric=dict(result,price=str(float(price)),qty=str(float(qty)))
    if validate(numeric)['errors']:
        raise ValueError(f'SKU {sku}: ความละเอียดราคาหลังรวมทำให้ยอดคลาดเคลื่อน')
    return result


def review_and_merge(rows):
    """Rebuild derived status from sources. Never change persisted business values."""
    from collections import defaultdict
    groups=defaultdict(list)
    for r in rows:
        validate(r)
        if r['status']=='ready':
            groups[r['sku'].strip()].append(r)
    merged=[]
    for members in groups.values():
        try:
            merged.append(merge_sku(members))
        except ValueError as ex:
            for r in members:
                r['errors'].append(str(ex))
                r['status']='blocked'
    return merged


def export_xlsx(rows,template,path):
    if not rows or any(validate(r)['errors'] for r in rows):
        raise ValueError('ต้องแก้รายการที่ไม่พร้อมทั้งหมดก่อน export')
    wb=openpyxl.load_workbook(template)
    ws=wb['Sample']
    for column, title in enumerate(('Items', 'Price', 'Qty', 'Discount'), 1):
        ws.cell(1, column, title)
    styles=[copy(ws.cell(2,c)._style) for c in range(1,5)]
    height=ws.row_dimensions[2].height
    ws.delete_rows(2,ws.max_row)
    for i,r in enumerate(rows,2):
        # Match the exact numeric representation we will write, then reconcile it again.
        exported=dict(r,price=str(float(dec(r['price']))),qty=str(float(dec(r['qty']))))
        if validate(exported)['errors']:
            raise ValueError('ความละเอียดตัวเลขใน Excel ทำให้ยอดคลาดเคลื่อน')
        values=[r['sku'],float(dec(r['price'])),float(dec(r['qty'])),export_discount(r['discount'])]
        for c,value in enumerate(values,1):
            cell=ws.cell(i,c,value);cell._style=copy(styles[c-1])
            if c in (1,4): cell.data_type='s'
        ws.row_dimensions[i].height=height
    wb.save(path)
    wb.close()
