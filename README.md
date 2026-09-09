# ConsignmentSystem

เว็บภาษาไทยสำหรับนำเข้ารายงานขายฝากขาย ตรวจ/แก้ข้อมูล รวมตาม SKU และส่งออกตามแม่แบบ `Consign_sample.xlsx` โค้ด Frontend/Backend และข้อมูล Local อยู่ใต้ Workspace เดียวกัน โดย `data/` ไม่เข้า Git หรือ Docker image

## ใช้งานบนเครื่อง

Workspace นี้เตรียม dependency, .env และ production build ไว้แล้ว:

```bash
cd /Users/kittipat/Project-Work/Consignment-System
npm start
```

เปิด **http://127.0.0.1:3117** Backend ใช้ **http://127.0.0.1:8100/api/health**

หยุดด้วย **Ctrl+C** ใน Terminal ที่เปิด หรือเปิดอีก Terminal แล้วใช้:

```bash
cd /Users/kittipat/Project-Work/Consignment-System
npm run stop
npm run status
```

Start/Stop จากโฟลเดอร์อื่นได้ด้วย `bash /Users/kittipat/Project-Work/Consignment-System/scripts/start.sh` และ `stop.sh` ข้อมูลยังอยู่หลังหยุดระบบ ตัวหยุดตรวจตัว supervisor ของ Workspace นี้ ไม่สั่งปิดทุกโปรแกรมที่ใช้พอร์ต

ถ้า `npm start` ขณะระบบเปิดอยู่แล้ว จะแจ้ง URL เดิมและจบคำสั่งโดยไม่เปิดบริการซ้ำ หากพอร์ตถูกโปรแกรมอื่นใช้จะแจ้ง Backend/Frontend และเลขพอร์ต โดยไม่ปิดโปรแกรมนั้นอัตโนมัติ

หลังแก้โค้ด ให้ Stop → `npm run build` → Start

ติดตั้งบนเครื่องใหม่: ใช้ Node.js 22+ และ Python 3.14 แล้วรัน `npm run setup` (ติดตั้ง dependency, สร้าง .env หากยังไม่มี และ Build) พัฒนาเฉพาะ Frontend ใช้ `npm --prefix frontend run dev` โดยเปิด Backend แยกด้วย `.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8100 --reload` ปิด production server ก่อนใช้พอร์ตเดียวกัน

## ทดสอบ Local

```bash
npm test
npm run typecheck
npm run build
node frontend/node_modules/@playwright/test/cli.js install chromium
npm run test:e2e
npm run audit
```

Python tests ใช้ temporary database; E2E ใช้ `data/test/e2e/<run-id>` กับพอร์ต 8101/3118 แยกจาก Local. `audit` ตรวจไฟล์ตัวอย่าง 5 แหล่งที่ `data/local/samples` ซึ่งไม่ได้อยู่ใน Git; หากย้ายเครื่องให้คัดลอกไฟล์ตัวอย่างเอง ผลตรวจและไฟล์ทดสอบอยู่ `_wrx-output/evidence` ห้ามนำไฟล์ที่ใช้ SKU สมมติไปใช้ธุรกิจ

## ข้อมูลและ Environment

- `data/local/database/consignment-system.sqlite3`: ชุดข้อมูล Mapping กติกา Profile ฐานราคา และประวัติ
- `data/local/imports/<batch-id>/<file-id>.xlsx|pdf`: สำเนา Import
- `data/local/exports/<export-id>.xlsx`: ไฟล์ Export แต่ละครั้ง
- `data/local/backups`: สำรองรุ่นใหม่และรุ่นเดิม เก็บไว้จนกว่าจะจัดการเอง
- `data/local/temp`: ไฟล์ระหว่างประมวลผล ใช้ atomic publish เพื่อไม่ให้ไฟล์ที่เขียนไม่ครบถูกบันทึกเป็นผลสำเร็จ
- `data/local/logs`: Log และข้อมูล supervisor สำหรับ Start/Stop

แก้ `.env` ตาม `.env.example`; เส้นทาง relative อิงรากโปรเจกต์เสมอ OS Environment มีลำดับเหนือ .env. Backend อ่าน `.env` โดยตรง; Local supervisor ส่ง URL Backend ให้ Frontend ตอนเริ่ม. ห้ามใส่ค่าลับในตัวแปรที่ส่งไป Browser

การล้างข้อมูลนำเข้าลบชุดงานและสำเนา Import แต่คง Export/ทะเบียนตรวจซ้ำ/การตั้งค่า/Backup ไว้ หน้า History ระบุเมื่อไฟล์ Import ไม่พร้อมดาวน์โหลด หากลบไฟล์ไม่สำเร็จมีคิวลองใหม่ตอนเริ่ม Backend หรือเรียก `POST /api/storage/cleanup`. ไฟล์ต้นฉบับที่ผู้ใช้เลือกอัปโหลดไม่ถูกลบ และ Backup เดิมอาจยังมีสำเนาข้อมูลก่อนล้าง

## Docker บน Local

ต้องมี Docker Engine พร้อม Compose v2 ทำงานอยู่ เครื่องที่จัดทำ Workspace นี้ยังไม่มี Docker engine จึงยังไม่ได้ทดสอบสร้าง/รัน Container จริง

```bash
npm run docker:up
npm run docker:down
```

คำสั่ง Up สร้างโฟลเดอร์ข้อมูลเริ่มต้นหากจำเป็น ตั้ง UID/GID ของ Backend ให้เขียน bind mount ได้ แล้วรัน Compose แบบ foreground. เปิด http://127.0.0.1:3117 เช่นเดิม และหยุด Native Local ก่อนใช้พอร์ตนี้. `docker:down` เก็บ `data/` ไว้

Backend ใช้ mount `/data`; Frontend อ่าน `CONSIGN_BACKEND_URL=http://backend:8100` ตอนรัน ไม่ฝัง URL ของ Local ไว้ตอน Build. ทั้งสอง image ใช้ non-root user. หากตั้ง CONSIGN_DATA_DIR เป็นเส้นทางอื่น ให้สร้างโฟลเดอร์นั้นก่อน Compose Up. บน Windows ใช้ WSL หรือกำหนด CONSIGN_DOCKER_UID/GID ให้ตรงเครื่องรัน

## Import / Export / Backup

นำเข้า XLSX/PDF รูปแบบเดิม หรือเลือก Profile ที่ตั้งค่าใน **ตั้งค่า / ประวัติ**. ใช้ **โหลดชุดตัวอย่าง** เมื่อต้องการอ่าน 5 แหล่งจาก samples. คงรหัสอ้างอิงกรณีไม่มีสี/ไซซ์และแก้ภายหลังได้. เลือก Checkbox เพื่อแก้หลายแถว. ส่วนลดที่ข้อมูลไม่พอใช้0%และมีป้ายกำกับ

**Export เฉพาะรายการที่พร้อม** ข้ามแถว/ไฟล์ที่ยังผิด; **Export Excel** ทั้งชุดใช้ได้เมื่อทุกแถวพร้อม. ทุกครั้งรวม SKU ตรงกันโดยไม่ใช้ Barcode และบันทึกไฟล์เดิมไว้ดาวน์โหลดซ้ำ. GP/MG, ต้นทุนและยอดหลังส่วนลดแยกความหมาย; UIแสดงส่วนลด2ตำแหน่งแต่ใช้ค่าละเอียดในการคำนวณ/Excel

Backup รุ่นใหม่ format `consignment-system-backup` version2 รองรับเส้นทางแบบแยกหมวด; ยังกู้คืน `consign-demo-backup` version1 ได้. กู้คืนต้องตรวจไฟล์/จำนวนก่อนยืนยัน และสำรองก่อนแทนที่. ไม่มีการยืนยันตัวตนผู้ใช้ใน Local นี้

## ย้ายจากเดโมเดิม

หยุดเดโมเดิมก่อน คำสั่งปฏิเสธการเขียนทับฐานข้อมูลปลายทาง:

```bash
.venv/bin/python scripts/migrate-demo.py --source /path/to/old/demo/_wrx-output/data
```

คัดลอกฐานข้อมูลและไฟล์ที่ยังถูกอ้างอิง รักษา ID/ประวัติ/ยอด ตรวจ SHA256 สร้าง ZIP รุ่นเดิมก่อนย้าย และคัดลอก Backup เก่า. ไฟล์ cache ที่ไม่มีข้อมูลอ้างอิงคงอยู่ในเดโมเดิมและแจ้งจำนวนในรายงาน. ผลย้ายอยู่ `_wrx-output/evidence/migration.json`. ไม่ต้องรันคำสั่งซ้ำบน Workspace ที่ย้ายสำเร็จแล้ว

## การพัฒนาต่อ

ใช้ AGENTS.md และ `.agents/skills` สำหรับ Codex. กติกาคำนวณอยู่ [business-rules](docs/business-rules.md); รายการปัญหาที่รีวิวพบอยู่ [review-backlog](docs/review-backlog.md). งานนี้จัด Workspace/storage ไม่ได้แก้ทุกข้อใน backlog เช่น header drift, multi-sheet และนโยบายต้นทุนแทนยอดสุทธิ

Git เป็น repository บนเครื่อง ยังไม่มี Azure remote หรือการ Push. ไม่มีการสร้าง GCP resources/Auto Deploy ในรอบนี้. การเชื่อม Azure DevOps และเลือก GCP runtime/database เป็นงานเฟส Deploy; รองรับเพิ่ม object-storage adapter ผ่าน `backend/storage.py` โดยไม่ให้ Frontend อ้าง pathจริง
