# Deploy ด้วยตนเองบน Vercel

โค้ดมี configuration สำหรับ Next.js + FastAPI Services และ JSON บน Private
Blob แล้ว แต่ยังไม่ผ่านการ Deploy หรือทดสอบกับ Blob จริง ผลทดสอบบนเครื่อง
และ mock ไม่ได้ยืนยันว่า Cloud พร้อมใช้งานครบทุกกรณี

## 1. เตรียม repository

ใช้ `aiyakarn-y/consignment-project` และ branch `main` สำหรับรุ่นที่ตรวจแล้ว
ใช้ `develop` สำหรับการพัฒนาต่อไป เลือก repo root เป็น Root Directory
ไม่เลือก `frontend/` เพราะมีทั้งสอง service ใน `vercel.json`

## 2. เตรียม Vercel Project และ Private Blob

Import repository ใน Vercel เลือก Framework Preset เป็น **Services**
สร้าง Blob store แบบ **Private** และเชื่อมกับ project ใน environment ที่ต้องการ
เลือกแพ็กเกจ/Trial ตามบัญชีของคุณ ระบบนี้ไม่ได้สมัครหรืออัปเกรดให้อัตโนมัติ
ไม่ต้องสร้าง Neon เพราะโหมดนี้เก็บ metadata เป็น JSON ใน Blob

## 3. ตั้ง Environment Variables ของทั้งสอง service

| ชื่อ | ค่า |
| --- | --- |
| `CONSIGN_STATE_DRIVER` | `json` |
| `CONSIGN_STORAGE_DRIVER` | `vercel_blob` |
| `CONSIGN_BLOB_PREFIX` | เช่น `consignment-production` |
| `BLOB_READ_WRITE_TOKEN` | token ของ Private Blob จาก dashboard |
| `CONSIGN_BETA_MODE` | `1` |
| `CONSIGN_BETA_USER` | `beta` |
| `CONSIGN_BETA_PASSWORD` | รหัสสำหรับผู้ทดสอบ อย่างน้อย 12 ตัว ASCII ไม่มีช่องว่าง |

ตั้ง namespace ของ Preview เป็นอีกค่า เช่น `consignment-preview`
เพื่อไม่ให้ Preview แก้ข้อมูล Production โดยไม่ได้ตั้งใจ ทุก preview ที่ใช้
namespace เดียวกันจะเห็นข้อมูลชุดเดียวกัน

อย่าใช้ชื่อ `NEXT_PUBLIC_` กับ token/รหัสผ่าน อย่า upload `.env` หรือข้อมูล
`data/` เข้า repository และอย่าคัดลอก `CONSIGN_DATA_DIR` / template path /
Backend localhost ของเครื่องคุณไป Vercel

## 4. Build / Deploy

ใช้ค่าจาก `vercel.json`: frontend build ด้วย `next build --webpack`, backend
entrypoint `backend.app:app`, Python 3.14 จาก `.python-version` และ dependency
จาก `requirements.txt` ไฟล์ template อยู่ `resources/templates/Consign_sample.xlsx`
หาก Vercel แสดงข้อผิดพลาด ให้ตรวจ build/runtime logs ก่อนเปิดให้ผู้ใช้

## 5. ตรวจด้วยข้อมูลทดสอบ

1. เปิดลิงก์ ต้องถาม Username/Password และเรียก API โดยไม่ล็อกอินไม่ได้
2. ตรวจ `/api/health` หลังล็อกอิน: `state_driver=json`, `storage_driver=vercel_blob`
3. สร้างชุดข้อมูลและ Import Excel/PDF; ทดลองไฟล์รวมเกิน 4.5 MB ด้วย
4. แก้ราคา/ส่วนลด ตรวจยอด แล้ว Export และเปิด Excel ที่ดาวน์โหลด
5. ตรวจประวัติและ paging; ลอง Backup/Restore บนข้อมูลทดสอบเท่านั้น
6. เปิดอีก browser และ Redeploy เพื่อยืนยันว่าข้อมูลยังอยู่
7. ทดลองบันทึกพร้อมกัน ต้องไม่เขียนทับเงียบ ๆ; หากได้ 409 ให้โหลดข้อมูลใหม่

ตรวจ Blob ว่าข้อมูลอยู่ใน namespace ที่ตั้งไว้ รวม `state/system.json`,
`imports/`, `exports/`, `backups/` เฉพาะ staging สำหรับไฟล์ระหว่างส่งเท่านั้น
ที่เป็นข้อมูลชั่วคราว

## ขอบเขต Beta

JSON metadata สูงสุด 64 MiB และอ่าน snapshot ทั้งชุด เหมาะกับผู้ทดสอบกลุ่มเล็ก
ยังไม่มีบัญชี/สิทธิ์แยกรายบุคคลและยังไม่ป้องกันทุกกรณีของฟอร์มที่เปิดค้างเก่า
ถ้าใช้งานมากขึ้นควรประเมินฐานข้อมูลและการจัดการ concurrency เพิ่ม
รายละเอียดการสลับโหมด/ย้ายข้อมูลอยู่ [storage-modes.md](storage-modes.md)

เอกสารทางการ: [Services](https://vercel.com/docs/services),
[Private Blob](https://vercel.com/docs/vercel-blob/private-storage),
[Python runtime](https://vercel.com/docs/functions/runtimes/python)
