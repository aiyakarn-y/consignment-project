# รีวิว Consign Studio — 9 กันยายน 2026

PATH C / codex-only. ขอบเขต: ตรวจโค้ด backend/UI, คำนวณ, Import/Export, Mapping, ประวัติ, Backup/Restore และจำลองกรณีที่ชุดทดสอบเดิมไม่ครอบคลุม ไม่แก้โปรแกรม ไม่เปลี่ยนข้อมูลจริง ไม่เปิดเซิร์ฟเวอร์จริง

## ผลตรวจ

- Python regression 68 passed, 2 warnings จาก test-client dependencies
- TypeScript `npm run typecheck`: passed
- ตรวจไฟล์ต้นฉบับ 5 แหล่งอีกครั้งด้วย `scripts/audit-prices-costs.py`: 3,896 แถว, 4,795 ชิ้น, 49 กลุ่มสาขา, Export 1,008 SKU; ยอดขาย 1,192,677 และยอดหลังส่วนลดคำนวณ 901,536.74 ตรงกับกติกาปัจจุบัน (รวม Outlet ส่วนลดเริ่มต้น 0%)
- ตรวจรายแถว, control totals, รวมสาขา และอ่าน Excel ที่สร้างกลับมาเทียบ ผ่าน ไม่ใช่การรับรองความหมายต้นทุน/ฐาน VAT ที่ Sales ยังไม่ยืนยัน
- กรณีใหม่ด้านล่างจำลองด้วย Python/FastAPI TestClient ใน temporary directory แยกทั้งหมด: `_wrx-output/evidence/project-review/probes.py` และ `probes.json`
- ไม่ได้รัน browser E2E หรือ production build ใหม่ในการรีวิวครั้งนี้ เพราะไม่ได้เปลี่ยนโปรแกรม; ได้ตรวจโค้ด UI และ typecheck เพิ่ม
- พอร์ต 3117 และ 8100 ไม่มี listener หลังตรวจ เดโมยังหยุดอยู่

## จุดที่ยืนยันซ้ำได้และควรแก้

### R1 — สำคัญ: Profile ไม่ตรวจว่าหัวคอลัมน์เปลี่ยนตำแหน่ง
ตำแหน่ง: `backend/import_profiles.py:75–78`.
Profile จำ B=Qty, C=Price แต่ไฟล์ใหม่สลับเป็น B=Price, C=Qty. ข้อมูลจริง 2 ชิ้น × 100 ถูกอ่านเป็น 100 ชิ้น × 2 ยอดรวมยัง 200 จึง status=ready ไม่มี errors. การตรวจยอดรวมอย่างเดียวจับไม่ได้
เสนอ: บันทึกหัวตารางที่คาดหวังพร้อมเวอร์ชัน ตรวจทุกครั้งก่อน Import; หากต่างให้ Preview/Mapping ใหม่ ไม่เดาตำแหน่งใหม่เงียบ ๆ และตรวจคอลัมน์ที่จำเป็นไม่ให้ชี้ช่องเดียวกันโดยไม่ตั้งใจ

### R2 — สำคัญ: อ่านอัตโนมัติจบเมื่อพบชีตแรกที่รองรับ
ตำแหน่ง: `backend/core.py:341` และ return ของ Outlet/Outcast; Big C เลือก detail แรก.
สร้าง workbook KING POWER สองชีต ชีตละหนึ่งสินค้า อ่านได้สินค้าเฉพาะชีตแรก ไม่มีคำเตือนอีกชีต
เสนอ: แสดงชีตทั้งหมดและผลรายชีต เลือกชีตข้อมูลที่จะนำเข้า ชีตสรุป/ช่วยคำนวณต้องข้ามอย่างชัดเจน ป้องกันรวมซ้ำจากชีตสรุป และเทียบยอดควบคุมรายไฟล์/ชีต การตั้งค่า Profile ปัจจุบันเลือกได้หนึ่งชีตตาม config แต่ตัวอ่านอัตโนมัติไม่แสดงชีตที่ข้าม

### R3 — สำคัญ: Profile ใช้ต้นทุนรวมเป็นยอดสุทธิโดยอัตโนมัติ
ตำแหน่ง: `backend/import_profiles.py:84–85`.
ตัวอย่างราคา100 จำนวน2 ต้นทุน60/ชิ้น ไม่มี net และ discount → สร้าง net120 และ discount40%, ready. พฤติกรรมนี้มีคำอธิบายใน UI แต่ไม่มีตัวเลือกบอกว่าต้นทุนคือยอดส่งคืนจริงหรือแค่ต้นทุนสินค้า
เสนอ: เพิ่ม net-source mode ต่อ Profile: ใช้ยอดสุทธิที่ map / ยืนยันใช้ต้นทุนเป็นยอดส่งคืน / ไม่มียอดสุทธิ. ใช้ต้นทุนย้อนส่วนลดเฉพาะเมื่อยืนยันความหมาย สำหรับไม่มีฐานสุทธิหรือส่วนลดให้คงนโยบายผู้ใช้ default0% แก้ภายหลังได้ และแสดงที่มา GP/MG แยกกัน โดยไม่เปลี่ยนกติกาแหล่งเดิมที่ตรวจยืนยันไว้

### R4 — สำคัญ: กู้คืนไม่ได้หากไฟล์ที่ข้อมูลปัจจุบันอ้างอิงหาย
ตำแหน่ง: `backend/operations.py:257`, `create_backup`.
มี ZIP สำรองที่ถูกต้อง แต่ทำไฟล์ source ปัจจุบันหาย → restore409 เพราะสำรองก่อนกู้คืนไม่ผ่าน การกู้คืนซึ่งควรช่วยในกรณีนี้ติดขัด
เสนอ: โหมดกู้คืนฉุกเฉินที่แจ้งรายการไฟล์ปัจจุบันที่หายและให้ยืนยันเฉพาะกรณี เก็บ DB/ไฟล์ที่ยังอ่านได้พร้อมรายงานข้อขาด แยกจาก backupสมบูรณ์ ไม่ปิด safetybackup เงียบ ๆ; archiveปลายทางต้องตรวจครบเหมือนเดิม

### R5 — สำคัญ: Clear ล้มเหลวกลางทางอาจเหลือฐานข้อมูลอ้างไฟล์ที่ลบไปแล้ว
ตำแหน่ง: `backend/app.py:176–180`.
จำลอง unlinkไฟล์แรกสำเร็จ ไฟล์ที่สอง OSError → HTTP500, SQLite rollback ให้ batchกลับมา แต่ไฟล์แรกหายแล้ว
เสนอ: commitการล้างข้อมูลธุรกิจก่อน cleanupไฟล์เป็นงานที่ทำซ้ำได้ (ล้มเหลวให้เหลือ orphan แทน missing reference) หรือใช้ staging/trash และรายการกู้กลับ พร้อมทดสอบ disk/permission error

### R6 — ปานกลาง: Master Mapping ไม่แทนรหัสอ้างอิงที่ใช้ชั่วคราว
ตำแหน่ง: `backend/app.py:58`, `backend/core.py:validate` fallback partner.
นำเข้า partnerREF-1 → ใช้เป็น SKUตามนโยบายเดิม จากนั้น Master Shop+REF-1→SKU-REAL บันทึกสำเร็จ1mapping แต่ resolved0 และยังส่งออก REF-1 เพราะ mappedทำงานเฉพาะ SKUว่าง เกิดเหมือนกันในการนำเข้าครั้งถัดไปที่ validatorเติมpartnerก่อนmapped
เสนอ: จัดลำดับ SKUที่ผู้ใช้แก้/ต้นทางจริง > Masterที่ยืนยัน > รหัสอ้างอิงชั่วคราว เพิ่ม Previewว่าจะเปลี่ยนกี่รายการ; ให้ Masterแทนเฉพาะค่าจาก fallback ไม่ทับ SKUจริงหรือค่าที่ผู้ใช้แก้ และไม่ใช้ barcodeเป็นเงื่อนไขรวมยอด

### R7 — ปานกลาง: อัปโหลดหลายไฟล์แล้วไฟล์หนึ่งเสีย จัดการผลไม่สม่ำเสมอ
ตำแหน่ง: `backend/app.py:206–208`.
ส่ง Excelดีตามด้วย broken.xlsx ที่ไม่ใช่ ZIP → HTTP400, รายการจากไฟล์ดีไม่ถูกบันทึก แต่ไฟล์สำเนาดีถูกเขียนค้างแล้ว แตกต่างจาก parseerrorที่บันทึกผลสำเร็จบางไฟล์
เสนอ: เลือกกติกาชัดเจน แนะนำรายงานผลรายไฟล์และบันทึกไฟล์ดีตามเจตนา UI partialsuccess หรือ rollbackทั้งชุดรวมไฟล์บนดิสก์; ตรวจซ้ำระหว่างไฟล์ในคำขอเดียวกันด้วย และให้ผู้ใช้ retryเฉพาะไฟล์ที่ไม่ผ่าน

## ส่วนที่ควรเพิ่มตามการใช้งานจริง (ข้อเสนอจากโค้ด ไม่ใช่ทั้งหมดเป็น bug)

1. รายการชุดข้อมูลย้อนหลังพร้อมค้นหา/แบ่งหน้า: APIคืน20ชุดล่าสุด (`backend/app.py:166`) แต่ sidebarแสดงเพียง6 (`app/page.tsx:108`), ไม่มีเปิดดูชุดเก่าทั้งหมดในUI ข้อมูลไม่ได้ถูกลบแต่เข้าถึงยาก
2. จัดการงวด: ค่าเริ่มต้น hardcode2026-08 (`app/page.tsx:41`, `backend/app.py:158`). ให้เลือกงวดชัดก่อน Import, เตือนวันที่นอกงวดโดยคงค่าต้นทาง และแก้งวดที่เลือกผิดได้พร้อม audit. ไม่ควรเดาว่าทุกไฟล์อยู่เดือนปัจจุบัน
3. จัดการ Profile/Mapping/กติกา: มีบันทึก/แก้Profileและฐานราคา แต่ไม่มีปิดใช้งาน/ลบProfile หรือหน้าดู/แก้ Mappingที่ขัดแย้ง รวมถึงยกเลิกกติกาที่จำไว้โดยคงค่าที่ Importแล้ว
4. ยอดควบคุมบนหน้าเว็บ: นำ control-total auditมาใช้กับทุกImport รองรับกำหนดแถว/ช่องยอดรวมในProfile และแสดงอ่าน/ข้ามกี่แถวพร้อมเหตุผล ขณะนี้ auditที่เข้มกว่าสำหรับExcelเป็นสคริปต์แยก ไม่ใช่ทุกImportผ่านUI
5. ป้องกันรายการธุรกิจซ้ำในไฟล์ที่ถูกแก้: hashปัจจุบันจับไฟล์เหมือนทุกbyteได้เท่านั้น เพิ่มคีย์เอกสาร/บรรทัด + ลูกค้า/สาขา/วันที่เมื่อมีแหล่งอ้างอิง ไม่ใช้SKUอย่างเดียว เพราะการขายSKUซ้ำคนละธุรกรรมเป็นเรื่องปกติ
6. ก่อนรวมSKUข้ามแหล่งให้แสดงฐานVATที่ต่างกันและกำหนดฐานExportที่ต้องการให้ชัด ปัจจุบันรวมตัวเลขต้นทางตามคำสั่งเดิมและไม่แปลงVAT การบังคับแปลงต้องตกลงกติกาปลายทางก่อน; ยังรวมSKUตามเดิมได้หลังฐานถูกกำหนด
7. ถ้าต้องการติดตามขาดทุนหลังส่วนลด เพิ่มรายงานแยก: ปัจจุบัน flagเมื่อราคาขายก่อนหักต่ำกว่าต้นทุน ตัวอย่างขาย100 ทุน90 ลด20% จะไม่เข้าแท็บต่ำกว่าต้นทุนแม้สุทธิ80 ไม่ควรเปลี่ยนความหมายแท็บเดิมโดยไม่แจ้ง
8. แสดงความคืบหน้าขณะงานหนัก และล็อกการกระทำอื่นทั้งหน้าเมื่อRestore/ตั้งค่าใช้งาน: OperationsPanelมีbusyของตัวเองแยกจากparent ควรป้องกันผู้ใช้สั่งclear/importระหว่างrestore แม้ backendมีlockเรียงคำขอในprocessเดียว
9. อายุไฟล์สำรอง/Exportและแจ้งพื้นที่: ประวัติเก็บต่อเนื่องไม่มีนโยบายcleanup, restoreสร้างไฟล์ชื่อใหม่และคงไฟล์เก่าไว้; เพิ่มจัดการพื้นที่โดยห้ามลบไฟล์ที่ข้อมูลยังอ้างอิง
10. หากขยายไปหลายคนจึงเพิ่ม login/สิทธิ์/ผู้แก้จริง, การตรวจเวอร์ชันป้องกันแก้ทับจากหลายแท็บ และงานimportเบื้องหลัง. ปัจจุบันเหมาะกับ local single-user ไม่จำเป็นต้องเพิ่ม cloudเพื่อแก้7จุดข้างต้น

## ลำดับงานที่เสนอ

- รอบแรก: R1,R2,R3 เพื่อป้องกันข้อมูล/ยอดผิดแบบผ่านvalidation
- รอบถัดไป: R4,R5 เพื่อให้ล้างและกู้คืนทนต่อไฟล์หาย/IOfailure
- ต่อด้วย R6,R7 และประวัติย้อนหลัง/จัดการงวด/หน้าจัดการconfig
- เพิ่ม regressiontestsจากprobesก่อนแก้แต่ละข้อ และตรวจยอด5แหล่งเดิมหลังเปลี่ยน parser/calculation

การรีวิวนี้พบปัญหาจริงเพิ่มเติม จึงไม่ควรอ้างว่าโปรแกรมครบทุกกรณีจากการที่68testsเดิมผ่าน ไม่ได้ยืนยันว่า7จุดนี้เป็นปัญหาทั้งหมดที่เป็นไปได้

## เพิ่มเติม: Clean Code / โครงสร้างเพื่อพัฒนาและดูแลต่อ

คำตอบตรงไปตรงมา: มีพื้นฐานที่ดีหลายส่วน แต่ยังไม่ถือว่าจัดระเบียบพร้อมขยายฟีเจอร์ระยะยาวครบแล้ว เป็นโค้ดเดโมที่รวมหน้าที่และเขียนบีบไว้มาก การผ่าน tests/typecheck ไม่รับรองคุณภาพการแบ่งโมดูลหรือครอบคลุมทุกข้อผิดพลาด

### สิ่งที่ควรรักษาไว้

- TypeScript strict=true; backendมีPydanticสำหรับคำขอหลายจุด
- เงินคำนวณด้วยDecimal และปัดระดับสตางค์ที่กำหนด; Frontendทำหน้าที่แสดงผล ไม่ย้ายสูตรเงินไปใช้JavaScriptNumber
- Backendตรวจซ้ำก่อนExport ไม่เชื่อreadyจากหน้าเว็บ
- รวมSKUโดยคงต้นทาง/การแก้ไว้ และบันทึกProfile snapshot/Export checksum
- SQLใช้parameterสำหรับค่าข้อมูล; dynamicชื่อตารางปัจจุบันมาจากชุดค่าที่โค้ดกำหนด ไม่ใช่หลักฐานSQL injection
- มีการปิดworkbook, transactionในหลายจุด, AbortControllerสำหรับผลรายการ, ทดสอบข้อมูลแยกจากlive
- มีunit/integration/E2E และ independent control-total audit; สิ่งเหล่านี้เป็นฐานสำหรับrefactor

### C1 — จัดรูปแบบโค้ดและตั้งเครื่องมือตรวจอัตโนมัติก่อน
หลักฐาน `code-structure.json`: page.tsx 50,318ตัวอักษรใน201บรรทัด บรรทัดยาวสุด2,973; operations-panel.tsx 19,661ตัวอักษรใน62บรรทัด; globals.css บรรทัดยาวสุด16,211. ขนาดบรรทัดไม่ใช่เกณฑ์คุณภาพเพียงอย่างเดียว แต่ที่นี่หลายfunction/JSX/คำสั่งอยู่บรรทัดเดียว ทำให้reviewdiff/debugยาก
ไม่พบconfig ESLint/formatter, Ruff/Pythonformatter/typechecker หรือCIworkflowในdemo และpackage.jsonไม่มีlint/format script. `tsc`ไม่ตรวจHooks dependencyหรือรูปแบบโค้ด
เสนอ: formatterFrontend/CSS, Pythonformatter+linter และHooks lint; เพิ่มคำสั่งcheckที่รันซ้ำได้ แยกcommitจัดรูปแบบออกจากแก้พฤติกรรม ไม่ต้องเลือกรูปแบบที่ซับซ้อนหลายชุด

### C2 — Frontend แยกตามงานที่ผู้ใช้ทำ
`app/page.tsx`รวมworkspace/history/import/export/filter/table/master/bulkedit/drawer/confirmation/totals/loading, และมีuseStateจำนวนมาก. `operations-panel.tsx`รวม4featureและnetwork/stateของแต่ละfeature
เสนอ: ให้page.tsxประกอบหน้า; แยก ImportPanel, SalesTable, BulkEditDialog, EditDrawer, ShopTotals, BelowCostReport, ProfileEditor, ValuationSettings, ExportHistory, BackupRestore. แยกhookจัดการbatch/filterกับrequestออกจากJSX ไม่ต้องแยกทุกspanเป็นcomponent

### C3 — API client และสัญญาข้อมูลควรอยู่จุดเดียว
`api<T>`/error parsingซ้ำในpage.tsx:22และoperations-panel.tsx:19. Batch/SaleRow/ValuationเขียนTypeScriptด้วยมือ ส่วนbackendคืนdictและไม่มีresponse_modelชัดเจน ทำให้ชื่อ/nullablefieldเปลี่ยนข้างหนึ่งแล้วtypecheckอีกข้างไม่ตรวจเจอ; generic<T>ไม่ได้ตรวจJSONจริงที่runtime
เสนอ: กำหนดPydantic request/response schemas, OpenAPI contract และfrontendtypesจากสัญญาเดียว; ใช้sharedAPIclient/error model/formatเงินและวันที่ เก็บเงินเป็นdecimalstringในcontractเหมือนเดิม เพิ่มcontracttests

### C4 — Backend แยก HTTP / งานธุรกิจ / ที่เก็บข้อมูล
`backend/app.py`รวมFastAPIroutes, SQL/DDL, CRUD, fileIO, upload orchestration, mapping, summariesและexport. `core.py`รวม5sourceparsers, normalize, validation, math, warnings, mergeและExcelrender. `operations.py`รวมprofiles,valuation,history,zipvalidationและrestore
`operations.service()`import backend.appตอนรันเพื่อแก้dependencyวน และทดสอบเปลี่ยนDATA/DBglobal. ไม่ใช่ข้อผิดพลาดทุกครั้ง แต่ทำให้ขยาย/ทดสอบบริการเดี่ยวยาก
เสนอ: routersเรียกservices; servicesเรียกrepository/storage; parserแต่ละแหล่งอยู่คนละmoduleพร้อมregistry; configและconnectionส่งผ่านdependencyที่ชัดเจน คงเป็นแอปเดียว ไม่ต้องmicroservicesหรือเปลี่ยนframework

### C5 — แยก normalize / validate / derive ให้ผลข้างเคียงชัด
`validate`ทำทั้งเติมSKUfallback/defaultdiscount, อ่านต้นทุน/provenance, คำนวณ, เพิ่มhistorycontainerและเปลี่ยนstatusบนdictเดิม; summary/GETเรียกการderiveนี้ซ้ำ. ชื่อvalidateอย่างเดียวไม่บอกว่ามีการเติมbusinessfields และทำให้การจัดลำดับMasterผิดได้ตามR6
เสนอ: SourceRow (ต้นฉบับ), NormalizedSale, ValidationResult/ComputedTotalsที่ชัดเจน แยกการเติมค่าตามpolicyออกจากการตรวจ และให้การคำนวณคืนผลโดยไม่แก้ต้นฉบับโดยแอบแฝง เริ่มด้วยtypedmodelและtestsก่อนย้ายสูตร

### C6 — Transaction และที่เก็บข้อมูลต้องครอบคลุมไฟล์ด้วย
SQLiteWAL/parameterizedSQLเหมาะกับเดโม ไม่จำเป็นต้องเปลี่ยนDBทันที แต่CREATE TABLEทุกครั้งที่เปิดdb ไม่มีdatabase migrationversion และbatchเป็นJSONก้อนใหญ่ updateทั้งbatch. RowidorderingจากINSERT OR REPLACEไม่ใช่createdorderingที่แน่นอนเมื่อแก้ชุดเก่า. backupformatversionไม่ได้แทนdatabase migration
เสนอ: init/migrationแยก, repositoryรับผิดชอบtransaction, file staging/cleanupที่กู้ได้ตามR4/R5/R7, revisionสำหรับป้องกันแก้ทับก่อนรองรับหลายคน. ค่อยปรับตาราง/ดัชนีเมื่อมีขนาดข้อมูล/latencyจริง ไม่ต้องnormalizeDBทุกอย่างพร้อมrefactor

### C7 — Error handling และ log สำหรับตามปัญหา
หลายendpointcatch Exceptionแล้วคืนstr(ex)เป็น400/409 แม้บางกรณีเป็นปัญหาภายใน; บางIOexceptionขึ้น500ทั่วไป ไม่มีappstructuredlog/requestIDที่เห็นในโค้ด (มีserveraccesslogจากUvicorn)
เสนอ: domainerrorsแยกinvalidformat/mappingconflict/storagefailure, exceptionhandlerกลางและรหัสerrorที่frontendแปลได้; logtracebackด้านserverพร้อมrequest/batch/fileID โดยไม่ใส่rawเอกสาร/ข้อมูลส่วนตัวทั้งหมดลงlog; retryเฉพาะงานที่ทำซ้ำได้ไม่เพิ่มธุรกรรม

### C8 — State และ Hooks lifecycle ต้องมีcheck
ตัวอย่าง `EditDrawer useEffect`อ่านsavingแต่dependenciesมีเพียงonClose (`app/page.tsx:162`): เมื่อsavingเปลี่ยนเฉพาะภายในdrawer handlerอาจยังเห็นค่าเก่าและยอมEscapeระหว่างsave ข้อนี้เป็นการอ่านโค้ด ยังไม่ได้จำลองในbrowserในรอบนี้
OperationsPanelมีbusyแยกจากHome และ4sectionใช้runร่วมกันโดยไม่มีการยกเลิกrequestทุกจุด
เสนอ: ให้Hookslintช่วยจับdependency, ใช้stateการทำงานที่ระบุidle/loading/saving/errorชัดและประสานglobaldestructiveactions, testsจำลองlatency/เปลี่ยนtab/กดซ้ำ/ปิดdrawerขณะsave โดยไม่เพิ่มstatelibraryเพียงเพราะมีหลายuseState

### C9 — รักษาคุณภาพต่อเนื่อง ไม่ใช่จัดระเบียบครั้งเดียว
ไม่พบGitrepositoryในdemoหรือCIconfigของdemo. เพิ่มversioncontrolและcheckก่อนmergeตามระบบทีม; แยกdev/testdependenciesจากruntimeเมื่อจัดpackage. requirements.txtล็อกversionsอยู่แล้วจึงไม่ต้องอัปเดตทุกpackageเพียงเพื่อrefactor
จัดtestsเป็นdomain/parser/API/UI และfixturesกลางแทนimportclient/seedจากtest_grouping.py; เพิ่มregressionตาม7probes, fault-injectionและAPIcontract. ไม่ใช้จำนวนtestsหรือcoverage%เพียงอย่างเดียวสรุปความถูกต้อง

### โครงสร้างเป้าหมายที่เสนอ (ยังไม่ได้สร้าง)

```text
app/page.tsx                     # ประกอบหน้า
features/import/                # UI + hooks ของการนำเข้า
features/sales/                 # ตาราง/แก้ไข/รวมยอด
features/settings/              # profiles และฐานราคา
features/history/               # import/export history
features/backup/                # สำรอง/กู้คืน
components/ui/                  # controls/dialog/loading ที่ใช้ซ้ำจริง
lib/api/                        # client, contract types, errors
lib/format/                     # การแสดงเงิน/วันที่
backend/main.py                 # app factory / middleware / routes
backend/api/                    # routers และ request/response schemas
backend/services/               # import/export/mapping/backup workflows
backend/domain/                 # decimal math, validation, models
backend/parsers/                 # parser registry และแต่ละแหล่ง
backend/repositories/           # SQLite persistence
backend/storage/                # file store / archive / cleanup
backend/config.py
tests/                          # domain/parsers/api/ui + fixtures
```

ลำดับrefactor: (1) เก็บbaselineและ7redprobes (2) formatting/toolingแยกจากbehavior (3) แก้R1–R7ทีละงานพร้อมtests (4) แยกAPIcontract/clientและfrontendfeatures (5) แยกbackendlayers/transaction/migrations (6) ตรวจยอด5แหล่งและUIflowsหลังแต่ละชุด. ห้ามเปลี่ยนสูตรหรือรูปแบบConsign_sample.xlsxรวมกับงานจัดโค้ดโดยไม่มีเหตุผลและหลักฐานเฉพาะ

ไม่แนะนำเขียนระบบใหม่ทั้งก้อนหรือเปลี่ยนNext/FastAPIเพื่อแก้ความเป็นระเบียบ โครงสร้างปัจจุบันสามารถค่อย ๆ ปรับได้โดยรักษาการทำงานที่ผ่านการตรวจแล้ว
