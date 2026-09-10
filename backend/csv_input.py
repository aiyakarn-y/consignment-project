"""Read CSV as literal cells for the shared tabular mapping pipeline."""
import csv
import io
import openpyxl


def csv_workbook(content):
    if len(content) > 25 * 1024 * 1024:
        raise ValueError('CSV ต้องไม่เกิน 25 MB')
    if content.startswith((b'\xff\xfe', b'\xfe\xff')):
        encoding = 'utf-16'
    else:
        encoding = 'utf-8-sig'
    try:
        text = content.decode(encoding)
    except UnicodeError:
        try:
            text = content.decode('cp874')
        except UnicodeError:
            raise ValueError('CSV ต้องเป็น UTF-8, UTF-16 พร้อม BOM หรือ Windows-874') from None
    if not text.strip() or any(ord(c) < 32 and c not in '\r\n\t' for c in text):
        raise ValueError('CSV ว่างหรือมีข้อมูลที่ไม่ใช่ข้อความ')
    try:
        dialect = csv.Sniffer().sniff(text[:65536], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'CSV'
    count = 0
    try:
        for index, values in enumerate(csv.reader(io.StringIO(text, newline=''), dialect, strict=True), 1):
            count += len(values)
            if index > 50000 or len(values) > 200 or count > 1000000:
                raise ValueError('CSV รองรับไม่เกิน 50,000 แถว / 200 คอลัมน์ / 1,000,000 ช่อง')
            for col, value in enumerate(values, 1):
                if len(value) > 32767:
                    raise ValueError(f'CSV แถว {index}: ข้อความในช่องยาวเกินกำหนด')
                cell = sheet.cell(index, col, value)
                cell.data_type = 's'  # Never interpret formulas or numeric SKU text.
        return workbook
    except (csv.Error, ValueError) as exc:
        workbook.close()
        raise ValueError('อ่าน CSV ไม่สำเร็จ: '+str(exc)) from None
