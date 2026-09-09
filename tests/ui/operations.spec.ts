import {test,expect} from '../../frontend/node_modules/@playwright/test';
import {execFileSync} from 'node:child_process';
import path from 'node:path';

test('configure XLSX → valuation → duplicate audit → export history → backup/restore',async({page,request})=>{
 const source=execFileSync('.venv/bin/python',['-c',"import openpyxl,io,sys; w=openpyxl.Workbook();s=w.active;s.title='Sales';s.append(['SKU','Qty','Price','Cost','Amount','Cost amount']);s.append(['CUSTOM-E2E',2,107,101,214,202]);b=io.BytesIO();w.save(b);sys.stdout.buffer.write(b.getvalue())"]);
 const file={name:'new-format.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:source};
 await page.goto('/');await page.getByRole('button',{name:'ตั้งค่า / ประวัติ',exact:true}).click();
 await page.getByLabel('ชื่อรูปแบบนำเข้า').fill('Custom E2E');
 await page.getByLabel('ไฟล์ตัวอย่างรูปแบบใหม่').setInputFiles(file);
 await page.getByRole('button',{name:'อ่านชีตและหัวตาราง',exact:true}).click();
 await expect(page.getByLabel('ชีตรูปแบบใหม่')).toHaveValue('Sales');
 for(const [field,column] of Object.entries({sku:'A',qty:'B',price:'C',cost_price:'D',gross:'E',cost_total:'F'}))await page.getByLabel('คอลัมน์ '+field,{exact:true}).selectOption(column);
 await page.getByLabel('ลูกค้ารูปแบบใหม่').fill('Custom Shop');
 await page.getByRole('button',{name:'ดูตัวอย่าง Mapping',exact:true}).click();
 await expect(page.locator('.ops-preview-result')).toContainText('อ่าน 1 รายการ · พร้อม 1');
 await page.screenshot({path:'_wrx-output/evidence/operations-profile-preview.png',fullPage:true});
 await page.getByRole('button',{name:'บันทึกรูปแบบ',exact:true}).click();
 await expect(page.locator('.operations-panel [role=status]')).toContainText('บันทึกรูปแบบ Custom E2E');
 const profiles=await (await request.get('/api/profiles')).json();const profile=profiles.find((p:{config:{name:string}})=>p.config.name==='Custom E2E');
 await page.getByLabel('รูปแบบสำหรับ Import').selectOption(profile.id);
 await page.getByLabel('อัปโหลดรายงาน').setInputFiles(file);
 await expect(page.locator('.stat').filter({hasText:'รายการขาย'}).locator('strong')).toContainText('1');
 await page.getByRole('button',{name:'ฐานราคา / VAT',exact:true}).click();
 await page.getByLabel('ลูกค้าฐานราคา').fill('Custom Shop');
 await page.getByLabel('ฐาน sale_basis').selectOption('included');await page.getByLabel('ฐาน cost_basis').selectOption('excluded');await page.getByLabel('ฐาน settlement_basis').selectOption('excluded');
 await page.getByLabel('หมายเหตุฐานราคา').fill('E2E source basis');
 await page.getByLabel('ใช้กับรายการของลูกค้านี้ในชุดที่เปิดอยู่ด้วย').check();
 await page.getByRole('button',{name:'บันทึกฐานราคา',exact:true}).click();
 await expect(page.locator('.operations-panel [role=status]')).toContainText('ปรับใช้ 1 รายการ');
 const batches=await (await request.get('/api/batches')).json();const b=batches[0];
 const rows=await (await request.get(`/api/batches/${b.id}/rows`)).json();expect(rows.rows[0].comparison_sale_price).toBe('100');expect(rows.rows[0].price).toBe('107');
 for(let i=0;i<2;i++){
  const pending=page.waitForEvent('download');await page.getByRole('button',{name:'Export Excel',exact:true}).click();await pending;
  await expect(page.getByRole('dialog',{name:'กำลังดำเนินการ'})).toHaveCount(0);
 }
 await expect(page.locator('.main-content>.notice')).toContainText('เคย Export แล้ว 1 ครั้ง');
 await page.getByRole('button',{name:'ประวัติ Import / Export',exact:true}).click();
 await expect(page.locator('.operations-panel')).toContainText('เคยสร้างแล้ว 1 ครั้ง');
 await page.getByRole('button',{name:'สำรอง / กู้คืน',exact:true}).click();
 const backupDownload=page.waitForEvent('download');await page.getByRole('button',{name:'สร้างและดาวน์โหลดไฟล์สำรอง',exact:true}).click();const backup=await backupDownload;
 const backupPath=path.resolve('_wrx-output/evidence/operations-e2e-backup.zip');await backup.saveAs(backupPath);
 await expect(page.locator('.operations-panel [role=status]')).toContainText('สำรองแล้ว 1 ชุด');
 page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'ล้างข้อมูลนำเข้าทั้งหมด',exact:true}).click();await expect(page.locator('.main-content>.notice')).toContainText('ล้างข้อมูลนำเข้าแล้ว');
 // Registry survives clearing: cancel accidental re-import, preserving an empty batch.
 page.once('dialog',d=>d.dismiss());await page.getByLabel('อัปโหลดรายงาน').setInputFiles({...file,name:'renamed.xlsx'});await expect(page.locator('.main-content>.notice')).toContainText('ยกเลิกการนำเข้าซ้ำแล้ว');
 await page.getByRole('button',{name:'ตั้งค่า / ประวัติ',exact:true}).click();await page.getByRole('button',{name:'สำรอง / กู้คืน',exact:true}).click();
 await page.getByLabel('ไฟล์สำรองสำหรับกู้คืน').setInputFiles(backupPath);
 await expect(page.locator('.backup-preview')).toContainText('1 ชุด · 1 รายการ');
 await page.getByLabel('ยืนยันแทนที่ข้อมูลจากสำรอง').check();page.once('dialog',d=>d.accept());
 await page.getByRole('button',{name:'กู้คืนข้อมูลที่ตรวจแล้ว',exact:true}).click();
 await expect(page.locator('.operations-panel [role=status]')).toContainText('กู้คืนข้อมูลสำเร็จ');
 expect((await (await request.get('/api/batches')).json())[0].id).toBe(b.id);
 expect((await (await request.get('/api/export-history')).json()).length).toBe(2);
 await expect(page.getByRole('link',{name:'ดาวน์โหลดสำรองก่อนกู้คืนครั้งล่าสุด'})).toBeVisible();
 await page.screenshot({path:'_wrx-output/evidence/operations-restored.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await request.delete('/api/batches'); // Isolated test DB only; next workflow starts empty.
});
