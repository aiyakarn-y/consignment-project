import {test,expect} from '../../frontend/node_modules/@playwright/test';

test('history pagers navigate independently, resize, and retain page on failure',async({page})=>{
 let failExport=false;
 const requests:string[]=[];
 await page.route(/\/api\/(import|export)-history\?/,async route=>{
  const url=new URL(route.request().url());requests.push(url.pathname+url.search);
  if(failExport&&url.pathname.endsWith('export-history')){
   failExport=false;await route.fulfill({status:500,json:{detail:'ลองโหลดประวัติอีกครั้ง'}});return;
  }
  const size=Number(url.searchParams.get('size')),current=Number(url.searchParams.get('page'));
  const total=121,start=(current-1)*size;
  const rows=Array.from({length:Math.min(size,total-start)},(_,index)=>{
   const id=String(start+index+1);
   return {id,at:'2026-08-01T00:00:00Z',batch_id:'fixture',filename:`export-${id}.xlsx`,name:`import-${id}.xlsx`,period:'2026-08',snapshot:{period:'2026-08'},rows:1,source_rows:1,scope:'all',skipped_rows:0,previous_identical_exports:0,duplicate_override:false,error:null,source_available:true};
  });
  await route.fulfill({json:{rows,total,page:current,size,pages:Math.ceil(total/size)}});
 });
 await page.goto('/');await page.getByRole('button',{name:'ตั้งค่า / ประวัติ',exact:true}).click();
 await page.getByRole('button',{name:'ประวัติ Import / Export',exact:true}).click();
 const exports=page.getByRole('navigation',{name:'แบ่งหน้าประวัติ Export'});
 const imports=page.getByRole('navigation',{name:'แบ่งหน้าประวัติ Import'});
 await expect(exports).toContainText('1–20 จาก 121');
 await page.getByLabel('ประวัติ Export หน้าถัดไป',{exact:true}).click();
 await expect(exports).toContainText('21–40 จาก 121');
 await expect(imports).toContainText('1–20 จาก 121');
 await expect(page.locator('tbody tr').filter({hasText:'export-21.xlsx'})).toBeVisible();
 await page.getByLabel('จำนวนประวัติ Export ต่อหน้า').selectOption('100');
 await expect(exports).toContainText('1–100 จาก 121');
 await page.getByLabel('ประวัติ Export หน้าถัดไป',{exact:true}).click();
 await expect(exports).toContainText('101–121 จาก 121');
 await expect(page.getByLabel('ประวัติ Export หน้าถัดไป',{exact:true})).toBeDisabled();
 await page.getByLabel('จำนวนประวัติ Import ต่อหน้า').selectOption('50');
 await expect(imports).toContainText('1–50 จาก 121');
 await page.getByLabel('ประวัติ Import หน้าถัดไป',{exact:true}).click();
 await expect(imports).toContainText('51–100 จาก 121');
 failExport=true;
 await page.getByLabel('ประวัติ Export หน้าก่อน',{exact:true}).click();
 await expect(page.locator('.operations-panel [role=alert]')).toContainText('ลองโหลดประวัติอีกครั้ง');
 await expect(exports).toContainText('101–121 จาก 121');
 await page.getByLabel('ประวัติ Export หน้าก่อน',{exact:true}).click();
 await expect(exports).toContainText('1–100 จาก 121');
 expect(requests.some(r=>r.includes('export-history?page=2&size=20'))).toBe(true);
 expect(requests.some(r=>r.includes('import-history?page=2&size=50'))).toBe(true);
 await page.setViewportSize({width:390,height:844});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
