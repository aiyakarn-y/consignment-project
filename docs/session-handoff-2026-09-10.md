# ConsignmentSystem — สรุปส่งต่องาน 10 กันยายน 2026

อ่านเอกสารนี้เมื่อเริ่ม session ใหม่ แล้วตรวจ Git และสภาพแวดล้อมจริงก่อนแก้ไข
สถานะด้านล่างเป็นข้อมูล ณ วันที่บันทึก ไม่ใช่การรับรองสถานะ Production ปัจจุบัน

## โปรเจกต์และขอบเขตที่ผู้ใช้ยืนยัน

- Workspace: `/Users/kittipat/Project-Work/Consignment-System`
- ชื่อระบบ: **ConsignmentSystem**; package version `0.3.0-beta.1` (Beta version 1)
- Git: `https://github.com/aiyakarn-y/consignment-project.git`
- ทำงานบน `develop` แล้ว merge/push เข้า `main` เมื่อทดสอบเสร็จตามที่ผู้ใช้ขอ
- ผู้ใช้ Deploy เอง: ไม่ Deploy หรือสร้างบริการ Cloud/สมัครแพ็กเกจแทน
- เว็บที่ผู้ใช้แจ้ง: `https://consignment-project.vercel.app/`
- แนวทางอนาคตที่เคยหารือ: GCP + Azure DevOps; ปัจจุบันใช้ GitHub + Vercel
- ผู้ใช้ต้องการทดสอบครอบคลุมก่อนส่งขึ้น Git และไม่ให้ยืนยันว่า “ครบทุกกรณี” เกินหลักฐาน

## โครงสร้างและไฟล์สำคัญ

- Frontend: Next.js / React / TypeScript ใน `frontend/`
- Backend: FastAPI / Python, ใช้ Decimal กับจำนวนเงินใน `backend/core.py`
- Template: `resources/templates/Consign_sample.xlsx`
- `backend/config.py`: environment และ paths อิง repo root
- `backend/repository.py`: SQLite/JSON repository, JSON snapshot + optimistic concurrency
- `backend/storage.py`: local assets; `backend/blob_storage.py`: Private Blob adapter
- `backend/cloud_transport.py` และ `frontend/lib/api-fetch.ts`: staged multipart upload / download transport
- `frontend/app/cloud-storage/route.ts`: scoped client upload token
- `frontend/app/cloud-download/route.ts`: ตรวจ ticket ก่อนสร้าง signed download URL
- `vercel.json`: frontend/backend Services ใน Vercel project เดียว
- คู่มือ: `docs/storage-modes.md`, `docs/vercel-deploy.md`, `docs/csv-import.md`
- กติกายอด/ราคา: `docs/business-rules.md`; backlog: `docs/review-backlog.md`

## กติกาธุรกิจที่ต้องรักษา

- รวมสินค้าโดย **SKU เท่านั้น** ไม่ใช้ Barcode เป็น key สำหรับรวมยอด
- Export หัวคอลัมน์ `Items, Price, Qty, Discount` ตาม Excel template
- แสดงส่วนลดแต่ละองค์ประกอบ 2 ตำแหน่ง; เก็บความละเอียดภายในและแจ้งผลต่างการปัด
- GP/MG, ต้นทุน, ราคาขาย และยอดส่งคืนต้องแยกความหมาย ห้ามนำมาแทนกันโดยไม่มีกติกา
- คำนวณส่วนลดจากยอดเมื่อมีฐานที่ใช้ได้; ถ้าไม่มีให้ 0% และแก้ภายหลังได้
- แก้ราคา/จำนวน/ส่วนลดรายรายการหรือหลายรายการแล้วต้องคำนวณยอดใหม่
- รองรับ Export เฉพาะรายการพร้อม, ประวัติ Import/Export และ paging, clear history,
  source evidence, backup/restore, below-cost review และการเลือกชีต

## คำสั่ง Local และข้อมูล

| โหมด | Start | Stop | Frontend |
|---|---|---|---|
| SQLite local | `npm start` | `npm run stop` | `http://localhost:3117` |
| SQLite Beta | `npm run beta:start` | `npm run beta:stop` | `http://localhost:3119` |
| JSON local Beta | `npm run json:start` | `npm run json:stop` | `http://localhost:3120` |
| JSON + Blob Beta | `npm run blob:start` | `npm run blob:stop` | `http://localhost:3121` |

- โหมดมี data directories แยกกัน ไม่ย้ายข้อมูลอัตโนมัติ; ใช้ Backup/Restore เพื่อย้าย
- `.env.beta`: login ของ Local Beta; `.env.blob`: Token และ prefix สำหรับ Blob local
- `.env.blob` สร้างแล้ว permission 0600; ผู้ใช้ใส่ Token แล้วและใช้ทดสอบจริงสำเร็จ
- Prefix ที่เตรียมในไฟล์: `consignment-local-test`; live probes ใช้ UUID prefix แยกแต่ละรอบ
- ห้ามพิมพ์ Token/รหัสผ่าน, commit `.env*`, หรือส่งข้อมูลจริงใน `data/` ขึ้น Git
- `_wrx-output/` ถูก ignore; เป็นที่เก็บ Log และหลักฐานทดสอบ ไม่ควรนำเข้าประวัติ Git

## Vercel environment

ให้ทั้งสอง service ได้รับค่าที่ตรงกับ environment ที่ Deploy:

| ตัวแปร | ค่า |
|---|---|
| `CONSIGN_STATE_DRIVER` | `json` |
| `CONSIGN_STORAGE_DRIVER` | `vercel_blob` |
| `CONSIGN_BLOB_PREFIX` | `consignment-production` สำหรับ Production |
| `BLOB_READ_WRITE_TOKEN` | ค่าลับจาก Private Blob — ไม่เก็บในเอกสาร |
| `CONSIGN_BETA_MODE` | ผู้ใช้ขอปิด login ชั่วคราวด้วย `0` |

- Mode `0` ปิด Basic auth ทั้ง frontend/backend แม้บน Vercel; ใครเข้าลิงก์ได้ก็แก้/ล้างข้อมูลได้
- เปิดกลับด้วย mode `1` + username/password; ถ้าไม่ตั้ง mode บน Vercel จะยังต้องล็อกอิน
- ไม่ตั้ง path local ของ Mac บน Vercel; ลบ optional path variables ที่เป็นค่าว่าง
- Blob mode ใช้ `/tmp/consignment-system` สำหรับ scratch; ข้อมูลถาวรอยู่ Blob
- เปลี่ยน environment แล้วต้อง Redeploy; อย่าให้ผู้ใช้ส่ง Token ในแชต

## ปัญหาที่พบและการแก้ใน session นี้

1. Backend import ล้ม: `CONSIGN_STATE_DRIVER` ไม่ใช่ `sqlite/json` ตาม Log จริง
2. Path config ล้ม: `CONSIGN_DATA_DIR` ถูกตั้งเป็นค่าว่าง; แนะนำลบเพื่อใช้ default
3. Startup ล้ม: Token หาย/รูปแบบผิด และ prefix หาย/รูปแบบผิด ตามลำดับ
4. `httpx.DecodingError`: iter_bytes คลาย gzip แล้ว แต่ Response ใหม่เก็บ encoding header
   เดิม ทำให้คลายซ้ำ แก้โดยถอด Content-Encoding/Length/Transfer-Encoding ก่อนสร้าง Response
5. PUT 412 ซ้ำ: เปลี่ยน versioned GET ให้ `Accept-Encoding: identity` พร้อม `cache=0`
   เพื่อหลีกเลี่ยง validator ของ compressed representation และรักษา CAS
   **ข้อจำกัด:** ทดสอบ mock ทำซ้ำกลไกนี้ได้ แต่ sample บน Blob จริงคืน ETag เดียวกัน
   ทั้งสองแบบ จึงยังไม่ยืนยันสาเหตุ 412 เดิมได้แน่นอน ห้ามอ้างว่าพิสูจน์แล้ว
6. PUT 503 ตอน Export: เพิ่ม retry สูงสุด 3 ครั้งสำหรับ 429/500/502/503/504 และ
   transport failure ตรวจอ่าน bytes หลังผลลัพธ์ไม่แน่นอน ก่อนลอง path/content/ETag เดิม
   ถ้าบันทึกสำเร็จแล้วให้สำเร็จโดยไม่สร้างซ้ำ; ถ้ามี writer อื่นเปลี่ยนข้อมูลให้ conflict
   ห้ามปิด CAS, strip ETag หรือเปลี่ยนไปใช้ ETag ใหม่เพื่อฝืนเขียน
7. เพิ่ม CSV sales import ผ่าน **Mapping profile ที่ยืนยันแล้ว** ไม่เดาคอลัมน์อัตโนมัติ
   UTF-8/BOM, UTF-16 BOM, CP874; comma/semicolon/tab; quoted multiline; literal cells
   และ SKU ศูนย์นำหน้า รองรับ 25 MB, 50,000 rows, 200 columns, 1,000,000 cells
   เพิ่ม source path/download allowlists ให้ Backup/Restore และ Blob รองรับ CSV ด้วย
   XLSX/PDF เดิมยังรองรับ; CSV แสดงเป็นชีต `CSV`; Export ยังคง XLSX

## Git อ้างอิงก่อนบันทึกเอกสารนี้

- `5745d03`: optional Beta login
- `936bb6b`: แก้ double decompression
- `4549dbf`: versioned Blob GET ใช้ identity encoding
- `f5bfd25`: retry temporary Blob PUT failures
- `eb557dd`: ขยาย export fault tests
- **`f0100fa`: CSV support — latest implementation merge ณ เวลาสรุป**
- Commit ของเอกสารส่งต่อนี้จะใหม่กว่ารายการข้างต้น; ตรวจ `git log` จริงเมื่อเริ่มงาน

## หลักฐานทดสอบและข้อจำกัด

- หลังเพิ่ม CSV: Python **172 passed**; TypeScript ผ่าน
- CSV browser E2E ผ่าน (build แบบ production, สร้าง Mapping → Import → download XLSX)
- Expanded Blob suite 33 tests: new/existing object, transient statuses, timeout,
  lost response, verification-read failure, stale writer, permanent failure,
  ไม่มี export file/history ซ้ำหลัง recovery
- Live Blob ใช้ FastAPI TestClient บนเครื่องเชื่อม Private Blob จริง: sequential write,
  stale-write rejection, XLSX/CSV import, export + Excel readback, clear history,
  backup/restore + byte equality, remove file, clear batches ผ่านและล้าง test objects
- เคยพบ transient 503 ใน live test หนึ่งครั้งก่อนเพิ่ม retry; รอบหลังผ่าน
- Runtime probes/results: `_wrx-output/evidence/blob-live/`
- Plans: `_bmad-output/implementation-artifacts/` โดยเฉพาะ csv-import.md,
  blob-write-retry.md, blob-response-decoding.md, blob-conditional-writes.md
- ไม่ได้ยืนยัน latest deployed commit, browser signed download / large client upload
  บน Vercel หลังทุกการแก้ หรือ Docker; อย่าถือ local/live adapter tests แทนสิ่งเหล่านี้
- JSON snapshot limit 64 MiB และอ่านทั้งก้อน เหมาะ Beta กลุ่มเล็ก
- CAS ป้องกัน overlapping writes ไม่ใช่ทุกกรณีของฟอร์มเก่าที่ส่งภายหลัง
- Failed/cancelled uploads และการลบรายการไฟล์แบบ logical อาจทิ้ง orphan assets;
  ไม่ทำ sweep บน JSON เพราะเสี่ยงลบไฟล์ที่คำขออื่นยังบันทึกไม่เสร็จ
- Retry PUT ไม่ได้แก้ provider outages ถาวร หรือเพิ่ม retry ทุก GET/DELETE/startup

## แนวทางเริ่มงานครั้งถัดไป

1. อ่าน AGENTS.md และเอกสารนี้ ตรวจ branch/status และงานผู้ใช้ที่ยังไม่ commit
2. ระบุ PATH/REASON/EVIDENCE/MODEL ROUTE ก่อนแก้หรือ review
3. หากเป็น Vercel bug ให้ตรวจ endpoint และ Runtime Log; อย่าเดาว่าเป็น environment
4. เพิ่ม regression test ที่ทำซ้ำปัญหา ใช้ data/prefix ทดสอบแยก ไม่ clear Production
5. Run checks ที่เกี่ยวข้อง, commit/push develop, merge/push main เมื่ออยู่ในขอบเขตที่อนุญาต
6. แจ้ง commit ที่ควร Deploy และผลทดสอบจริง ผู้ใช้เป็นคน Deploy เอง
